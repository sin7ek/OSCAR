"""Pre-publication refreshed-copy adoption — deliberate, durable, never in-place."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from oscar import metadata_reprocess as rp
from oscar import workflow_ledger as wl
from oscar.api import app

JOB = "e4ca0a116f744e0799d2dbf04161f6f1"
OLD = "a" * 32
NEW = "b" * 32
REL = "f0a7ab08-1111-2222-3333-444444444444"
FINGERPRINT = "e" * 64
TOKEN = "0123456789abcdef0123456789abcdef"
TRACK = "audio/01 - Symphony.flac"
HASH = "d" * 64


@pytest.fixture
def adopted(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("OSCAR_WORKFLOW_DB", str(config / "workflow.sqlite3"))
    root = tmp_path / JOB
    root.mkdir()
    for copy in (OLD, NEW):
        (root / ("metadata-copy-" + copy)).mkdir()
    monkeypatch.setattr(rp.verification if hasattr(rp, "verification") else
                        __import__("oscar.verification", fromlist=["x"]),
                        "_safe_job", lambda job: root)
    old = {
        "job_id": JOB, "release_id": REL, "fingerprint": "c" * 64,
        "album": {"musicbrainz_release_id": REL, "musicbrainz_disc_id": "x" * 28,
                  "catalog_numbers": ["002894778668"]},
        "tracks": [{"number": 1, "original_file": TRACK,
                    "tags": {"MUSICBRAINZ_ALBUMID": REL,
                             "MUSICBRAINZ_DISCID": "x" * 28,
                             "DISCNUMBER": "2", "TRACKNUMBER": "1",
                             "TRACKTOTAL": "1", "DISCTOTAL": "11",
                             "CATALOGNUMBER": ["002894778668"]}}],
    }
    new = json.loads(json.dumps(old))
    new["fingerprint"] = FINGERPRINT
    new["album"]["catalog_numbers"] = ["002894778668", "477 8668"]
    new["tracks"][0]["tags"]["CATALOGNUMBER"] = ["002894778668", "477 8668"]
    for copy, preview in [(OLD, old), (NEW, new)]:
        folder = root / ("metadata-copy-" + copy)
        (folder / "metadata-preview.json").write_text(json.dumps(preview))
        (folder / "metadata-manifest.json").write_text(json.dumps({
            "status": "tagged_copy_ready_for_review", "job_id": JOB,
            "copy_id": copy, "release_id": REL,
            "preview_fingerprint": preview["fingerprint"],
            "identification_status": "INFERRED_OPERATOR_ACCEPTED",
            "files": {TRACK: {"source_sha256": HASH}},
        }))
    def inspect(job, copy):
        return {"status": "tags_match_preview", "release_id": REL,
                "track_count": 1, "tracks": [{
                    "sha256_matches": True, "audio_streaminfo_md5_matches": True,
                    "tags_match": True}]}
    monkeypatch.setattr(rp.metadata_staging, "inspect_copy", inspect)
    monkeypatch.setattr(rp.metadata_staging, "_source",
                        lambda job: (root, {"files_sha256": {TRACK: HASH}}, {}))
    now = wl._now()
    with wl._db() as db:
        db.execute("""INSERT INTO workflow_jobs
            (job_id,identification_mode,secure_review_level,phase,created_at,
             updated_at,accepted_release_id,metadata_release_id,metadata_copy_id,
             metadata_fingerprint) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (JOB, "semi_automatic", "on_ambiguity", "METADATA_READY",
             now, now, REL, REL, OLD, old["fingerprint"]))
    monkeypatch.setattr(wl, "refresh", lambda job: wl._view(wl._db(), job))
    return root


def test_selects_new_copy_atomically_preserving_existing_staging(adopted):
    before = {str(p): p.read_bytes() for p in adopted.rglob("*.json")}
    result = rp.adopt_new_staging_copy_for_go(
        JOB, NEW, FINGERPRINT, "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")
    assert result["active_copy_id"] == NEW
    assert result["new_archive_publication"] is False
    with wl._db() as db:
        item = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (JOB,)).fetchone()
        assert item["phase"] == "METADATA_READY"
        assert item["metadata_copy_id"] == NEW
        assert item["metadata_fingerprint"] == FINGERPRINT
        assert item["archive_publish_id"] == ""
        events = [x["reason"] for x in db.execute("SELECT * FROM workflow_events")]
        assert any("operator_adopted_refreshed_copy" in event for event in events)
    assert {str(p): p.read_bytes() for p in adopted.rglob("*.json")} == before
    with pytest.raises(rp.ReprocessError, match="already the active"):
        rp.adopt_new_staging_copy_for_go(JOB, NEW, FINGERPRINT,
                                         "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")


def test_refuses_reserved_archive_even_when_phase_ready(adopted):
    with wl._db() as db:
        db.execute("UPDATE workflow_jobs SET archive_publish_id=? WHERE job_id=?",
                   ("f" * 32, JOB))
    with pytest.raises(rp.ReprocessError, match="unpublished"):
        rp.adopt_new_staging_copy_for_go(
            JOB, NEW, FINGERPRINT, "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")
    with wl._db() as db:
        assert db.execute("SELECT metadata_copy_id FROM workflow_jobs").fetchone()[0] == OLD


def test_refuses_unverified_copy_or_disc_identity_change(adopted, monkeypatch):
    monkeypatch.setattr(rp.metadata_staging, "inspect_copy",
                        lambda job, copy: {"status": "review_required"})
    with pytest.raises(rp.ReprocessError, match="integrity"):
        rp.adopt_new_staging_copy_for_go(
            JOB, NEW, FINGERPRINT, "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")
    monkeypatch.setattr(rp.metadata_staging, "inspect_copy",
                        lambda job, copy: {"status": "tags_match_preview", "release_id": REL,
                                           "track_count": 1,
                                           "tracks": [{"sha256_matches": True,
                                                      "audio_streaminfo_md5_matches": True,
                                                      "tags_match": True}]})
    saved = adopted / ("metadata-copy-" + NEW) / "metadata-preview.json"
    value = json.loads(saved.read_text())
    value["tracks"][0]["tags"]["DISCNUMBER"] = "5"
    saved.write_text(json.dumps(value))
    with pytest.raises(rp.ReprocessError, match="disc/track identity"):
        rp.adopt_new_staging_copy_for_go(
            JOB, NEW, FINGERPRINT, "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")


def test_refuses_modified_source_evidence_and_wrong_fingerprint(adopted):
    with pytest.raises(rp.ReprocessError, match="fingerprint"):
        rp.adopt_new_staging_copy_for_go(
            JOB, NEW, "f" * 64, "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")
    path = adopted / ("metadata-copy-" + NEW) / "metadata-manifest.json"
    obj = json.loads(path.read_text())
    obj["files"][TRACK]["source_sha256"] = "0" * 64
    path.write_text(json.dumps(obj))
    with pytest.raises(rp.ReprocessError, match="original rip hashes"):
        rp.adopt_new_staging_copy_for_go(
            JOB, NEW, FINGERPRINT, "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")


def test_ledger_refuses_stale_old_id_and_mode(adopted):
    with pytest.raises(wl.WorkflowError, match="changed"):
        wl.adopt_refreshed_metadata_copy(
            JOB, "9" * 32, NEW, REL, FINGERPRINT,
            "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")
    with wl._db() as db:
        db.execute("UPDATE workflow_jobs SET identification_mode='best_guess'")
    with pytest.raises(wl.WorkflowError, match="Semi Automatic"):
        wl.adopt_refreshed_metadata_copy(
            JOB, OLD, NEW, REL, FINGERPRINT,
            "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION")


def test_endpoint_requires_token_and_ui_uses_strict_confirmation(monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    path = "/api/go/jobs/" + JOB + "/musicbrainz/adopt-refreshed-copy"
    body = {"copy_id": NEW, "fingerprint": FINGERPRINT,
            "confirmation": "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION"}
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, json={**body, "copy_id": "invalid"},
                       headers={"X-OSCAR-RIP-TOKEN": TOKEN}).status_code == 422
    html = client.get("/").text
    assert "Use verified refreshed copy for FIRST Go publication" in html
