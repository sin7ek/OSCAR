"""Persistent, no-write OSCAR orchestration ledger tests."""
import json

import pytest
from fastapi.testclient import TestClient

from oscar import workflow_ledger as ledger
from oscar.settings import OscarSettings
from oscar.api import app

JOB = "f41806152a614b1a9006b10456b9bbd4"


@pytest.fixture
def saved(tmp_path, monkeypatch):
    root=tmp_path/"staging"
    root.mkdir()
    job=root/("oscar-"+JOB)
    job.mkdir()
    state={"id":JOB,"status":"needs_verification","returncode":0,
           "disc_id":"ROkQlooU5tDdgVZOkfXXTy.S4oU-"}
    (job/"state.json").write_text(json.dumps(state))
    folder=tmp_path/"config"
    folder.mkdir()
    monkeypatch.setenv("OSCAR_RIP_ROOT",str(root))
    monkeypatch.setenv("OSCAR_WORKFLOW_DB",str(folder/"workflow.sqlite3"))
    monkeypatch.setattr(ledger.verification,"report",
                        lambda job_id: {"job_id":job_id,"status":"checks_passed"})
    monkeypatch.setattr(ledger,"discover_settings",
                        lambda:OscarSettings(identification_mode="best_guess",
                                             secure_review_level="before_archive"))
    return job


def test_registration_snapshots_mode_and_does_not_touch_staging(saved,monkeypatch):
    original=(saved/"state.json").read_bytes()
    result=ledger.register(JOB)
    assert result["phase"]=="RELEASE_REVIEW_PENDING"
    assert result["identification_mode"]=="best_guess"
    assert result["secure_review_level"]=="before_archive"
    assert not result["automated_actions_enabled"]
    assert len(result["events"])==1
    monkeypatch.setattr(ledger,"discover_settings",
                        lambda:OscarSettings(identification_mode="secure"))
    again=ledger.register(JOB)
    assert again["identification_mode"]=="best_guess"
    assert len(again["events"])==1
    assert (saved/"state.json").read_bytes()==original


def test_defer_resume_is_idempotent_and_persisted(saved):
    ledger.register(JOB)
    first=ledger.review_action(JOB,"defer")
    assert first["phase"]=="DEFERRED_REVIEW"
    second=ledger.review_action(JOB,"defer")
    assert len(second["events"])==2
    assert ledger.refresh(JOB)["phase"]=="DEFERRED_REVIEW"
    result=ledger.review_action(JOB,"resume")
    assert result["phase"]=="RELEASE_REVIEW_PENDING"
    assert len(result["events"])==3
    assert ledger.list_jobs()["jobs"][0]["phase"]=="RELEASE_REVIEW_PENDING"


def test_verification_pending_only_advances_on_actual_saved_evidence(saved,monkeypatch):
    monkeypatch.setattr(ledger.verification,"report",
                        lambda job_id: {"job_id":job_id,"status":"review_required"})
    assert ledger.register(JOB)["phase"]=="VERIFICATION_PENDING"
    assert ledger.refresh(JOB)["phase"]=="VERIFICATION_PENDING"
    monkeypatch.setattr(ledger.verification,"report",
                        lambda job_id: {"job_id":job_id,"status":"checks_passed"})
    assert ledger.refresh(JOB)["phase"]=="RELEASE_REVIEW_PENDING"


def test_unknown_workflow_cannot_be_advanced(saved):
    with pytest.raises(ledger.WorkflowError):
        ledger.review_action(JOB,"defer")
    with pytest.raises(ledger.WorkflowError):
        ledger.register("not-an-id")
    with pytest.raises(ledger.WorkflowError):
        ledger.review_action(JOB,"publish")
    assert not list(saved.glob("metadata-copy-*"))


def test_workflow_tracking_ui_only_states_supported_capabilities():
    html=TestClient(app).get("/").text
    assert "Persistent workflow ledger" in html
    assert "Go! jobs are registered automatically; use this form only for manual recovery" in html
    assert "workflow-register" in html
