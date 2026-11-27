"""Secure-ripping prototype: offline tests only, NEVER access real drives."""
import json
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from oscar import ripping
from oscar.api import app

STABLE = "ata-Optiarc"
DISC = "I5l9cCSFccLKFEKS.7wqSZAorPU-"
TOKEN = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    stage = tmp_path / "staging"
    stage.mkdir()
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(stage))
    monkeypatch.setattr(ripping, "selected_drive", lambda stable: ("/dev/sr2", 667))
    monkeypatch.setattr(ripping, "read_toc", lambda device: {
        "musicbrainz_disc_id": DISC, "tracks": [{"number": 1}]})
    monkeypatch.setattr(ripping, "_ACTIVE", set())
    monkeypatch.setattr(ripping, "_JOBS", {})
    return stage


def test_no_rip_when_disabled(monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_RIPPING", raising=False)
    with pytest.raises(ripping.RipError, match="disabled"):
        ripping.plan(STABLE)
    r=TestClient(app).post("/api/rip/start",json={"stable_id":STABLE,
                    "confirmation":"RIP_TO_STAGING"},headers={"X-OSCAR-RIP-TOKEN":TOKEN})
    assert r.status_code == 403


def test_token_and_confirmation_required(sandbox):
    client=TestClient(app)
    payload={"stable_id":STABLE, "confirmation":"RIP_TO_STAGING"}
    assert client.post("/api/rip/start",json=payload).status_code==403
    assert client.post("/api/rip/start",json={"stable_id":STABLE,"confirmation":"no"},
                       headers={"X-OSCAR-RIP-TOKEN":TOKEN}).status_code==422
    assert not list(sandbox.iterdir())


def test_fixed_safe_command_and_offset(sandbox):
    info=ripping.plan(STABLE)
    args=info["command"]
    assert args[:5]==["cyanrip","-d","/dev/sr2","-s","667"]
    assert args[args.index("-D")+1]=="audio"
    assert "-N" in args and "-o" in args
    assert "-B" not in args  # Debian cyanrip 0.9.3 does not support -B
    assert "-A" not in args  # AccurateRip must remain enabled
    assert "-Q" not in args and "-O" not in args
    assert info["disc_id"]==DISC


def test_only_new_folder_receives_rip_and_hashes(sandbox):
    existing=sandbox/"DO_NOT_TOUCH.txt"
    existing.write_text("untouched")
    def fake_runner(args, *, cwd, stdout, stderr, timeout, check):
        assert args[0]=="cyanrip" and check is False
        output=Path(cwd)/"audio"
        output.mkdir()
        (output/"01 - Test.flac").write_bytes(b"fake flac in unit test")
        stdout.write(b"fake cyanrip output")
        return SimpleNamespace(returncode=0)
    job=ripping.start(STABLE,runner=fake_runner)
    for _ in range(100):
        state=ripping.status(job["id"])
        if state["status"] not in ("queued","running"):
            break
        time.sleep(.01)
    assert state["status"]=="needs_verification"
    assert state["flac_count"]==1
    assert len(state["files_sha256"]["audio/01 - Test.flac"])==64
    assert existing.read_text()=="untouched"
    folders=list(sandbox.glob("oscar-*"))
    assert len(folders)==1
    assert (folders[0]/"cyanrip-console.log").exists()
    assert (folders[0]/"plan.json").exists()
    assert (folders[0]/"state.json").exists()


@pytest.mark.parametrize("lookup_fails", [False, True])
def test_ctdb_runs_automatically_after_full_rip(sandbox, monkeypatch, lookup_fails):
    from threading import Event
    from oscar import ctdb_verification

    monkeypatch.setenv("OSCAR_CTDB_EXECUTABLE", "/opt/ctdb/ctdb-cli")
    completed = Event()
    calls = []

    def extract(args, *, cwd, **kwargs):
        audio = Path(cwd) / "audio"
        audio.mkdir()
        (audio / "01 - Test.flac").write_bytes(b"saved staged tracks")
        (audio / "disc.cue").write_text(
            'FILE "01 - Test.flac" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n')
        return SimpleNamespace(returncode=0)

    def ctdb(args, **kwargs):
        calls.append(args)
        assert STABLE not in ripping._ACTIVE
        if lookup_fails:
            raise subprocess.TimeoutExpired(args, 180)
        return SimpleNamespace(returncode=0, stderr=b"", stdout=(
            f'<ctdb xmlns="{ctdb_verification._NAMESPACE}"><verify_result xmlns=""'
            ' status="found" confidence="2" total_entries="3"/></ctdb>').encode())

    monkeypatch.setattr(ctdb_verification.subprocess, "run", ctdb)
    job = ripping.start(STABLE, runner=extract, on_completed=lambda _: completed.set())
    assert completed.wait(3)
    directory = sandbox / ("oscar-" + job["id"])
    evidence, _ = ctdb_verification.saved_evidence(job["id"], directory)
    assert evidence["trigger"] == "automatic"
    assert evidence["status"] == ("lookup_failed" if lookup_fails else "matched")
    assert ripping.status(job["id"])["status"] == "needs_verification"
    ctdb_verification.automatic(job["id"], directory)
    assert len(calls) == 1


def test_nonzero_exit_never_claims_verified(sandbox):
    job=ripping.start(STABLE,runner=lambda *a,**k:SimpleNamespace(returncode=2))
    for _ in range(100):
        state=ripping.status(job["id"])
        if state["status"] not in ("queued","running"):break
        time.sleep(.01)
    assert state["status"]=="failed"
    assert "cyanrip" in state["error"]


def test_reject_staging_root_symlink(sandbox, tmp_path, monkeypatch):
    fake=tmp_path/"redirect"
    fake.symlink_to(sandbox, target_is_directory=True)
    monkeypatch.setenv("OSCAR_RIP_ROOT",str(fake))
    with pytest.raises(ripping.RipError,match="real directory"):
        ripping.staging_root()


def test_rip_button_is_explicit():
    html=TestClient(app).get("/").text
    assert "Test rip to staging (experimental)" in html
    assert "RIP_TO_STAGING" in html
    assert "X-OSCAR-RIP-TOKEN" in html


def test_interrupted_job_is_not_reported_as_success(sandbox):
    jobid="d"*32
    directory=sandbox/("oscar-"+jobid)
    directory.mkdir()
    (directory/"state.json").write_text(json.dumps({"id":jobid,"status":"running"}))
    assert ripping.status(jobid)["status"]=="interrupted"


def test_tray_control_busy_guard_and_read_only_ioctl(sandbox):
    calls = []
    def opener(device, flags):
        assert device == "/dev/sr2"
        assert flags & os.O_NONBLOCK
        return 9
    def ioctl(fd, op):
        calls.append((fd, op))
    def closer(fd):
        calls.append(("close", fd))
    assert ripping.control_tray(STABLE, "eject", opener=opener,
                                closer=closer, ioctl=ioctl)["status"] == "command_sent"
    assert calls == [(9, 0x5309), ("close", 9)]
    calls.clear()
    ripping.control_tray(STABLE, "close", opener=opener,
                         closer=closer, ioctl=ioctl)
    assert calls == [(9, 0x5319), ("close", 9)]
    ripping._ACTIVE.add(STABLE)
    with pytest.raises(ripping.RipError, match="busy"):
        ripping.control_tray(STABLE, "eject", opener=opener, ioctl=ioctl)
    ripping._ACTIVE.clear()
    with pytest.raises(ripping.RipError, match="Unsupported"):
        ripping.control_tray(STABLE, "toggle", opener=opener, ioctl=ioctl)


def test_selected_track_diagnostic_is_never_a_full_disc_workflow(sandbox, monkeypatch):
    from oscar import workflow_ledger
    monkeypatch.setattr(ripping, "read_toc", lambda device: {
        "musicbrainz_disc_id": DISC,
        "tracks": [{"number": n} for n in range(1, 18)]})
    assert ripping.plan(STABLE, selected_tracks=[17, 1, 5])["command"][-2:] == ["-l", "1,5,17"]
    for wrong in ([7, 7], [18], [0], ["7"], []):
        with pytest.raises(ripping.RipError, match="Selected tracks"):
            ripping.plan(STABLE, selected_tracks=wrong)
    def runner(args, *, cwd, stdout, stderr, timeout, check):
        assert args[-2:] == ["-l", "7"]
        output = Path(cwd) / "audio"
        output.mkdir()
        (output / "07 - Diagnostic.flac").write_bytes(b"diagnostic")
        return SimpleNamespace(returncode=0)
    job = ripping.start(STABLE, runner=runner, selected_tracks=[7])
    for _ in range(100):
        state = ripping.status(job["id"])
        if state["status"] not in ("queued", "running"):
            break
        time.sleep(.01)
    assert state["status"] == "partial_diagnostic"
    assert state["selected_tracks"] == [7]
    assert (sandbox / ("oscar-" + job["id"]) / "audio" / "07 - Diagnostic.flac").exists()
    with pytest.raises(workflow_ledger.WorkflowError, match="diagnostic"):
        workflow_ledger._observed_phase(job["id"], state)


def test_stop_preserves_partial_staging_and_interrupted_job(sandbox, monkeypatch):
    import threading
    ready = threading.Event()
    stopped = threading.Event()
    class FakeProcess:
        def __init__(self, args, *, cwd, stdout, stderr):
            assert args[0] == "cyanrip"
            output = Path(cwd) / "audio"
            output.mkdir()
            (output / "01 - Partial.flac").write_bytes(b"partial audio")
            ready.set()
        def poll(self):
            return None if not stopped.is_set() else -15
        def terminate(self):
            stopped.set()
        def wait(self, timeout):
            assert stopped.wait(2)
            return -15
    monkeypatch.setattr(subprocess, "Popen", FakeProcess)
    job = ripping.start(STABLE)
    assert ready.wait(2)
    assert ripping.stop(job["id"])["status"] == "stop_requested"
    for _ in range(100):
        state = ripping.status(job["id"])
        if state["status"] == "interrupted":
            break
        time.sleep(.01)
    assert state["status"] == "interrupted"
    assert "partial staging" in state["error"]
    folder = sandbox / ("oscar-" + job["id"])
    assert (folder / "audio" / "01 - Partial.flac").read_bytes() == b"partial audio"
    assert (folder / "cyanrip-console.log").exists()
    assert (folder / "plan.json").exists()
    assert (folder / "state.json").exists()
    with pytest.raises(ripping.RipError, match="active"):
        ripping.stop(job["id"])


def test_ui_control_endpoint_confirmation_and_diagnostic_restrictions(sandbox):
    client = TestClient(app)
    headers = {"X-OSCAR-RIP-TOKEN": TOKEN}
    assert client.post("/api/rip/tray", json={
        "stable_id": STABLE, "action": "eject", "confirmation": "no"
    }, headers=headers).status_code == 422
    assert client.post("/api/rip/jobs/" + "a"*32 + "/stop", json={
        "confirmation": "no"}, headers=headers).status_code == 422
    assert client.post("/api/go/start", json={
        "stable_id": STABLE, "selected_tracks": [7],
        "confirmation": "RIP_TO_STAGING"}, headers=headers).status_code == 422
    assert client.post("/api/rip/start", json={
        "stable_id": STABLE, "selected_tracks": [7],
        "confirmation": "RIP_TO_STAGING"}, headers=headers).status_code == 422
    html = client.get("/").text
    assert "Stop rip…" in html
    assert "Advanced · rip selected tracks" in html
    assert "/api/rip/tray" in html
    assert not list(sandbox.iterdir())
