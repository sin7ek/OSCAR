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


def test_semi_automatic_snapshots_candidates_and_requires_explicit_acceptance(rig):
    rig[1]["mode"]="semi_automatic"
    job_id=_finish(rig)
    rig[2]["status"]="checks_passed"
    first=go.advance(job_id,lookup=lambda disc,toc:{"releases":[
        {"id":RELEASE1,"title":"Proposed disc-ID album","barcode":"123456789"},
        {"id":RELEASE2,"title":"Alternate edition"}]})
    assert first["action"]=="semi_release_review"
    assert first["workflow"]["identification_mode"]=="semi_automatic"
    assert first["workflow"]["accepted_release_id"]==""
    assert first["workflow"]["proposed_release_id"]==RELEASE1
    assert len(first["workflow"]["candidate_options"])==2
    assert first["workflow"]["release_match_status"]=="INFERRED_NOT_PHYSICALLY_VERIFIED"
    # Once frozen, browser polls and restarts do not silently replace options.
    second=go.advance(job_id,lookup=lambda disc,toc:{"releases":[]})
    assert second["action"]=="semi_release_review"
    assert len(second["workflow"]["candidate_options"])==2
    with pytest.raises(ledger.WorkflowError):
        ledger.accept_semi_release(job_id, RELEASE2,"WRONG")
    with pytest.raises(ledger.WorkflowError):
        ledger.accept_semi_release(job_id,"00000000-0000-0000-0000-000000000000",
                                    "ACCEPT_INFERRED_RELEASE")
    accepted=ledger.accept_semi_release(job_id,RELEASE2,"ACCEPT_INFERRED_RELEASE")
    assert accepted["phase"]=="RELEASE_ACCEPTED"
    assert accepted["accepted_release_id"]==RELEASE2
    assert accepted["release_match_status"]=="INFERRED_OPERATOR_ACCEPTED"
    assert not accepted["release_physically_verified"]
    assert not accepted["automated_actions_enabled"]
    assert ledger.accept_semi_release(job_id,RELEASE2,"ACCEPT_INFERRED_RELEASE")["events"]==accepted["events"]
    with pytest.raises(ledger.WorkflowError):
        ledger.accept_semi_release(job_id,RELEASE1,"ACCEPT_INFERRED_RELEASE")
    # A successful approval authorizes a *separate* isolated staging copy.
    # A broken metadata lookup must stop safely without modifying originals.
    outcome=go.advance(job_id,metadata_preview=lambda job,release: (_ for _ in ()).throw(
        go.metadata_staging.MetadataError("no exact medium")))
    assert outcome["action"]=="metadata_review_required"
    assert outcome["release_id"]==RELEASE2
    assert not list(rig[0].rglob("metadata-copy-*"))


def test_semi_automatic_can_defer_and_resume_without_losing_candidates(rig):
    rig[1]["mode"]="semi_automatic"
    job_id=_finish(rig)
    rig[2]["status"]="checks_passed"
    go.advance(job_id,lookup=lambda disc,toc:{"releases":[{"id":RELEASE1,"title":"Album"}]})
    ledger.review_action(job_id,"defer")
    assert go.advance(job_id)["action"]=="review_required"
    ledger.review_action(job_id,"resume")
    result=go.advance(job_id,lookup=lambda disc,toc:{"releases":[]})
    assert result["action"]=="semi_release_review"
    assert result["candidates"][0]["release_id"]==RELEASE1


def test_semi_automatic_api_requires_auth_and_does_not_create_tags(rig):
    rig[1]["mode"]="semi_automatic"
    job_id=_finish(rig)
    rig[2]["status"]="checks_passed"
    go.advance(job_id,lookup=lambda disc,toc:{"releases":[{"id":RELEASE1,"title":"Album"}]})
    client=TestClient(app)
    route=f"/api/go/jobs/{job_id}/accept-release"
    body={"release_id":RELEASE1,"confirmation":"ACCEPT_INFERRED_RELEASE"}
    assert client.post(route,json=body).status_code==403
    assert client.post(route,json={**body,"confirmation":"no"},
                       headers={"X-OSCAR-RIP-TOKEN":TOKEN}).status_code==409
    result=client.post(route,json=body,headers={"X-OSCAR-RIP-TOKEN":TOKEN})
    assert result.status_code==200
    assert result.json()["phase"]=="RELEASE_ACCEPTED"
    assert not list(rig[0].rglob("metadata-copy-*"))


def test_secure_and_best_guess_cannot_approve_through_semi_endpoint(rig):
    job_id=_finish(rig)
    rig[2]["status"]="checks_passed"
    go.advance(job_id,lookup=lambda disc,toc:{"releases":[{"id":RELEASE1}]})
    with pytest.raises(ledger.WorkflowError):
        ledger.accept_semi_release(job_id,RELEASE1,"ACCEPT_INFERRED_RELEASE")


def _fake_metadata_flow(job_id, release_id):
    calls = []
    fingerprint = "a" * 64
    def preview(job, release):
        calls.append(("preview", job, release))
        return {"job_id": job, "release_id": release,
                "fingerprint": fingerprint}
    def start(job, release, fp, confirmation, **kwargs):
        calls.append(("start", job, release, fp, confirmation, kwargs))
        return {"job_id": job, "copy_id": kwargs["reserved_copy_id"], "status": "running"}
    def status(job, copy_id):
        calls.append(("status", job, copy_id))
        return {"job_id": job, "copy_id": copy_id,
                "status": "tagged_copy_ready_for_review"}
    def inspect(job, copy_id):
        calls.append(("inspect", job, copy_id))
        return {"job_id": job, "copy_id": copy_id,
                "release_id": release_id, "status": "tags_match_preview"}
    return calls, {"metadata_preview": preview, "metadata_copy_start": start,
                   "metadata_copy_status": status, "metadata_copy_inspect": inspect}


def test_go_semi_metadata_handoff_is_durable_single_copy(rig):
    rig[1]["mode"] = "semi_automatic"
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    go.advance(job_id, lookup=lambda disc, toc: {"releases": [{"id": RELEASE1}]})
    matrix = "936245901-2.2 WME"
    ledger.accept_semi_release(job_id, RELEASE1, "ACCEPT_INFERRED_RELEASE",
                               matrix_runout=matrix)
    calls, adapters = _fake_metadata_flow(job_id, RELEASE1)
    started = go.advance(job_id, **adapters)
    assert started["action"] == "metadata_copy_running"
    copy_id = started["copy_id"]
    assert started["workflow"]["metadata_release_id"] == RELEASE1
    assert started["workflow"]["metadata_fingerprint"] == "a" * 64
    assert started["workflow"]["release_match_status"] == "INFERRED_OPERATOR_ACCEPTED"
    assert calls[-1][0] == "start"
    assert calls[-1][-1]["reserved_copy_id"] == copy_id
    assert calls[-1][-1]["matrix_runout"] == matrix
    assert started["workflow"]["matrix_runout"] == matrix
    assert calls[-1][-1]["identification_status"] == "INFERRED_OPERATOR_ACCEPTED"
    # No new worker can be launched on a repeat poll.
    result = go.advance(job_id, **adapters)
    assert result["action"] == "metadata_ready"
    assert result["copy_id"] == copy_id
    assert sum(item[0] == "start" for item in calls) == 1
    assert result["workflow"]["phase"] == "METADATA_READY"
    assert go.advance(job_id, **adapters)["action"] == "metadata_ready"
    assert sum(item[0] == "start" for item in calls) == 1
    assert not list(rig[0].rglob("metadata-copy-*"))
    assert len([e for e in result["workflow"]["events"]
                if e["reason"] == "metadata_copy_reserved_before_worker"]) == 1


def test_go_best_guess_handoff_only_uses_snapshotted_release(rig):
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    go.advance(job_id, lookup=lambda disc, toc: {"releases": [{"id": RELEASE1}]})
    calls, adapters = _fake_metadata_flow(job_id, RELEASE1)
    started = go.advance(job_id, **adapters)
    assert started["action"] == "metadata_copy_running"
    assert started["workflow"]["release_match_status"] == "INFERRED_NOT_PHYSICALLY_VERIFIED"
    assert calls[-1][-1]["identification_status"] == "INFERRED_NOT_PHYSICALLY_VERIFIED"
    with pytest.raises(ledger.WorkflowError):
        ledger.reserve_metadata_copy(job_id, RELEASE2, "b" * 64)


def test_secure_mode_never_starts_inferred_metadata_handoff(rig):
    rig[1]["mode"] = "secure"
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    go.advance(job_id, lookup=lambda disc, toc: {"releases": [{"id": RELEASE1}]})
    with pytest.raises(ledger.WorkflowError):
        ledger.reserve_metadata_copy(job_id, RELEASE1, "a" * 64)
    assert not list(rig[0].rglob("metadata-copy-*"))


def test_metadata_handoff_interrupted_or_failed_never_retries(rig):
    rig[1]["mode"] = "semi_automatic"
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    go.advance(job_id, lookup=lambda disc, toc: {"releases": [{"id": RELEASE1}]})
    ledger.accept_semi_release(job_id, RELEASE1, "ACCEPT_INFERRED_RELEASE")
    calls, adapters = _fake_metadata_flow(job_id, RELEASE1)
    started = go.advance(job_id, **adapters)
    assert started["action"] == "metadata_copy_running"
    # Emulate lost async process after restart, with its durable reservation intact.
    adapters["metadata_copy_status"] = lambda job, copy: (_ for _ in ()).throw(
        go.metadata_staging.MetadataError("no complete manifest"))
    failed = go.advance(job_id, **adapters)
    assert failed["action"] == "metadata_review_required"
    assert failed["workflow"]["phase"] == "METADATA_REVIEW_REQUIRED"
    assert failed["copy_id"] == started["copy_id"]
    assert go.advance(job_id, **adapters)["action"] == "metadata_review_required"
    assert sum(item[0] == "start" for item in calls) == 1
    assert not list(rig[0].rglob("metadata-copy-*"))


def test_bad_tagged_copy_inspection_requires_review(rig):
    rig[1]["mode"] = "semi_automatic"
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    go.advance(job_id, lookup=lambda disc, toc: {"releases": [{"id": RELEASE1}]})
    ledger.accept_semi_release(job_id, RELEASE1, "ACCEPT_INFERRED_RELEASE")
    calls, adapters = _fake_metadata_flow(job_id, RELEASE1)
    go.advance(job_id, **adapters)
    adapters["metadata_copy_inspect"] = lambda job, copy: {
        "release_id": RELEASE1, "status": "review_required"}
    result = go.advance(job_id, **adapters)
    assert result["action"] == "metadata_review_required"
    assert result["workflow"]["phase"] == "METADATA_REVIEW_REQUIRED"


def test_go_metadata_preview_failure_never_reserves_copy(rig):
    rig[1]["mode"] = "semi_automatic"
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    go.advance(job_id, lookup=lambda disc, toc: {"releases": [{"id": RELEASE1}]})
    ledger.accept_semi_release(job_id, RELEASE1, "ACCEPT_INFERRED_RELEASE")
    error = go.advance(job_id, metadata_preview=lambda job, release: (_ for _ in ()).throw(
        go.metadata_staging.MetadataError("ambiguous medium")))
    assert error["action"] == "metadata_review_required"
    state = ledger.refresh(job_id)
    assert state["phase"] == "RELEASE_ACCEPTED"
    assert state["metadata_copy_id"] == ""


def _prepare_verified_go_archive(rig, monkeypatch, mode="semi_automatic"):
    from oscar import metadata_staging
    rig[1]["mode"] = mode
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    go.advance(job_id, lookup=lambda disc, toc: {"releases": [{"id": RELEASE1}]})
    if mode == "semi_automatic":
        ledger.accept_semi_release(job_id, RELEASE1, "ACCEPT_INFERRED_RELEASE")
    calls, adapters = _fake_metadata_flow(job_id, RELEASE1)
    go.advance(job_id, **adapters)
    go.advance(job_id, **adapters)
    state = ledger.refresh(job_id)
    assert state["phase"] == "METADATA_READY"
    monkeypatch.setattr(metadata_staging, "inspect_copy", lambda job, copy: {
        "status": "tags_match_preview", "release_id": RELEASE1})
    return job_id, state["metadata_copy_id"]


def _fake_go_archive_plan(job_id, copy_id):
    return {"job_id": job_id, "copy_id": copy_id, "release_id": RELEASE1,
            "fingerprint": "a" * 64, "relative_directory": "Boulez/Stravinsky",
            "output_exists": False, "metadata_observations": [],
            "album": {"title": "Stravinsky", "artist": "Boulez"}, "disc_number": 1,
            "disc_total": 1, "profile": "classical", "kind": "original_tags",
            "provenance": {"recovery": None, "metadata_source": "MusicBrainz",
                           "verification_method": "cyanrip", "accuraterip_coverage": None},
            "tracks": [], "source_evidence": [], "include_cover": False}


def test_go_archive_preview_only_after_verified_copy(rig, monkeypatch):
    job_id = _finish(rig)
    rig[2]["status"] = "checks_passed"
    with pytest.raises(go.GoError, match="METADATA_READY"):
        go.archive_preview(job_id)
    # The shared fixture tracks verification callbacks for each mocked rip.
    # Reset its list before starting the independent verified-copy scenario.
    rig[3].clear()
    prepared_job, copy = _prepare_verified_go_archive(rig, monkeypatch)
    review = lambda *a, **kw: {"release_id": RELEASE1, "tracks": [
        {"number": 1, "work_ids": ["work-1"], "conductor": ["Boulez"]}]}
    preview = go.archive_preview(
        prepared_job, review=review,
        prepare=lambda *a, **kw: _fake_go_archive_plan(prepared_job, copy))
    assert preview["can_publish"]
    assert preview["requires_operator_confirmation"]
    assert preview["archive_review"]["tracks"][0]["work_ids"] == ["work-1"]
    assert preview["release_match_status"] == "INFERRED_OPERATOR_ACCEPTED"
    assert "Physical edition status: INFERRED_OPERATOR_ACCEPTED" in preview["sources_preview"]


def test_go_archive_publish_confirmation_fingerprint_and_source(rig, monkeypatch):
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    plan = _fake_go_archive_plan(job_id, copy)
    launched = []
    def publish(*args, **kwargs):
        launched.append((args, kwargs))
        return {"publish_id": kwargs["reserved_publish_id"], "status": "running"}
    adapter = lambda *a, **kw: plan
    with pytest.raises(go.GoError, match="confirmation"):
        go.archive_publish_start(job_id, "a"*64, "NOT_APPROVED",
                                 prepare=adapter, start=publish)
    with pytest.raises(go.GoError, match="changed"):
        go.archive_publish_start(job_id, "b"*64, "PUBLISH_REVIEWED_ARCHIVE",
                                 prepare=adapter, start=publish)
    assert not launched
    result = go.archive_publish_start(
        job_id, "a"*64, "PUBLISH_REVIEWED_ARCHIVE",
        prepare=adapter, start=publish)
    assert len(launched) == 1
    assert launched[0][0][1] == copy
    assert result["release_match_status"] == "INFERRED_OPERATOR_ACCEPTED"


def test_go_archive_publish_observations_and_existing_destination_block(rig, monkeypatch):
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    plan = _fake_go_archive_plan(job_id, copy)
    plan["metadata_observations"] = [{"code": "missing_classical_work_link"}]
    launched = []
    publisher = lambda *a, **kw: launched.append((a,kw))
    with pytest.raises(go.GoError, match="acknowledgement"):
        go.archive_publish_start(job_id, "a"*64, "PUBLISH_REVIEWED_ARCHIVE",
                                 prepare=lambda *a, **kw: plan, start=publisher)
    plan["output_exists"] = True
    with pytest.raises(go.GoError, match="exists"):
        go.archive_publish_start(job_id, "a"*64, "PUBLISH_REVIEWED_ARCHIVE",
                                 acknowledge_observations=True,
                                 prepare=lambda *a, **kw: plan, start=publisher)
    assert not launched


def test_go_archive_publisher_rejects_wrong_release_and_inspection(rig, monkeypatch):
    from oscar import metadata_staging
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    wrong = _fake_go_archive_plan(job_id, copy)
    wrong["release_id"] = RELEASE2
    with pytest.raises(go.GoError, match="differs"):
        go.archive_preview(job_id,
            review=lambda *a, **kw: {"release_id": RELEASE1},
            prepare=lambda *a, **kw: wrong)
    monkeypatch.setattr(metadata_staging, "inspect_copy", lambda *a: {
        "status": "review_required", "release_id": RELEASE1})
    with pytest.raises(go.GoError, match="no longer matches"):
        go.archive_publish_start(job_id, "a"*64, "PUBLISH_REVIEWED_ARCHIVE")


def test_go_archive_endpoints_require_auth(rig):
    client = TestClient(app)
    job_id = "f" * 32
    assert client.post(f"/api/go/jobs/{job_id}/archive/preview").status_code == 403
    assert client.post(f"/api/go/jobs/{job_id}/archive/publish",
        json={"fingerprint": "a"*64,
              "confirmation": "PUBLISH_REVIEWED_ARCHIVE"}).status_code == 403


def test_durable_archive_manual_reservation_rejects_second_worker(rig, monkeypatch):
    from oscar import archive_publish
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    plan = _fake_go_archive_plan(job_id, copy)
    launched = []
    def start(*args, **kwargs):
        launched.append(kwargs["reserved_publish_id"])
        return {"publish_id": kwargs["reserved_publish_id"], "status": "running"}
    first = go.archive_publish_start(
        job_id, "a"*64, "PUBLISH_REVIEWED_ARCHIVE",
        prepare=lambda *a, **kw: plan, start=start)
    assert first["workflow"]["phase"] == "ARCHIVE_PUBLISH_RUNNING"
    assert first["result"]["publish_id"] == launched[0]
    assert len(launched) == 1
    assert ledger.refresh(job_id)["archive_publish_id"] == launched[0]
    with pytest.raises(go.GoError, match="METADATA_READY"):
        go.archive_publish_start(job_id, "a"*64, "PUBLISH_REVIEWED_ARCHIVE",
                                 prepare=lambda *a, **kw: plan, start=start)
    assert len(launched) == 1
    with pytest.raises(ledger.WorkflowError, match="already reserved"):
        ledger.reserve_archive_publish(
            job_id, copy, RELEASE1, "a"*64, plan["relative_directory"])


def test_archive_reconciliation_recovers_manifest_after_worker_restart(rig, monkeypatch):
    from oscar import archive_publish
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    planned = _fake_go_archive_plan(job_id, copy)
    reserved = ledger.reserve_archive_publish(
        job_id, copy, RELEASE1, "a"*64, planned["relative_directory"])
    pid = reserved["archive_publish_id"]
    # The old worker's in-memory status is unavailable after process restart.
    def missing(*a):
        raise archive_publish.PublishError("worker state lost")
    validated = {"status": "published_verified", "job_id": job_id, "copy_id": copy}
    monkeypatch.setattr(archive_publish, "archive_root",
                        lambda: rig[0])
    monkeypatch.setattr(
        __import__("oscar.collection_catalog", fromlist=["import_published"]),
        "import_published", lambda **kw: {"imported": 1, "indexed": True})
    done = go.reconcile_archive(job_id, publish_status=missing,
                               manifest_reader=lambda *a: validated)
    assert done["action"] == "archive_published"
    assert done["workflow"]["phase"] == "ARCHIVE_PUBLISHED"
    assert done["workflow"]["archive_catalog_status"] == "indexed"
    assert go.reconcile_archive(job_id)["action"] == "archive_published"


def test_archive_lost_worker_without_manifest_stops_permanently(rig, monkeypatch):
    from oscar import archive_publish
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    reserved = ledger.reserve_archive_publish(
        job_id, copy, RELEASE1, "a"*64, "Artist/Album/Disc 01")
    result = go.reconcile_archive(
        job_id,
        publish_status=lambda *a: (_ for _ in ()).throw(
            archive_publish.PublishError("no worker")),
        manifest_reader=lambda *a: None)
    assert result["action"] == "archive_review_required"
    assert ledger.refresh(job_id)["archive_publish_id"] == reserved["archive_publish_id"]
    assert go.reconcile_archive(job_id)["action"] == "archive_review_required"


def test_best_guess_autopublish_requires_explicit_optin_and_unique_candidate(rig, monkeypatch):
    from oscar import archive_publish
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch, mode="best_guess")
    plan = _fake_go_archive_plan(job_id, copy)
    monkeypatch.setattr(archive_publish, "prepare", lambda *a, **kw: plan)
    calls = []
    def starter(*args, **kwargs):
        calls.append(kwargs)
        return {"publish_id": kwargs["reserved_publish_id"], "status": "running"}
    monkeypatch.setattr(archive_publish, "start", starter)
    assert go.advance(job_id)["action"] == "metadata_ready"
    assert not calls
    monkeypatch.setenv("OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH", "1")
    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_PUBLISH", "1")
    start = go.advance(job_id)
    assert start["action"] == "archive_publish_running"
    assert start["workflow"]["phase"] == "ARCHIVE_PUBLISH_RUNNING"
    assert start["release_match_status"] == "INFERRED_NOT_PHYSICALLY_VERIFIED"
    assert calls[0]["include_cover"] is False
    assert calls[0]["acknowledge_observations"] is False
    assert calls[0]["reserved_publish_id"] == start["publish_id"]


def test_best_guess_autopublish_warning_and_ambiguous_block(rig, monkeypatch):
    from oscar import archive_publish
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch, mode="best_guess")
    monkeypatch.setenv("OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH", "1")
    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_PUBLISH", "1")
    plan = _fake_go_archive_plan(job_id, copy)
    plan["metadata_observations"] = [{"code": "missing_work_relationship"}]
    monkeypatch.setattr(archive_publish, "prepare", lambda *a, **kw: plan)
    launched = []
    monkeypatch.setattr(archive_publish, "start", lambda *a, **kw: launched.append(a))
    assert go.advance(job_id)["action"] == "archive_review_required"
    assert not launched
    plan["metadata_observations"] = []
    with ledger._db() as db:
        db.execute("UPDATE workflow_jobs SET release_evidence='inferred_disc_id_ranked' WHERE job_id=?",
                   (job_id,))
    assert go.advance(job_id)["action"] == "archive_review_required"
    assert not launched
    assert ledger.refresh(job_id)["archive_publish_id"] == ""


def test_secure_cannot_reserve_inferred_archive(rig, monkeypatch):
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    with ledger._db() as db:
        db.execute("UPDATE workflow_jobs SET identification_mode='secure' WHERE job_id=?",
                   (job_id,))
    with pytest.raises(ledger.WorkflowError, match="Secure"):
        ledger.reserve_archive_publish(job_id, copy, RELEASE1, "a"*64, "Artist/Album")


def test_reconciler_requires_exact_persisted_manifest_and_every_flac_hash(rig, monkeypatch):
    import hashlib
    from oscar import archive_publish
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    relative = "Artist/Album/Disc 01"
    reserved = ledger.reserve_archive_publish(
        job_id, copy, RELEASE1, "a"*64, relative)
    dest = rig[0] / relative
    dest.mkdir(parents=True)
    file = dest / "01.flac"
    file.write_bytes(b"verified archive content")
    sha = hashlib.sha256(file.read_bytes()).hexdigest()
    manifest = {"status": "published_verified",
                "publish_id": reserved["archive_publish_id"],
                "job_id": job_id, "copy_id": copy,
                "release_id": RELEASE1,
                "archive_plan_fingerprint": "a"*64,
                "files": [{"filename": "01.flac", "sha256": sha}]}
    (dest / "manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(archive_publish, "archive_root", lambda: rig[0])
    assert go._read_published_archive(job_id, reserved) == manifest
    file.write_bytes(b"tampered content")
    assert go._read_published_archive(job_id, reserved) is None
    file.write_bytes(b"verified archive content")
    manifest["publish_id"] = "f"*32
    (dest / "manifest.json").write_text(json.dumps(manifest))
    assert go._read_published_archive(job_id, reserved) is None


def test_reconciler_refuses_symlinked_archive_parent(rig, monkeypatch, tmp_path):
    import hashlib
    from oscar import archive_publish
    job_id, copy = _prepare_verified_go_archive(rig, monkeypatch)
    reserved = ledger.reserve_archive_publish(
        job_id, copy, RELEASE1, "a"*64, "Linked/Album")
    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "Album").mkdir(parents=True)
    (rig[0] / "Linked").symlink_to(elsewhere, target_is_directory=True)
    monkeypatch.setattr(archive_publish, "archive_root", lambda: rig[0])
    assert go._read_published_archive(job_id, reserved) is None


def test_new_oscar_navigation_preserves_advanced_tools_and_auth_endpoints():
    """PR71 changes layout only: all original safe review APIs remain reachable."""
    html = TestClient(app).get("/").text
    for name in ("go", "review", "collection", "settings"):
        assert f"['{name}'," in html
    assert "panel-'+name" in html
    assert "tab-'+name" in html
    for marker in (
        "go-drive-cards", "go-workflows", "go-refresh-drives",
        "review-jobs", "review-refresh", "oscar-advanced",
        "go-job", "go-advance", "go-start",
        "workflow-register", "verify-start",
        "metadata-preview-btn", "physical-compare-btn",
        "collection-import", "discogs-check",
        "profile", "identification-mode", "drives", "save",
    ):
        assert marker in html
    assert "startGoForDrive" in html
    assert "refreshGoCards" in html
    assert "refreshReviewQueue" in html
    assert "Only explicit actions change metadata" in html
    assert "no archive publication" not in html.lower().split("<script>")[0][-120:]


def test_oscar_inline_javascript_syntax_if_node_available():
    """Catch broken UI scripts without making Node a runtime dependency."""
    import shutil
    import subprocess
    import re
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is not installed in this test environment")
    html = TestClient(app).get("/").text
    scripts = re.findall(r"<script(?: [^>]*)?>(.*?)</script>", html, flags=re.S)
    assert scripts
    for script in scripts:
        result = subprocess.run([node, "--check", "--input-type=commonjs"],
                                input=script, capture_output=True, text=True,
                                timeout=15, check=False)
        assert result.returncode == 0, result.stderr


def test_review_reverify_uses_existing_auth_protected_verification_api():
    """Review reuses the existing explicit verification API, never starts another rip."""
    html = TestClient(app).get("/").text
    assert "Reverify saved rip" in html
    assert "verifyExistingJob(job.job_id,status)" in html
    assert "if(job.phase==='VERIFICATION_PENDING')" in html
    assert "The prior verification report is backed up" in html
    assert "/api/rip/jobs/'+job+'/verification" in html
    assert "window.confirm('Reverify this saved rip" in html


def test_discid_attach_link_uses_saved_toc_and_never_submits_edit(tmp_path, monkeypatch):
    """Only an accepted, verified single CD gets a link to MusicBrainz' own editor."""
    from oscar import boxsets
    directory = tmp_path / ("oscar-" + "a" * 32)
    directory.mkdir()
    (directory / "plan.json").write_text(json.dumps({
        "disc_id": DISC, "toc_string": "1 2 1000 150 300"}))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.setattr(ledger, "refresh", lambda job_id: {
        "identification_mode": "semi_automatic",
        "accepted_release_id": RELEASE1,
        "release_match_status": "INFERRED_OPERATOR_ACCEPTED"})
    monkeypatch.setattr(verification, "_safe_job", lambda job_id: directory)
    monkeypatch.setattr(verification, "_load_job", lambda folder, job_id: {"disc_id": DISC})
    monkeypatch.setattr(verification, "report", lambda job_id: {
        "status": "checks_passed", "job_id": job_id, "expected_tracks": 2,
        "tracks": [{"checks_passed": True}, {"checks_passed": True}]})
    from oscar import api
    monkeypatch.setattr(api, "lookup_release_medium", lambda *args: None, raising=False)
    monkeypatch.setattr(boxsets, "lookup_release_medium", lambda *args: {
        "status": "no_exact_medium_match", "total_media": 1,
        "all_media": [{"format": "CD", "position": 1, "track_count": 2,
                       "disc_id_attached": False}]})
    response = TestClient(app).get(
        "/api/go/jobs/" + "a" * 32 + "/musicbrainz/discid-attach",
        headers={"X-OSCAR-RIP-TOKEN": TOKEN})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "human_submission_required"
    assert "toc=1+2+1000+150+300" in data["musicbrainz_attach_url"]
    assert "filter-release.query=" + RELEASE1 in data["musicbrainz_attach_url"]
    assert data["release_id"] == RELEASE1
    assert "will not submit" in data["warning"].lower()
    assert "Add missing Disc ID to MusicBrainz" in TestClient(app).get("/").text


def test_discid_attach_link_rejects_unaccepted_or_ambiguous_job(tmp_path, monkeypatch):
    from oscar import boxsets
    directory = tmp_path / ("oscar-" + "a" * 32)
    directory.mkdir()
    (directory / "plan.json").write_text(json.dumps({
        "disc_id": DISC, "toc_string": "1 2 1000 150 300"}))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    accepted = {"identification_mode": "semi_automatic",
                "accepted_release_id": "",
                "release_match_status": "INFERRED_NOT_PHYSICALLY_VERIFIED"}
    monkeypatch.setattr(ledger, "refresh", lambda job_id: accepted)
    monkeypatch.setattr(verification, "_safe_job", lambda job_id: directory)
    monkeypatch.setattr(verification, "_load_job", lambda folder, job_id: {"disc_id": DISC})
    monkeypatch.setattr(verification, "report", lambda job_id: {
        "status": "checks_passed", "job_id": job_id, "expected_tracks": 2,
        "tracks": [{"checks_passed": True}, {"checks_passed": True}]})
    client = TestClient(app)
    url = "/api/go/jobs/" + "a" * 32 + "/musicbrainz/discid-attach"
    headers = {"X-OSCAR-RIP-TOKEN": TOKEN}
    assert client.get(url, headers=headers).status_code == 409
    accepted["accepted_release_id"] = RELEASE1
    accepted["release_match_status"] = "INFERRED_OPERATOR_ACCEPTED"
    monkeypatch.setattr(boxsets, "lookup_release_medium", lambda *args: {
        "status": "no_exact_medium_match", "total_media": 2,
        "all_media": [{"format": "CD", "position": 1, "track_count": 2}]})
    assert client.get(url, headers=headers).status_code == 409
