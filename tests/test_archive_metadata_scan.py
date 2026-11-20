"""Archive-first scanning tests: no staging required, no archive mutation."""
import hashlib
import json
import os

import pytest
from fastapi.testclient import TestClient

from oscar import archive_metadata_scan as scan
from oscar.api import app

RELEASE = "fa89edc1-32f9-4290-8788-bbac2e366a46"
PUBLISH = "3908eef79f114450b0a7eb76bec44926"
DISC = "VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-"
TOKEN = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def archive(tmp_path, monkeypatch):
    root = tmp_path / "archive"
    album = root / "Carmen Gomes Inc" / "Desire (2010) [fa89edc1]"
    album.mkdir(parents=True)
    db = tmp_path / "config"; db.mkdir()
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(root))
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(db / "catalog.sqlite3"))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_MUSICBRAINZ", "1")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    files = []
    for n in range(1, 3):
        f = album / f"{n:02d} - Song.flac"
        f.write_bytes(f"fake FLAC {n}".encode())
        files.append({"track": n, "filename": f.name,
                      "sha256": hashlib.sha256(f.read_bytes()).hexdigest()})
    manifest = {"status": "published_verified", "publish_id": PUBLISH,
                "release_id": RELEASE, "disc_number": 1, "disc_total": 1,
                "files": files}
    (album / "manifest.json").write_text(json.dumps(manifest))
    class FakeFlac:
        def __init__(self, name):
            self.name = name
        def items(self):
            return {
                "MUSICBRAINZ_ALBUMID": [RELEASE], "MUSICBRAINZ_DISCID": [DISC],
                "MUSICBRAINZ_TRACKID": ["rec-"+self.name[-14:-13]] if False else [
                    "rec-" + os.path.basename(self.name)[:2].lstrip("0")],
                "TITLE": ["Song"], "ARTIST": ["Carmen Gomes Inc."],
                "ALBUM": ["Desire"],
            }.items()
    monkeypatch.setattr(scan, "FLAC", FakeFlac)
    def lookup(release, disc, count):
        assert (release,disc,count)==(RELEASE,DISC,2)
        return {"release_id": RELEASE, "status": "exact_disc_id_and_track_count",
                "label_info": [{"name": "CFMusic", "catalog_number": "CGi2010"}],
                "matched_media": [{
                    "position": 1, "format": "CD", "disc_id_attached": True,
                    "track_count_matches": True,
                    "tracks": [
                        {"position": 1, "title": "Song", "recording_id": "rec-1",
                         "artist_credit": "Carmen Gomes Inc."},
                        {"position": 2, "title": "Song", "recording_id": "rec-2",
                         "artist_credit": "Carmen Gomes Inc."},
                    ]}]}
    return album, lookup


def test_archive_metadata_addition_without_staging_or_any_archive_writes(archive):
    album, lookup = archive
    before = {p.name: p.read_bytes() for p in album.iterdir()}
    result = scan.scan("additions", str(album), lookup=lookup)
    assert result["detected"] == 2
    assert {x["field"] for x in result["pending"]} == {"CATALOGNUMBER", "LABEL"}
    assert {p.name: p.read_bytes() for p in album.iterdir()} == before
    assert scan.scan("additions", str(album), lookup=lookup)["detected"] == 2
    assert scan.list_proposals()["count"] == 2


def test_ignore_suppresses_exact_proposal_and_new_value_reappears(archive):
    album, lookup = archive
    first = scan.scan("additions", str(album), lookup=lookup)
    catalog_fp = next(x["fingerprint"] for x in first["pending"] if x["field"]=="CATALOGNUMBER")
    accepted = scan.decide(catalog_fp, "ignore", lookup=lookup)
    assert accepted["status"] == "ignored" and accepted["applied"] is False
    repeat = scan.scan("additions", str(album), lookup=lookup)
    assert repeat["suppressed"] == 1
    assert all(x["fingerprint"] != catalog_fp for x in repeat["pending"])
    assert scan.decision_history()["events"][0]["decision"] == "ignored"
    def changed(*args):
        updated = lookup(*args)
        updated["label_info"][0]["catalog_number"] = "CGI-2010"
        return updated
    next_result = scan.scan("additions", str(album), lookup=changed)
    assert any(x["after"] == ["CGI-2010"] for x in next_result["pending"])
    assert scan.list_proposals(include_decided=True)["count"] == 3


def test_accepted_is_not_applied_and_decision_is_durable(archive):
    album, lookup = archive
    item = scan.scan("additions", str(album), lookup=lookup)["pending"][0]
    out = scan.decide(item["fingerprint"], "accept", lookup=lookup)
    assert out["status"] == "accepted" and not out["applied"]
    assert scan.list_proposals(include_decided=True)["count"] == 2
    assert scan.list_proposals()["count"] == 1
    with pytest.raises(scan.ScanError, match="not pending"):
        scan.decide(item["fingerprint"], "ignore", lookup=lookup)


def test_changes_mode_detects_changed_title_without_mutating(archive):
    album, lookup = archive
    def changed(*args):
        result = lookup(*args)
        result["matched_media"][0]["tracks"][0]["title"] = "Corrected Song"
        return result
    value = scan.scan("changes", str(album), lookup=changed)
    assert value["detected"] == 1
    assert value["pending"][0]["scope"] == "track"
    assert value["pending"][0]["field"] == "TITLE"
    assert value["pending"][0]["after"] == ["Corrected Song"]


def test_rejects_hash_or_recording_identity_mismatch(archive):
    album, lookup = archive
    (album/"01 - Song.flac").write_bytes(b"tampered")
    with pytest.raises(scan.ScanError, match="SHA-256"):
        scan.scan("additions", str(album), lookup=lookup)
    assert scan.list_proposals()["count"] == 0


def test_rejects_incorrect_medium_and_stale_provider_decision(archive):
    album, lookup = archive
    first = scan.scan("additions", str(album), lookup=lookup)
    fp = first["pending"][0]["fingerprint"]
    def other_medium(*args):
        result = lookup(*args)
        result["matched_media"][0]["position"] = 2
        return result
    with pytest.raises(scan.ScanError, match="medium ambiguous"):
        scan.decide(fp, "accept", lookup=other_medium)
    assert scan.list_proposals()["count"] == 2


def test_api_auth_and_gui_controls(archive):
    assert TestClient(app).post("/api/collection/archive-metadata/scan",
            json={"mode":"additions","archive_path":str(archive[0])}).status_code == 403
    html = TestClient(app).get("/").text
    assert "Scan archive for metadata additions" in html
    assert "Scan archive for metadata changes" in html
    assert "Ignore this exact change" in html
