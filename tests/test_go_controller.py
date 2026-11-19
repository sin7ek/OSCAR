"""Go controller phase 1: no real optical drives or web requests."""
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oscar import go_controller as go, workflow_ledger as ledger, ripping, verification
from oscar.settings import OscarSettings
from oscar.api import app

DRIVE = "test-drive"
DISC = "I5l9cCSFccLKFEKS.7wqSZAorPU-"
RELEASE1 = "4b370e6c-e6d2-36a5-8c47-5337a2d77d69"
RELEASE2 = "09fe4a40-7d2b-400e-b3de-b148f55fbcad"
TOKEN = "a" * 32


@pytest.fixture
def rig(tmp_path,monkeypatch):
    stage = tmp_path / "stage"
    stage.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("OSCAR_RIP_ROOT",str(stage))
    monkeypatch.setenv("OSCAR_WORKFLOW_DB",str(config/"workflow.sqlite3"))
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING","1")
    monkeypatch.setenv("OSCAR_RIP_TOKEN",TOKEN)
    monkeypatch.setattr(ripping,"selected_drive",lambda stable:("/dev/sr2",667))
    monkeypatch.setattr(ripping,"read_toc",lambda device:{
        "musicbrainz_disc_id":DISC,"toc_string":"1 2 1000 150 300",
        "tracks":[{"number":1},{"number":2}]})
    monkeypatch.setattr(ripping,"_ACTIVE",set())
    monkeypatch.setattr(ripping,"_JOBS",{})
    mode = {"mode":"best_guess"}
    monkeypatch.setattr(ledger,"discover_settings",lambda:OscarSettings(
        identification_mode=mode["mode"],secure_review_level="on_ambiguity"))
    report = {"status":"not_started"}
    monkeypatch.setattr(verification,"report",lambda job_id:{
        "job_id":job_id,**report})
    called = []
    monkeypatch.setattr(verification,"start",lambda job_id:called.append(job_id) or {
        "job_id":job_id,"status":"running"})
    monkeypatch.setattr(go.musicbrainz,"lookup_enabled",lambda:True)
    def runner(args,*,cwd,stdout,stderr,timeout,check):
        audio=Path(cwd)/"audio"
        audio.mkdir()
        (audio/"01 - Example.flac").write_bytes(b"test FLAC bytes 01")
        (audio/"02 - Example.flac").write_bytes(b"test FLAC bytes 02")
        stdout.write(b"mock rip log\n")
        return SimpleNamespace(returncode=0)
    return stage,mode,report,called,runner


def _finish(rig):
    stage,mode,report,called,runner = rig
    job=ripping.start(DRIVE,runner=runner,on_created=ledger.register_created,
                      on_completed=go._after_rip)
    for _ in range(200):
        if ripping.status(job["id"])["status"]=="needs_verification":
            break
        time.sleep(.01)
    assert ripping.status(job["id"])["status"]=="needs_verification"
    # The worker saves its completed rip state before invoking the
    # verification callback. Allow that asynchronous callback to complete.
    for _ in range(200):
        if called == [job["id"]]:
            break
        time.sleep(.01)
    assert called==[job["id"]]
    return job["id"]


def test_go_creates_ledger_before_worker_and_triggers_verification(rig):
    job_id=_finish(rig)
    state=ledger.register(job_id)
    assert state["identification_mode"]=="best_guess"
    assert state["events"][0]["reason"]=="go_created_before_extraction"
    assert len(state["events"])==1
    assert (rig[0]/("oscar-"+job_id)/"plan.json").is_file()
    assert state["automated_actions_enabled"] is False


def test_go_best_guess_is_persistently_inferred_never_physical(rig):
    job_id=_finish(rig)
    rig[2]["status"]="checks_passed"
    result=go.advance(job_id,lookup=lambda disc,toc:{"releases":[
        {"id":RELEASE1,"title":"Album","labels":[{"catalog_number":"AA 1"}],"barcode":"1234"}]})
    assert result["action"]=="best_guess_proposed"
    assert result["release_id"]==RELEASE1
    assert result["release_match_status"]=="INFERRED_NOT_PHYSICALLY_VERIFIED"
    assert not result["workflow"]["release_physically_verified"]
    assert len(result["workflow"]["events"])==3
    repeated=go.advance(job_id,lookup=lambda disc,toc:{"releases":[
        {"id":RELEASE1,"title":"Album","labels":[{"catalog_number":"AA 1"}]}]})
    assert len(repeated["workflow"]["events"])==3
    assert not list(rig[0].rglob("metadata-copy-*"))


def test_go_secure_mode_requires_edition_evidence(rig):
    rig[1]["mode"]="secure"
    job_id=_finish(rig)
    rig[2]["status"]="checks_passed"
    response=go.advance(job_id,lookup=lambda disc,toc:{"releases":[
        {"id":RELEASE2,"title":"Handel","labels":[{"catalog_number":"ES 99220"}]}]})
    assert response["action"]=="secure_physical_review"
    assert response["workflow"]["proposed_release_id"]==""
    assert response["catalog_or_barcode_needed"]
    assert not response["workflow"]["release_physically_verified"]


def test_go_blocked_on_failed_or_missing_evidence(rig):
    job_id=_finish(rig)
    result=go.advance(job_id,verify_start=lambda job:{"job_id":job,"status":"running"})
    assert result["action"]=="verifying"
    rig[2]["status"]="review_required"
    assert go.advance(job_id)["action"]=="verification_review"
    rig[2]["status"]="checks_passed"
    assert go.advance(job_id,lookup=lambda disc,toc:{"releases":[]})["action"]=="missing_release"


def test_go_missing_saved_toc_requires_review(rig):
    job_id=_finish(rig)
    rig[2]["status"]="checks_passed"
    plan_file=rig[0]/("oscar-"+job_id)/"plan.json"
    plan=json.loads(plan_file.read_text())
    plan.pop("toc_string")
    plan_file.write_text(json.dumps(plan))
    assert go.advance(job_id)["action"]=="toc_missing"


def test_go_api_auth_and_confirmation(rig):
    client=TestClient(app)
    payload={"stable_id":DRIVE,"confirmation":"RIP_TO_STAGING"}
    assert client.post("/api/go/start",json=payload).status_code==403
    assert client.post("/api/go/start",json={"stable_id":DRIVE,"confirmation":"wrong"},
         headers={"X-OSCAR-RIP-TOKEN":TOKEN}).status_code==422
    assert "Go! — rip to verified staging" in client.get("/").text


def test_go_failed_ledger_registration_prevents_cyanrip(rig,monkeypatch):
    def failure(job):
        raise ledger.WorkflowError("Database offline")
    monkeypatch.setattr(ledger,"register_created",failure)
    with pytest.raises(ledger.WorkflowError):
        go.start(DRIVE)
    assert not list(rig[0].rglob("cyanrip-console.log"))


def test_go_interrupted_extract_never_retries(rig):
    job_id=_finish(rig)
    ripping._JOBS.clear() # Simulate fresh process, no in-memory job status.
    state_file=rig[0]/("oscar-"+job_id)/"state.json"
    state=json.loads(state_file.read_text())
    state["status"]="running"
    state_file.write_text(json.dumps(state))
    result=go.advance(job_id)
    assert result["action"]=="interrupted_review"
    assert result["workflow"]["phase"]=="RIP_INTERRUPTED"


def test_go_poll_immediately_after_create_before_state_file(rig, monkeypatch):
    import threading
    gate=threading.Event()
    def delayed_run(job,device,offset,workdir,runner,on_completed):
        gate.wait(timeout=2)
    monkeypatch.setattr(ripping,"_run",delayed_run)
    try:
        result=go.start(DRIVE)
        job_id=result["job"]["id"]
        assert not (rig[0]/("oscar-"+job_id)/"state.json").exists()
        first=go.advance(job_id)
        assert first["action"]=="ripping"
        assert first["workflow"]["phase"]=="RIP_IN_PROGRESS"
    finally:
        gate.set()
