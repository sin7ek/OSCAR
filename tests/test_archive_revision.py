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
def fixture(tmp_path, monkeypatch, request):
    root = tmp_path / "archive"
    undated = getattr(request, "param", None) == "undated"
    year = "" if undated else "2010"
    edition = "Desire" if undated else "Desire (2010)"
    old = root / "Carmen Gomes Inc" / f"{edition} [fa89edc1]"
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
            **({"RELEASECOUNTRY": ["CA"]} if undated else {}),
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
            (str(old), "Carmen Gomes Inc", "Desire", year, RELEASE, 2,
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


def test_reconcile_after_promotion_but_before_sqlite_commit(fixture, monkeypatch):
    root, old, original, _ = fixture
    plan = _approve(fixture)
    real_finalize = revision._finalize
    def interrupted(db, row, **kw):
        raise RuntimeError("simulated process loss before Collection transaction")
    monkeypatch.setattr(revision, "_finalize", interrupted)
    with pytest.raises(revision.RevisionError, match="not fully completed"):
        revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    op = revision.operations()["items"][0]
    assert op["status"] == "prepared"
    assert Path(op["dest_path"]).is_dir()
    assert Path(op["backup_path"]).is_dir()
    assert catalog.list_items()["items"][0]["archive_path"] == str(old)
    monkeypatch.setattr(revision, "_finalize", real_finalize)
    recovered = revision.reconcile(op["operation_id"])
    assert recovered["status"] == "completed"
    assert catalog.list_items()["items"][0]["archive_path"] == op["dest_path"]
    assert revision.operations()["items"][0]["status"] == "completed"
    assert {name: (Path(op["backup_path"])/name).read_bytes()
            for name in original} == original


def test_rejects_tampered_original_cue_before_publishing(fixture):
    _, old, original, _ = fixture
    plan = _approve(fixture)
    (old/"album.cue").write_text("modified cue")
    with pytest.raises(revision.RevisionError, match="not fully completed"):
        revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert old.is_dir()
    assert {name: (old/name).read_bytes() for name in original} == original
    assert not revision.operations()["items"]


def test_second_revision_can_be_planned_from_new_archive_without_staging(fixture):
    root, old, _, _ = fixture
    plan = _approve(fixture)
    result = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    new_path = result["archive_path"]
    # Future revisions must not be blocked merely because a revision already exists.
    assert scanner._archive_snapshot(new_path)["release_id"] == RELEASE
    # New source fields match MusicBrainz; no new proposal should be created.
    assert scanner.scan("changes", new_path, lookup=fixture[3])["detected"] == 0


def test_real_flac_audio_integrity_through_metadata_revision(fixture, monkeypatch, tmp_path):
    """Integration exercise with actual encoded audio if the FLAC CLI exists."""
    import shutil
    import subprocess
    import wave
    from mutagen.flac import FLAC as MutagenFLAC

    flac_bin, ffmpeg_bin = shutil.which("flac"), shutil.which("ffmpeg")
    if not flac_bin and not ffmpeg_bin:
        pytest.skip("Neither flac nor ffmpeg is installed on this CI runner")
    root, old, _, lookup = fixture
    wav = tmp_path / "silent.wav"
    with wave.open(str(wav), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(b"\\x00\\x00" * 2400)
    manifest_path = old / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    original_md5s = []
    for item in manifest["files"]:
        path = old / item["filename"]
        path.unlink()
        if flac_bin:
            subprocess.check_call([flac_bin, "--silent", "-f", "-o", str(path), str(wav)])
        else:
            subprocess.check_call([ffmpeg_bin, "-v", "error", "-y", "-i", str(wav),
                                   "-c:a", "flac", str(path)])
        obj = MutagenFLAC(str(path))
        obj["MUSICBRAINZ_ALBUMID"] = RELEASE
        obj["MUSICBRAINZ_DISCID"] = DISC
        obj["MUSICBRAINZ_TRACKID"] = f"rec-{item['track']}"
        obj["TITLE"] = "Song"
        obj["ARTIST"] = "Carmen Gomes Inc."
        obj["ALBUM"] = "Desire"
        obj.save()
        item["sha256"] = _digest(path)
        item["streaminfo_audio_md5"] = format(MutagenFLAC(str(path)).info.md5_signature, "032x")
        original_md5s.append(item["streaminfo_audio_md5"])
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(scanner, "FLAC", MutagenFLAC)
    monkeypatch.setattr(revision, "FLAC", MutagenFLAC)
    def real_flac_runner(args, **kwargs):
        test_command = ([flac_bin, "-t", "--silent", args[-1]] if flac_bin else
                        [ffmpeg_bin, "-v", "error", "-i", args[-1], "-f", "null", "-"])
        with subprocess.Popen(test_command, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE) as proc:
            proc.communicate(timeout=kwargs.get("timeout", 180))
            return SimpleNamespace(returncode=proc.returncode)
    monkeypatch.setattr(revision.subprocess, "run", real_flac_runner)
    result = scanner.scan("additions", str(old), lookup=lookup)
    for row in result["pending"]:
        scanner.decide(row["fingerprint"], "accept", lookup=lookup)
    plan = revision.preview(str(old))
    completed = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    new = Path(completed["archive_path"])
    assert new.is_dir()
    for index, item in enumerate(json.loads((new / "manifest.json").read_text())["files"]):
        obj = MutagenFLAC(str(new / item["filename"]))
        assert format(obj.info.md5_signature, "032x") == original_md5s[index]
        assert obj["CATALOGNUMBER"] == ["CGi2010"]
        assert obj["LABEL"] == ["CFMusic"]
        assert _digest(new / item["filename"]) == item["sha256"]
    assert Path(completed["original_retained_at"]).is_dir()


def test_revision_updates_existing_recordlabel_alias_on_approved_label_change(fixture):
    """Approved LABEL changes may not leave contradictory legacy RECORDLABEL tags."""
    _, old, _, lookup = fixture
    manifest_path = old / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["files"]:
        source = old / entry["filename"]
        tags = json.loads(source.read_text())
        tags["RECORDLABEL"] = ["Older Record Label"]
        source.write_text(json.dumps(tags, sort_keys=True))
        entry["sha256"] = _digest(source)
    manifest_path.write_text(json.dumps(manifest))
    proposal = scanner.scan("changes", str(old), lookup=lookup)["pending"]
    label = next(item for item in proposal if item["field"] == "LABEL")
    assert label["before"] == ["Older Record Label"]
    assert label["after"] == ["CFMusic"]
    scanner.decide(label["fingerprint"], "accept", lookup=lookup)
    plan = revision.preview(str(old))
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    migrated = Path(done["archive_path"])
    for entry in json.loads((migrated / "manifest.json").read_text())["files"]:
        tags = FakeFlac(migrated / entry["filename"])
        assert tags.get("LABEL") == ["CFMusic"]
        assert tags.get("RECORDLABEL") == ["CFMusic"]
    assert scanner.scan("changes", str(migrated), lookup=lookup)["detected"] == 0


def test_approved_multilabel_revision_updates_exact_sourced_collection_label(fixture, monkeypatch):
    root, old, original, lookup = fixture
    # Previously enriched Collection values can be partial while the newly
    # reviewed release explicitly names multiple labels.
    with catalog._connect() as db:
        db.execute("UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                   ("Epic", "musicbrainz_exact_release_catalog_match", str(old)))
    def multilabel(*args):
        value = lookup(*args)
        value["label_info"] = [
            {"name": "Daylight", "catalog_number": "CGi2010"},
            {"name": "Epic", "catalog_number": "CGi2010"},
        ]
        return value
    monkeypatch.setattr(scanner, "lookup_release_medium", multilabel)
    result = scanner.scan("additions", str(old), lookup=multilabel)
    label = next(x for x in result["pending"] if x["field"] == "LABEL")
    scanner.decide(label["fingerprint"], "accept", lookup=multilabel)
    plan = revision._plan(str(old), lookup=multilabel)
    # No need to also approve catalog change; the label-only migration can
    # update the Collection row while preserving the original folder name.
    revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert catalog.list_items()["items"][0]["label"] == "Daylight; Epic"
    assert catalog.list_items()["items"][0]["label_provenance"] == "archive_revision_approved_labels"
    catalog.import_published()
    assert catalog.list_items()["items"][0]["label"] == "Daylight; Epic"


def test_approved_label_revision_preserves_manual_collection_value(fixture):
    _, old, _, lookup = fixture
    with catalog._connect() as db:
        db.execute("UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                   ("My verified physical label", "manual", str(old)))
    result = scanner.scan("additions", str(old), lookup=lookup)
    label = next(x for x in result["pending"] if x["field"] == "LABEL")
    scanner.decide(label["fingerprint"], "accept", lookup=lookup)
    plan = revision.preview(str(old))
    revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert catalog.list_items()["items"][0]["label"] == "My verified physical label"

def test_explicit_reconciliation_repairs_previously_completed_multilabel_row(fixture, monkeypatch):
    from oscar.collection_labels import reconcile_applied_archive_labels
    _, old, _, lookup = fixture
    def multilabel(*args):
        value = lookup(*args)
        value["label_info"] = [
            {"name": "Daylight", "catalog_number": "CGi2010"},
            {"name": "Epic", "catalog_number": "CGi2010"},
        ]
        return value
    monkeypatch.setattr(scanner, "lookup_release_medium", multilabel)
    with catalog._connect() as db:
        db.execute("UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                   ("Epic", "musicbrainz_exact_release_catalog_match", str(old)))
    proposal = scanner.scan("additions", str(old), lookup=multilabel)["pending"]
    label = next(x for x in proposal if x["field"] == "LABEL")
    scanner.decide(label["fingerprint"], "accept", lookup=multilabel)
    plan = revision.preview(str(old))
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    revised = done["archive_path"]
    # Model a historical completed migration from before the new finalizer:
    with catalog._connect() as db:
        db.execute("UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                   ("Epic", "musicbrainz_exact_release_catalog_match", revised))
    before = (Path(revised) / "01 - Song.flac").read_bytes()
    report = reconcile_applied_archive_labels()
    assert report["labels_updated"] == 1
    assert catalog.list_items()["items"][0]["label"] == "Daylight; Epic"
    assert (Path(revised) / "01 - Song.flac").read_bytes() == before
    assert reconcile_applied_archive_labels()["labels_updated"] == 0


def test_explicit_reconciliation_preserves_manually_curated_label(fixture, monkeypatch):
    from oscar.collection_labels import reconcile_applied_archive_labels
    _, old, _, lookup = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    with catalog._connect() as db:
        db.execute("UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                   ("My curated edition note", "manual", done["archive_path"]))
    result = reconcile_applied_archive_labels()
    assert result["labels_updated"] == 0
    assert result["manual_values_preserved"] == 1
    assert catalog.list_items()["items"][0]["label"] == "My curated edition note"


def test_completed_archive_revision_verify_is_read_only_and_checks_both_generations(fixture, monkeypatch):
    from oscar import archive_revision_verify as maintenance
    monkeypatch.setattr(maintenance, "FLAC", FakeFlac)
    _, old, _, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    before_original = {p.name: p.read_bytes() for p in Path(done["original_retained_at"]).glob("*.flac")}
    before_new = {p.name: p.read_bytes() for p in Path(done["archive_path"]).glob("*.flac")}
    report = maintenance.verify(done["operation_id"])
    assert report["status"] == "verified"
    assert report["original_flacs_verified"] == 2
    assert report["revised_flacs_verified"] == 2
    assert report["approved_fields_verified"] == 2
    assert report["collection_verified"] and report["manifest_and_evidence_verified"]
    assert {p.name: p.read_bytes() for p in Path(done["archive_path"]).glob("*.flac")} == before_new
    assert {p.name: p.read_bytes() for p in Path(done["original_retained_at"]).glob("*.flac")} == before_original


def test_verify_rejects_changed_new_flac_and_missing_original_evidence(fixture, monkeypatch):
    from oscar import archive_revision_verify as maintenance
    monkeypatch.setattr(maintenance, "FLAC", FakeFlac)
    _, old, _, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    modified = Path(done["archive_path"]) / "01 - Song.flac"
    modified.write_bytes(b"tampered after publication")
    with pytest.raises((maintenance.ArchiveVerifyError, scanner.ScanError), match="SHA-256"):
        maintenance.verify(done["operation_id"])


def test_verify_rejects_stale_sourced_collection_label(fixture, monkeypatch):
    from oscar import archive_revision_verify as maintenance
    monkeypatch.setattr(maintenance, "FLAC", FakeFlac)
    _, old, _, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    with catalog._connect() as db:
        db.execute("UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                   ("Old label", "musicbrainz_exact_release_catalog_match", done["archive_path"]))
    with pytest.raises(maintenance.ArchiveVerifyError, match="Label is stale"):
        maintenance.verify(done["operation_id"])


def test_clean_is_opt_in_per_operation_and_requires_fresh_verification(fixture, monkeypatch):
    from oscar import archive_revision_verify as verify_engine
    from oscar import archive_revision_cleanup as cleanup
    monkeypatch.setattr(verify_engine, "FLAC", FakeFlac)
    _, old, _, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    receipt = verify_engine.verify(done["operation_id"])["verification_fingerprint"]
    historical = Path(done["original_retained_at"])
    active = Path(done["archive_path"])
    new_bytes = {p.name: p.read_bytes() for p in active.glob("*.flac")}
    monkeypatch.delenv("OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP", raising=False)
    with pytest.raises(cleanup.ArchiveCleanupError, match="disabled"):
        cleanup.clean(done["operation_id"], receipt, cleanup.CONFIRM,
                      external_backup_confirmed=True)
    assert historical.is_dir()
    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP", "1")
    with pytest.raises(cleanup.ArchiveCleanupError, match="confirmation"):
        cleanup.clean(done["operation_id"], receipt, cleanup.CONFIRM,
                      external_backup_confirmed=False)
    with pytest.raises(cleanup.ArchiveCleanupError, match="stale"):
        cleanup.clean(done["operation_id"], "0" * 64, cleanup.CONFIRM,
                      external_backup_confirmed=True)
    assert historical.is_dir()
    cleaned = cleanup.clean(done["operation_id"], receipt, cleanup.CONFIRM,
                            external_backup_confirmed=True)
    assert cleaned["status"] == "cleaned"
    assert not historical.exists()
    assert active.is_dir()
    assert {p.name: p.read_bytes() for p in active.glob("*.flac")} == new_bytes
    assert cleanup.cleanup_status(done["operation_id"])["status"] == "completed"
    assert revision.operations()["items"][0]["cleanup_status"] == "completed"
    with pytest.raises(cleanup.ArchiveCleanupError, match="already recorded"):
        cleanup.clean(done["operation_id"], receipt, cleanup.CONFIRM,
                      external_backup_confirmed=True)


def test_clean_refuses_corrupted_original_and_preserves_it(fixture, monkeypatch):
    from oscar import archive_revision_verify as verify_engine
    from oscar import archive_revision_cleanup as cleanup
    monkeypatch.setattr(verify_engine, "FLAC", FakeFlac)
    _, old, _, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    receipt = verify_engine.verify(done["operation_id"])["verification_fingerprint"]
    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP", "1")
    backup = Path(done["original_retained_at"])
    (backup / "01 - Song.flac").write_bytes(b"damaged")
    with pytest.raises((cleanup.ArchiveCleanupError, verify_engine.ArchiveVerifyError), match="SHA-256"):
        cleanup.clean(done["operation_id"], receipt, cleanup.CONFIRM,
                      external_backup_confirmed=True)
    assert backup.exists()
    assert cleanup.cleanup_status(done["operation_id"]) is None


def test_explicit_reconciliation_preserves_unknown_nonempty_label_provenance(fixture):
    from oscar.collection_labels import reconcile_applied_archive_labels
    _, old, _, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    with catalog._connect() as db:
        db.execute("UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                   ("Legacy manually curated value", "", done["archive_path"]))
    report = reconcile_applied_archive_labels()
    assert report["labels_updated"] == 0
    assert report["manual_values_preserved"] == 1
    assert catalog.list_items()["items"][0]["label"] == "Legacy manually curated value"


def test_verify_and_clean_api_require_auth_and_opt_in(fixture, monkeypatch):
    from oscar import archive_revision_verify as verify_engine
    from oscar import archive_revision_cleanup as cleanup
    monkeypatch.setattr(verify_engine, "FLAC", FakeFlac)
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    _, old, _, _ = fixture
    plan = _approve(fixture)
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    client = TestClient(app)
    payload = {"operation_id": done["operation_id"]}
    assert client.post("/api/collection/archive-revisions/verify", json=payload).status_code == 403
    headers = {"X-OSCAR-RIP-TOKEN": TOKEN}
    result = client.post("/api/collection/archive-revisions/verify",
                         json=payload, headers=headers)
    assert result.status_code == 200
    assert result.json()["status"] == "verified"
    clean_request = {
        **payload,
        "verification_fingerprint": result.json()["verification_fingerprint"],
        "confirmation": cleanup.CONFIRM,
        "external_backup_confirmed": True,
    }
    assert client.post("/api/collection/archive-revisions/clean",
                       json=clean_request).status_code == 403
    monkeypatch.delenv("OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP", raising=False)
    response = client.post("/api/collection/archive-revisions/clean",
                           json=clean_request, headers=headers)
    assert response.status_code == 409
    assert Path(done["original_retained_at"]).exists()


@pytest.mark.parametrize("fixture", ["undated"], indirect=True)
def test_date_and_country_revision_moves_undated_archive(fixture, monkeypatch):
    from oscar import archive_revision_verify

    _, old, original, lookup = fixture

    def corrected_release(*args):
        return {**lookup(*args), "date": "1985", "country": "DE"}

    monkeypatch.setattr(scanner, "lookup_release_medium", corrected_release)
    monkeypatch.setattr(archive_revision_verify, "FLAC", FakeFlac)

    for mode, field in [("additions", "DATE"), ("changes", "RELEASECOUNTRY")]:
        proposals = scanner.scan(mode, str(old))["pending"]
        proposal = next(item for item in proposals if item["field"] == field)
        scanner.decide(proposal["fingerprint"], "accept")
    plan = revision.preview(str(old))
    current = old.with_name("Desire (1985) [fa89edc1]")
    assert plan["dest_path"] == str(current)
    assert old.exists() and not current.exists()

    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert done["status"] == "completed"
    assert not old.exists()
    historical = Path(done["original_retained_at"])
    for name, data in original.items():
        assert (historical / name).read_bytes() == data
        actual = FakeFlac(current / name)
        assert actual.get("DATE") == ["1985"]
        assert actual.get("RELEASECOUNTRY") == ["DE"]

    entry, = catalog.list_items()["items"]
    assert (entry["archive_path"], entry["year"], entry["musicbrainz_release_id"]) == (str(current), "1985", RELEASE)
    assert archive_revision_verify.verify(done["operation_id"])["status"] == "verified"
    assert catalog.import_published()["imported"] == 0


def test_discogs_genre_addition_pins_source_and_updates_collection(fixture, monkeypatch):
    from oscar import genre_evidence

    _, old, _, _ = fixture
    source = "https://www.discogs.com/release/4709815"
    monkeypatch.setattr(genre_evidence, "discogs_fallback", lambda info: (["Electronic"], source))
    proposals = scanner.scan("additions", str(old))["pending"]
    genre = next(item for item in proposals if item["field"] == "GENRE")
    assert genre["source"] == "discogs" and genre["source_url"] == source

    scanner.decide(genre["fingerprint"], "accept")
    different_source = "https://www.discogs.com/release/11725689"
    monkeypatch.setattr(genre_evidence, "discogs_fallback", lambda info: (["Electronic"], different_source))
    with pytest.raises(revision.RevisionError, match="provider data"):
        revision.preview(str(old))

    monkeypatch.setattr(genre_evidence, "discogs_fallback", lambda info: (["Electronic"], source))
    plan = revision.preview(str(old))
    done = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    current = Path(done["archive_path"])
    assert FakeFlac(current / "01 - Song.flac").get("GENRE") == ["Electronic"]
    assert catalog.list_items()["items"][0]["genres"] == "Electronic"
    manifest = json.loads((current / "manifest.json").read_text())
    assert manifest["revision"]["genre_source_url"] == source
