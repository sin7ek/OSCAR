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
