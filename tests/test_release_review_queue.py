"""Regression coverage for persistent deferred physical-release reviews."""
import json

import pytest
from fastapi.testclient import TestClient

from oscar import release_review_queue as queue
from oscar.api import app

JOB = "95dbf0da233d4a3887800a517a149b3c"


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    base = tmp_path / "staging"
    folder = base / ("oscar-" + JOB)
    folder.mkdir(parents=True)
    (folder / "state.json").write_text(json.dumps({"id": JOB}))
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(base))
    monkeypatch.setattr(queue.verification, "report",
                        lambda job: {"status": "checks_passed", "expected_tracks": 14})
    return tmp_path / "pending.sqlite3"


def test_missing_release_can_be_deferred_and_resumed(prepared):
    result = queue.defer(JOB, reason="missing_release", title="Essential Dance Traxx",
                         catalog_number="CCC 97001", notes="Wrong shared Disc ID candidate",
                         path=prepared)
    assert result["status"] == "pending"
    assert queue.pending(path=prepared)["items"][0]["job_id"] == JOB
    assert queue.pending(path=prepared)["items"][0]["notes"] == "Wrong shared Disc ID candidate"
    queue.defer(JOB, reason="wrong_edition", title="Essential Dance Traxx",
                catalog_number="CCC 97001", path=prepared)
    records = queue.pending(path=prepared)["items"]
    assert len(records) == 1
    assert records[0]["reason"] == "wrong_edition"
    assert queue.resolve(JOB, path=prepared)["status"] == "resolved"
    assert queue.pending(path=prepared)["items"] == []


def test_only_verified_rips_can_be_deferred(prepared, monkeypatch):
    monkeypatch.setattr(queue.verification, "report",
                        lambda job: {"status": "review_required"})
    with pytest.raises(queue.RecoveryError, match="pass staging verification"):
        queue.defer(JOB, reason="missing_release", path=prepared)


def test_invalid_reason_or_job_does_not_write(prepared):
    with pytest.raises(queue.RecoveryError, match="reason"):
        queue.defer(JOB, reason="automatically_approve", path=prepared)
    with pytest.raises(queue.RecoveryError, match="ID"):
        queue.defer("../", reason="missing_release", path=prepared)


def test_guidance_ui_and_save_list_endpoints_present():
    html = TestClient(app).get("/").text
    for key in ("recovery-reason", "recovery-defer", "recovery-list",
                "wrong_edition", "missing_release", "Mark review resolved"):
        assert key in html


def test_deferred_release_endpoints_require_auth(monkeypatch):
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    monkeypatch.delenv("OSCAR_RIP_TOKEN", raising=False)
    client = TestClient(app)
    assert client.get("/api/release-reviews").status_code == 403
    assert client.post(f"/api/rip/jobs/{JOB}/release-review/defer",
                       json={"reason": "missing_release"}).status_code == 403
