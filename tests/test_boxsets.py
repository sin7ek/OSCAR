"""Regression tests for exact medium matching in multi-disc MusicBrainz releases."""
import json

import pytest
from fastapi.testclient import TestClient

from oscar import boxsets
from oscar.api import app


DISC_ID = "sT6cTPp0_qZRfvu1jHQ8VBNx.X4-"
RELEASE_ID = "423f636d-742d-47b0-9ba2-51515a6fdfd2"


def fixture():
    return {
        "id": RELEASE_ID, "title": "Boulez Conducts Stravinsky",
        "media": [
            {"position": 1, "title": "Orchestral works", "format": "CD",
             "track-count": 9, "discs": [{"id": "OtherDiscId_000000000000000000"}],
             "tracks": []},
            {"position": 6, "title": "Songs", "format": "CD",
             "track-count": 32, "discs": [{"id": DISC_ID}],
             "tracks": [
                {"number": "1", "position": 1, "title": "Song 1",
                 "artist-credit": [{"name": "Soloist"}, {"name": "Ensemble", "joinphrase": ""}],
                 "recording": {"id": "some-recording-id", "title": "Recording"}},
                {"number": "2", "position": 2, "recording": {"title": "Song 2"}}
             ]}
        ]
    }


def test_exact_sixth_disc():
    result = boxsets.parse_release_media(fixture(), DISC_ID, 32)
    assert result["status"] == "exact_disc_id_and_track_count"
    assert result["total_media"] == 2  # Only 2 fixture media
    assert len(result["matched_media"]) == 1
    assert result["matched_media"][0]["position"] == 6
    assert result["matched_media"][0]["tracks"][0]["title"] == "Song 1"
    assert result["requires_review"]


def test_unknown_disc_not_guessed_by_track_count():
    result = boxsets.parse_release_media(fixture(), "DifferentDiscID012345678901234", 32)
    assert result["status"] == "no_exact_medium_match"
    assert result["matched_media"] == []


def test_count_mismatch_not_approved():
    result = boxsets.parse_release_media(fixture(), DISC_ID, 31)
    assert result["status"] == "review_disc_id_or_count_ambiguity"
    assert not result["matched_media"][0]["track_count_matches"]


class Response:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return json.dumps(fixture()).encode()


def test_release_lookup_validates_and_preserves_disc(monkeypatch):
    import oscar.musicbrainz as mb
    monkeypatch.setattr(mb.time, "monotonic", lambda: 123456.0)
    monkeypatch.setattr(mb.time, "sleep", lambda seconds: None)
    result = boxsets.lookup_release_medium(RELEASE_ID, DISC_ID, 32, opener=lambda req, timeout: Response())
    assert result["matched_media"][0]["position"] == 6
    assert result["status"] == "exact_disc_id_and_track_count"


def test_reject_invalid_release_id():
    with pytest.raises(Exception, match="Invalid release MBID"):
        boxsets.lookup_release_medium("../etc/passwd", DISC_ID, 32)


def test_page_displays_medium_inspector():
    assert "Inspect disc & tracklist" in TestClient(app).get("/").text


def test_medium_endpoint_respects_disabled_flag(monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_MUSICBRAINZ", raising=False)
    r = TestClient(app).get("/api/release-medium", params={"stable_id":"ata-Optiarc","release_id":RELEASE_ID})
    assert r.status_code == 403
