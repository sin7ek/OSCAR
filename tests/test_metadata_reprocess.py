"""Regression tests for safe metadata refresh and separate staging reprocessing."""
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from oscar import metadata_reprocess as reprocess
from oscar.api import app

JOB = "b68488f667cc492d8dd94f90717cdb28"
COPY = "9af8f01c736843ff8f53a1d7e8af2b56"
RELEASE = "fa89edc1-32f9-4290-8788-bbac2e366a46"
TOKEN = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def saved(tmp_path, monkeypatch):
    from oscar import verification
    root = tmp_path / JOB
    old = root / ("metadata-copy-" + COPY)
    old.mkdir(parents=True)
    workflow = {
        "phase": "ARCHIVE_PUBLISHED",
        "identification_mode": "semi_automatic",
        "release_match_status": "INFERRED_OPERATOR_ACCEPTED",
        "accepted_release_id": RELEASE,
        "metadata_release_id": RELEASE,
        "metadata_copy_id": COPY,
        "archive_publish_id": "3908eef79f114450b0a7eb76bec44926",
    }
    base = {
        "job_id": JOB, "release_id": RELEASE, "fingerprint": "a" * 64,
        "album": {"title": "Desire", "artist": "Carmen Gomes Inc.",
                  "date": "2010", "catalog_numbers": [], "labels": []},
        "tracks": [{"number": 1, "original_file": "audio/01 - Only You Can.flac",
                    "tags": {"TITLE": "Only You Can", "ALBUM": "Desire"}}],
    }
    (old / "metadata-preview.json").write_text(json.dumps(base))
    (old / "metadata-manifest.json").write_text(json.dumps({
        "job_id": JOB, "copy_id": COPY, "status": "tagged_copy_ready_for_review",
        "preview_fingerprint": "a" * 64,
    }))
    monkeypatch.setattr(reprocess.workflow_ledger, "refresh", lambda job: workflow)
    monkeypatch.setattr(verification, "_safe_job", lambda job: root)
    monkeypatch.setattr(reprocess.metadata_staging, "inspect_copy",
                        lambda job, copy: {"status": "tags_match_preview"})
    current = json.loads(json.dumps(base))
    current["fingerprint"] = "b" * 64
    current["album"]["catalog_numbers"] = ["CGi2010"]
    current["album"]["labels"] = [{"name": "Test Label", "catalog_number": "CGi2010"}]
    current["tracks"][0]["tags"]["CATALOGNUMBER"] = ["CGi2010"]
    monkeypatch.setattr(reprocess.metadata_staging, "preview",
                        lambda job, release, **kw: current)
    return root, workflow, base, current


def test_refresh_reports_catalog_change_without_mutating_old_copy(saved):
    root, workflow, old, current = saved
    before = {str(p): p.read_bytes() for p in root.rglob("*.json")}
    result = reprocess.refresh_preview(JOB)
    assert result["status"] == "changes_found"
    assert result["old_catalog_numbers"] == []
    assert result["new_catalog_numbers"] == ["CGi2010"]
    assert result["change_count"] >= 2
    assert any(x["field"] == "CATALOGNUMBER" and x["scope"] == "track"
               for x in result["changes"])
    assert result["historical_status"] == "INFERRED_OPERATOR_ACCEPTED"
    assert result["previous_copy_id"] == COPY
    assert {str(p): p.read_bytes() for p in root.rglob("*.json")} == before
    assert workflow["phase"] == "ARCHIVE_PUBLISHED"


def test_preview_unchanged_avoids_unnecessary_new_copy(saved, monkeypatch):
    _, _, old, _ = saved
    monkeypatch.setattr(reprocess.metadata_staging, "preview",
                        lambda job, release, **kw: old)
    assert reprocess.refresh_preview(JOB)["new_copy_allowed"] is False
    with pytest.raises(reprocess.ReprocessError, match="No new"):
        reprocess.create_new_staging_copy(JOB, old["fingerprint"],
                                         "REPROCESS_TO_NEW_STAGING_COPY")


def test_reprocess_requires_confirmation_and_fingerprint(saved, monkeypatch):
    calls = []
    monkeypatch.setattr(reprocess.metadata_staging, "start_copy",
                        lambda *args, **kwargs: calls.append((args, kwargs)) or
                        {"copy_id": "c" * 32, "job_id": JOB, "status": "running"})
    with pytest.raises(reprocess.ReprocessError, match="confirmation"):
        reprocess.create_new_staging_copy(JOB, "b" * 64, "bad")
    with pytest.raises(reprocess.ReprocessError, match="changed since preview"):
        reprocess.create_new_staging_copy(JOB, "c" * 64,
                                         "REPROCESS_TO_NEW_STAGING_COPY")
    assert not calls
    result = reprocess.create_new_staging_copy(
        JOB, "b" * 64, "REPROCESS_TO_NEW_STAGING_COPY")
    assert result["status"] == "running"
    assert result["previous_copy_id"] == COPY
    assert calls[0][0] == (JOB, RELEASE, "b" * 64, "COPY_TAGGED_TO_STAGING")
    assert calls[0][1]["identification_status"] == "INFERRED_OPERATOR_ACCEPTED"
    assert "no archive replacement" in result["note"]


def test_refuse_unaccepted_job_or_changed_track_source(saved, monkeypatch):
    _, workflow, _, current = saved
    workflow["accepted_release_id"] = ""
    with pytest.raises(reprocess.ReprocessError, match="accepted"):
        reprocess.refresh_preview(JOB)
    workflow["accepted_release_id"] = RELEASE
    current["tracks"][0]["original_file"] = "audio/another.flac"
    with pytest.raises(reprocess.ReprocessError, match="ordering"):
        reprocess.refresh_preview(JOB)


def test_refuse_unsafe_saved_copy_or_failed_readback(saved, monkeypatch):
    root, _, _, _ = saved
    monkeypatch.setattr(reprocess.metadata_staging, "inspect_copy",
                        lambda *args: {"status": "review_required"})
    with pytest.raises(reprocess.ReprocessError, match="integrity"):
        reprocess.refresh_preview(JOB)
    original = root / ("metadata-copy-" + COPY) / "metadata-preview.json"
    original.unlink()
    original.symlink_to(root / "other.json")
    with pytest.raises(reprocess.ReprocessError, match="unsafe"):
        reprocess.refresh_preview(JOB)


def test_refresh_api_authentication_and_gui(monkeypatch):
    import oscar.api as api
    monkeypatch.setenv("OSCAR_ENABLE_MUSICBRAINZ", "1")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    client = TestClient(app)
    assert client.post("/api/go/jobs/" + JOB + "/musicbrainz/metadata-refresh").status_code == 403
    assert client.post("/api/go/jobs/" + JOB + "/musicbrainz/reprocess-copy",
                       json={"fingerprint": "a" * 64,
                             "confirmation": "REPROCESS_TO_NEW_STAGING_COPY"}).status_code == 403
    monkeypatch.setattr(api, "musicbrainz_metadata_refresh", api.musicbrainz_metadata_refresh)
    page = client.get("/").text
    assert "Refresh metadata from MusicBrainz (compare, no writes)" in page
    assert "Create new reviewed staging copy (no archive replacement)" in page
