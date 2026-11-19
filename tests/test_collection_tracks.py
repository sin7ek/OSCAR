"""Metadata-provenant per-track archive catalog regression tests."""
import hashlib
import json
from pathlib import Path

import pytest

from oscar import collection_catalog as catalog
from oscar import collection_labels as labels
from oscar import collection_tracks as tracks

RELEASE = "bde012c4-e129-4db0-b840-6ed5918a0c0a"


@pytest.fixture
def album(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    folder = archive / "Composer" / "[DG 100] Collection (1999) [bde012c4]"
    folder.mkdir(parents=True)
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(archive))
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(settings / "catalog.sqlite3"))
    first, second = (folder / "01.flac", folder / "02.flac")
    first.write_bytes(b"first-flac-test")
    second.write_bytes(b"second-flac-test")
    manifest = {
        "status": "published_verified", "release_id": RELEASE,
        "files": [
            {"track":1,"filename":"01.flac","sha256":hashlib.sha256(first.read_bytes()).hexdigest()},
            {"track":2,"filename":"02.flac","sha256":hashlib.sha256(second.read_bytes()).hexdigest()},
        ],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    class FakeFLAC:
        def __init__(self, path):
            self.path = Path(path)
            data = {
                "01.flac": {
                    "TITLE": ["Prélude"], "TRACKNUMBER": ["1"],
                    "MUSICBRAINZ_ALBUMID": [RELEASE],
                    "MUSICBRAINZ_TRACKID": ["recording-01"],
                    "MUSICBRAINZ_RELEASETRACKID": ["release-track-01"],
                    "COMPOSER": ["Georg Friedrich Händel"],
                    "CONDUCTOR": ["Jordi Savall"],
                    "ORCHESTRA": ["Le Concert des Nations"],
                    "WORK": ["Water Music, HWV 348"],
                    "MUSICBRAINZ_WORKID": ["work-01"],
                    "PERFORMER": ["Jane Example (soprano)", "Soloist One (solo violin)"],
                },
                "02.flac": {
                    "TITLE": ["Air"], "TRACKNUMBER": ["2"],
                    "MUSICBRAINZ_ALBUMID": [RELEASE],
                    "WORK": ["Work One", "Work Two"],
                    "MUSICBRAINZ_WORKID": ["only-one-id"],
                    "PERFORMER": ["Jordi Savall (conductor)"],
                },
            }
            self.tags = data[self.path.name]
        def items(self):
            return self.tags.items()
        def get(self, key, default=None):
            return self.tags.get(key, default if default is not None else [])
    import mutagen.flac
    monkeypatch.setattr(mutagen.flac, "FLAC", FakeFLAC)
    return folder, first, second


def test_index_tracks_and_search_by_classical_identity(album):
    folder, first, second = album
    original = [p.read_bytes() for p in (first, second)]
    assert catalog.import_published()["imported"] == 1
    outcome = tracks.index_published_tracks()
    assert outcome["tracks_indexed"] == 2
    assert not outcome["archive_modified"]
    entries = tracks.find_tracks(search="Händel")
    assert entries["total"] == 1
    assert entries["tracks"][0]["title"] == "Prélude"
    assert entries["tracks"][0]["recording_id"] == "recording-01"
    assert entries["tracks"][0]["release_track_id"] == "release-track-01"
    assert tracks.find_tracks(search="Water Music")["total"] == 1
    assert tracks.find_tracks(role="conductor")["total"] == 1
    assert tracks.find_tracks(role="soloist")["total"] == 1
    assert tracks.find_tracks(search="Jane Example",role="soloist")["total"] == 0
    assert tracks.find_tracks(search="Soloist One",role="soloist")["total"] == 1
    work = entries["tracks"][0]["works"][0]
    assert work["musicbrainz_work_id"] == "work-01"
    assert work["source_tag"] == "WORK"
    assert [p.read_bytes() for p in (first, second)] == original
    assert tracks.index_published_tracks()["tracks_indexed"] == 2
    assert tracks.find_tracks()["total"] == 2


def test_misaligned_work_ids_never_merged(album):
    catalog.import_published()
    tracks.index_published_tracks()
    second = tracks.find_tracks(search="Air")["tracks"][0]
    assert {w["work_title"] for w in second["works"]} == {"Work One","Work Two"}
    assert all(not w["musicbrainz_work_id"] for w in second["works"])


def test_corrupt_archive_sha_blocks_index_without_deleting_prior_good_data(album):
    folder, first, second = album
    catalog.import_published()
    tracks.index_published_tracks()
    assert tracks.find_tracks()["total"] == 2
    second.write_bytes(b"tampered")
    result = tracks.index_published_tracks()
    assert result["tracks_indexed"] == 0
    assert result["albums_skipped"] >= 1
    assert tracks.find_tracks()["total"] == 2


def test_backfill_only_with_exact_release_catalog_and_does_not_overwrite(album):
    catalog.import_published()
    seen = []
    def lookup(release, catalogno):
        seen.append((release, catalogno))
        return "Deutsche Grammophon"
    result = labels.backfill_labels(lookup=lookup)
    assert result["labels_updated"] == 1
    assert seen == [(RELEASE, "DG 100")]
    row = catalog.list_items()["items"][0]
    assert row["label"] == "Deutsche Grammophon"
    assert row["label_provenance"] == "musicbrainz_exact_release_catalog_match"
    assert labels.backfill_labels(lookup=lookup)["labels_updated"] == 0


def test_exact_musicbrainz_label_lookup_rejects_other_catalog(monkeypatch):
    def fetch(request, **kwargs):
        assert "/release/"+RELEASE in request.full_url
        return {"id": RELEASE, "label-info": [
            {"catalog-number":"DG 100", "label":{"name":"Deutsche Grammophon"}},
            {"catalog-number":"OTHER 100","label":{"name":"Unrelated label"}},
        ]}
    monkeypatch.setattr(labels, "fetch_json", fetch)
    assert labels.exact_release_labels(RELEASE, "DG-100") == "Deutsche Grammophon"
    assert labels.exact_release_labels(RELEASE, "NOT MY CD") == ""


def test_track_gui_controls_present():
    from fastapi.testclient import TestClient
    from oscar.api import app
    page = TestClient(app).get("/").text
    assert "Index verified published tracks" in page
    assert "Fill missing labels from exact MusicBrainz release" in page
    assert "track-role" in page
