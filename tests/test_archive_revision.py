"""Offline end-to-end archive migration tests with fake FLAC/decoder.

These assert exact original preservation, catalog directory migration, SQLite
proposal application, version history, no staging dependency and rollback.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oscar import archive_metadata_scan as scanner
from oscar import archive_revision as revision
from oscar import collection_catalog as catalog
from oscar.api import app

RELEASE = "fa89edc1-32f9-4290-8788-bbac2e366a46"
PUBLISH = "3908eef79f114450b0a7eb76bec44926"
DISC = "VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-"
MD5 = 123456789
TOKEN = "0123456789abcdef0123456789abcdef"


class FakeFlac:
    def __init__(self, path):
        self.path = Path(path)
        self.tags = json.loads(self.path.read_text())
        self.info = SimpleNamespace(md5_signature=MD5)
    def items(self):
        return self.tags.items()
    def get(self, key):
        return self.tags.get(key.upper(), [])
    def __setitem__(self, key, value):
        self.tags[key.upper()] = list(value)
    def save(self):
        self.path.write_text(json.dumps(self.tags, sort_keys=True))


def _digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = tmp_path / "archive"
    old = root / "Carmen Gomes Inc" / "Desire (2010) [fa89edc1]"
    old.mkdir(parents=True)
    db_root = tmp_path / "config"; db_root.mkdir()
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(root))
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(db_root / "catalog.sqlite3"))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_MUSICBRAINZ", "1")
    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_REVISIONS", "1")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    monkeypatch.setattr(scanner, "FLAC", FakeFlac)
    monkeypatch.setattr(revision, "FLAC", FakeFlac)
    monkeypatch.setattr(catalog, "_archive_tag_metadata", lambda album, manifest: {
        **{field: "" for field in catalog._ENRICHED},
        "legacy_soloists": "",
    })
    monkeypatch.setattr(revision.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    source_bytes = {}
    files = []
    for number in (1,2):
        name = f"{number:02d} - Song.flac"
        target = old / name
        target.write_text(json.dumps({
            "MUSICBRAINZ_ALBUMID": [RELEASE],
            "MUSICBRAINZ_DISCID": [DISC],
            "MUSICBRAINZ_TRACKID": [f"rec-{number}"],
            "TITLE": ["Song"], "ARTIST": ["Carmen Gomes Inc."],
            "ALBUM": ["Desire"],
        }, sort_keys=True))
        source_bytes[name] = target.read_bytes()
        files.append({"track": number, "filename": name,
                      "sha256": _digest(target),
                      "streaminfo_audio_md5": format(MD5, "032x")})
    cue = old / "album.cue"
    cue.write_text('FILE "01 - Song.flac" WAVE\nFILE "02 - Song.flac" WAVE\n')
    evidence = old / "ExtractionEvidence" / "audio"
    evidence.mkdir(parents=True)
    (evidence / "original.cue").write_bytes(b"verified original disc cue")
    manifest = {
        "status": "published_verified",
        "publish_id": PUBLISH,
        "release_id": RELEASE,
        "profile": "standard",
        "disc_number": 1, "disc_total": 1,
        "label_info": [{"name": "CFMusic", "catalog_number": None}],
        "cue": {"filename": "album.cue", "sha256": _digest(cue)},
        "source_evidence": [{
            "filename": "ExtractionEvidence/audio/original.cue",
            "sha256": _digest(evidence / "original.cue"),
            "size": (evidence / "original.cue").stat().st_size,
        }],
        "files": files,
    }
    (old / "manifest.json").write_text(json.dumps(manifest))
    with catalog._connect() as db:
        db.execute(
            "INSERT INTO archive_items "
            "(archive_path,artist,title,year,musicbrainz_release_id,track_count,archive_status,imported_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (str(old), "Carmen Gomes Inc", "Desire", "2010", RELEASE, 2,
             "published_verified", "2026-11-20T00:00:00+00:00"),
        )
    def lookup(release, disc, count):
        assert (release,disc,count)==(RELEASE,DISC,2)
        return {"release_id": RELEASE, "status": "exact_disc_id_and_track_count",
                "label_info": [{"name":"CFMusic", "catalog_number":"CGi2010"}],
                "matched_media": [{
                    "position":1,"format":"CD","disc_id_attached":True,
                    "track_count_matches":True,
                    "tracks":[
                        {"position":1,"title":"Song","recording_id":"rec-1",
                         "artist_credit":"Carmen Gomes Inc."},
                        {"position":2,"title":"Song","recording_id":"rec-2",
                         "artist_credit":"Carmen Gomes Inc."},
                    ],
                }]}
    monkeypatch.setattr(scanner,"lookup_release_medium",lookup)
    # No staging folder is created. All source material exists in /archive.
    return root, old, source_bytes, lookup


def _approve(fixture):
    _, old, _, lookup = fixture
    result = scanner.scan("additions", str(old), lookup=lookup)
    assert {x["field"] for x in result["pending"]} == {"CATALOGNUMBER", "LABEL"}
    for row in result["pending"]:
        assert scanner.decide(row["fingerprint"], "accept", lookup=lookup)["status"] == "accepted"
    return revision.preview(str(old))


def test_preview_catalog_path_and_no_archive_mutations(fixture):
    root, old, source_bytes, _ = fixture
    plan = _approve(fixture)
    assert plan["source_path"] == str(old)
    assert plan["dest_path"] == str(root / "Carmen Gomes Inc" /
                                   "[CGi2010] Desire (2010) [fa89edc1]")
    assert plan["catalog_number"] == "CGi2010"
    assert len(plan["accepted_changes"]) == 2
    assert {name: (old/name).read_bytes() for name in source_bytes} == source_bytes
    assert len(list(root.rglob("manifest.json"))) == 1


def test_applied_revision_keeps_original_and_changes_collection(fixture, monkeypatch):
    root, old, original, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert done["status"] == "completed"
    current = Path(done["archive_path"])
    assert current.is_dir() and current != old and not old.exists()
    historical = Path(done["original_retained_at"])
    assert historical.is_dir()
    assert {name: (historical/name).read_bytes() for name in original} == original
    current_tags = FakeFlac(current / "01 - Song.flac")
    assert current_tags.get("CATALOGNUMBER") == ["CGi2010"]
    assert current_tags.get("LABEL") == ["CFMusic"]
    manifest = json.loads((current/"manifest.json").read_text())
    assert manifest["revision"]["parent_publish_id"] == PUBLISH
    assert manifest["revision"]["parent_manifest_sha256"] == _digest(historical/"manifest.json")
    assert len(manifest["files"]) == 2
    assert catalog.list_items()["total"] == 1
    assert catalog.list_items()["items"][0]["archive_path"] == str(current)
    assert catalog.list_items()["items"][0]["catalog_number"] == "CGi2010"
    assert scanner.scan("additions", str(current), lookup=fixture[3])["detected"] == 0
    statuses = [item["status"] for item in scanner.list_proposals(include_decided=True)["items"]]
    assert statuses == ["applied", "applied"]
    assert revision.operations()["items"][0]["status"] == "completed"
    assert catalog.import_published()["imported"] == 0
    assert catalog.list_items()["total"] == 1


def test_no_mutation_when_opt_in_disabled_or_fingerprint_stale(fixture, monkeypatch):
    _, old, source_bytes, _ = fixture
    plan = _approve(fixture)
    monkeypatch.delenv("OSCAR_ENABLE_ARCHIVE_REVISIONS")
    with pytest.raises(revision.RevisionError, match="disabled"):
        revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_REVISIONS", "1")
    with pytest.raises(revision.RevisionError, match="changed since migration preview"):
        revision.apply(str(old), "0"*64, "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert {name: (old/name).read_bytes() for name in source_bytes} == source_bytes
    assert len(revision.operations()["items"]) == 0


def test_rollback_on_failed_promotion_keeps_live_archive(fixture, monkeypatch):
    from oscar import archive_publish
    _, old, source_bytes, _ = fixture
    plan = _approve(fixture)
    original = archive_publish._rename_noreplace
    count = 0
    def fault(source, dest):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("simulated promotion failure")
        return original(source, dest)
    monkeypatch.setattr(archive_publish, "_rename_noreplace", fault)
    with pytest.raises(revision.RevisionError, match="not fully completed"):
        revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert old.is_dir()
    assert {name: (old/name).read_bytes() for name in source_bytes} == source_bytes
    assert revision.operations()["items"][0]["status"] == "rolled_back"
    assert catalog.list_items()["items"][0]["archive_path"] == str(old)


def test_authenticated_revision_routes_and_gui(fixture):
    client = TestClient(app)
    assert client.post("/api/collection/archive-revisions/preview",
                       json={"archive_path":str(fixture[1])}).status_code == 403
    assert client.post("/api/collection/archive-revisions/apply",
                       json={"archive_path":str(fixture[1]),
                             "fingerprint":"0"*64,"confirmation":"APPLY_VERIFIED_ARCHIVE_REVISION"}).status_code == 403
    html = client.get("/").text
    assert "Preview approved archive migration for selected album" in html
    assert "APPLY_VERIFIED_ARCHIVE_REVISION" in html
    assert "OSCAR_ENABLE_ARCHIVE_REVISIONS=1" in html
