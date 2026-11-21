"""Read-only metadata diff and boxset integrity entry-point regression tests."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oscar import archive_revision_boxset_verify as verify
from oscar.api import app


class FakeTags:
    def __init__(self, fields):
        self.tags = fields


@pytest.fixture
def flac_pairs(monkeypatch):
    values = {}
    monkeypatch.setattr(verify, "FLAC", lambda filename: FakeTags(values[str(filename)]))
    return values


def test_only_approved_label_difference_is_allowed(flac_pairs, tmp_path):
    old, new = tmp_path / "old.flac", tmp_path / "new.flac"
    flac_pairs[str(old)] = {
        "ARTIST": ["Igor Stravinsky"], "WORK": ["Ebony Concerto"],
        "MUSICBRAINZ_TRACKID": ["record-1"], "LABEL": [],
    }
    flac_pairs[str(new)] = {
        "artist": ["Igor Stravinsky"], "work": ["Ebony Concerto"],
        "musicbrainz_trackid": ["record-1"], "label": ["Deutsche Grammophon"],
    }
    assert verify.compare_tags(old, new, ["Deutsche Grammophon"]) == {}


def test_unapproved_metadata_or_recording_change_fails(flac_pairs, tmp_path):
    old, new = tmp_path / "before.flac", tmp_path / "after.flac"
    flac_pairs[str(old)] = {
        "WORK": ["Ebony Concerto"], "MUSICBRAINZ_TRACKID": ["record-1"],
        "LABEL": [], "RECORDLABEL": [],
    }
    flac_pairs[str(new)] = {
        "WORK": ["Concertino"], "MUSICBRAINZ_TRACKID": ["record-2"],
        "LABEL": ["Deutsche Grammophon"], "RECORDLABEL": ["Deutsche Grammophon"],
    }
    differences = verify.compare_tags(old, new, ["Deutsche Grammophon"])
    assert set(differences) == {"WORK", "MUSICBRAINZ_TRACKID", "RECORDLABEL"}


def test_bad_approved_label_or_values_fail(flac_pairs, tmp_path):
    old, new = tmp_path / "old.flac", tmp_path / "new.flac"
    flac_pairs[str(old)] = {"LABEL": ["Wrong"], "CONDUCTOR": ["Pierre Boulez"]}
    flac_pairs[str(new)] = {"LABEL": ["Other"], "CONDUCTOR": ["Pierre Boulez"]}
    assert "LABEL" in verify.compare_tags(old, new, ["Deutsche Grammophon"])


def test_missing_history_or_unfinished_operation_is_rejected(monkeypatch):
    class Db:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): return self
        def fetchone(self): return {"status": "prepared", "entries_json": "[]"}
    monkeypatch.setattr(verify.group, "_db", lambda: Db())
    with pytest.raises(verify.group.BoxsetApplyError, match="Only completed"):
        verify.verify("a" * 32)


def test_integrity_endpoint_is_authenticated_and_ui_has_action(monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_TOKEN", "0123456789abcdef0123456789abcdef")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    assert client.post("/api/collection/archive-revisions/boxset-verify",
                       json={"operation_id": "a" * 32}).status_code == 403
    response = client.post("/api/collection/archive-revisions/boxset-verify",
        headers={"X-OSCAR-RIP-TOKEN": "0123456789abcdef0123456789abcdef"},
        json={"operation_id": "not-an-id"})
    assert response.status_code == 422
    assert "Verify original, audio, metadata and Collection" in client.get("/").text
