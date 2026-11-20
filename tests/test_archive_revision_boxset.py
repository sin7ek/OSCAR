"""Read-only coordinated multidisc label preview regression tests."""
import hashlib
import json
from pathlib import Path

import pytest

from oscar import archive_metadata_scan as scan
from oscar import archive_revision_boxset as boxset
from oscar import collection_catalog as catalog

RELEASE = "423f636d-742d-47b0-9ba2-51515a6fdfd2"
DISCS = {
    4: "VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-",
    6: "ROkQlooU5tDdgVZOkfXXTy.S4oU-",
}


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / "archive"
    root.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(root))
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(config / "catalog.sqlite3"))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("OSCAR_ENABLE_MUSICBRAINZ", "1")
    parent = root / "Stravinsky; Pierre Boulez" / "[6CD 477 8730 GB6] Boulez Conducts Stravinsky (2010) [423f636d]"
    original = {}
    paths = {}
    for n in DISCS:
        leaf = parent / f"Disc {n:02d}"
        leaf.mkdir(parents=True)
        audio = leaf / "01 - Track.flac"
        audio.write_bytes(b"fake flac disc" + str(n).encode())
        manifest = {
            "status": "published_verified",
            "publish_id": f"{n:032x}", "release_id": RELEASE,
            "disc_number": n, "disc_total": 6,
            "files": [{
                "track": 1, "filename": audio.name,
                "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            }],
        }
        (leaf / "manifest.json").write_text(json.dumps(manifest))
        original[n] = (audio.read_bytes(), (leaf / "manifest.json").read_bytes())
        paths[n] = leaf
        with catalog._connect() as db:
            db.execute(
                "INSERT INTO archive_items "
                "(archive_path,artist,title,year,musicbrainz_release_id,track_count,"
                "disc_number,disc_total,archive_status,imported_at,catalog_number) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (str(leaf), "Stravinsky; Pierre Boulez", "Boulez Conducts Stravinsky",
                 "2010", RELEASE, 1, n, 6, "published_verified", "2026", "6CD 477 8730 GB6"),
            )

    class FakeFlac:
        def __init__(self, path):
            self.path = Path(path)
            self.n = int(self.path.parent.name.split()[-1])
        def items(self):
            return {
                "MUSICBRAINZ_ALBUMID": [RELEASE],
                "MUSICBRAINZ_DISCID": [DISCS[self.n]],
                "MUSICBRAINZ_TRACKID": [f"record-{self.n}"],
                "CATALOGNUMBER": ["6CD 477 8730 GB6"],
                "TITLE": ["Track"],
                "ARTIST": ["Stravinsky; Pierre Boulez"],
            }.items()
    monkeypatch.setattr(scan, "FLAC", FakeFlac)

    def lookup(release, disc_id, count):
        assert release == RELEASE and count == 1
        n = next(n for n, identifier in DISCS.items() if identifier == disc_id)
        return {
            "release_id": RELEASE, "status": "exact_disc_id_and_track_count",
            "label_info": [{"name": "Deutsche Grammophon",
                            "catalog_number": "6CD 477 8730 GB6"}],
            "matched_media": [{
                "position": n, "format": "CD",
                "disc_id_attached": True, "track_count_matches": True,
                "tracks": [{
                    "position": 1, "title": "Track",
                    "recording_id": f"record-{n}",
                    "artist_credit": "Stravinsky; Pierre Boulez",
                }],
            }],
        }
    return paths, original, lookup


def test_boxset_preview_groups_partial_release_and_recognizes_approvals(prepared):
    paths, originals, lookup = prepared
    for leaf in paths.values():
        pending = scan.scan("additions", str(leaf), lookup=lookup)["pending"]
        assert len(pending) == 1 and pending[0]["field"] == "LABEL"
        scan.decide(pending[0]["fingerprint"], "accept", lookup=lookup)
    result = boxset.preview(RELEASE, lookup=lookup)
    assert result["present_disc_numbers"] == [4, 6]
    assert result["missing_disc_numbers"] == [1, 2, 3, 5]
    assert result["partial_boxset"] is True
    assert result["disc_total"] == 6
    assert result["reviewed_labels"] == ["Deutsche Grammophon"]
    assert result["all_present_discs_reviewed"] is True
    assert result["apply_supported"] is False
    assert all(x["label_status"] == "approved_for_review" for x in result["disc_reviews"])
    for n, leaf in paths.items():
        assert ((leaf / "01 - Track.flac").read_bytes(),
                (leaf / "manifest.json").read_bytes()) == originals[n]


def test_boxset_preview_requires_approval_on_every_present_disc(prepared):
    paths, originals, lookup = prepared
    first = scan.scan("additions", str(paths[4]), lookup=lookup)["pending"]
    scan.decide(first[0]["fingerprint"], "accept", lookup=lookup)
    second = scan.scan("additions", str(paths[6]), lookup=lookup)["pending"]
    assert second[0]["field"] == "LABEL"
    result = boxset.preview(RELEASE, lookup=lookup)
    assert not result["all_present_discs_reviewed"]
    assert [x["label_status"] for x in result["disc_reviews"]] == [
        "approved_for_review", "needs_operator_approval",
    ]
    assert result["apply_supported"] is False


def test_boxset_preview_refuses_wrong_release_or_non_boxset(prepared):
    paths, _, lookup = prepared
    with pytest.raises(boxset.BoxsetReviewError, match="full MusicBrainz"):
        boxset.preview("423f636d", lookup=lookup)
    with pytest.raises(boxset.BoxsetReviewError, match="No indexed"):
        boxset.preview("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", lookup=lookup)


def test_boxset_preview_api_requires_auth_and_ui_is_explicitly_read_only(prepared, monkeypatch):
    from fastapi.testclient import TestClient
    from oscar.api import app
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    html = client.get("/").text
    assert "Preview coordinated multidisc labels (read-only)" in html
    assert "archive-boxset-label-preview" in html
    assert "boxset-preview" in html
    no_auth = client.post("/api/collection/archive-revisions/boxset-preview",
                          json={"release_id": RELEASE})
    assert no_auth.status_code == 403


def test_five_of_six_preview_includes_newly_published_discs_and_invalidates_old_plan(
    prepared, monkeypatch
):
    """If the owner rips three more discs, the old two-disc plan must be stale."""
    paths, originals, lookup = prepared
    for leaf in paths.values():
        proposal = scan.scan("additions", str(leaf), lookup=lookup)["pending"][0]
        scan.decide(proposal["fingerprint"], "accept", lookup=lookup)
    before = boxset.preview(RELEASE, lookup=lookup)
    assert before["present_disc_numbers"] == [4, 6]
    monkeypatch.setattr(
        __import__(__name__, fromlist=["DISCS"]), "DISCS",
        {**DISCS,
         1: "AAAAAAAAAAAAAAAAAAAAAAAAAAA-",
         2: "BBBBBBBBBBBBBBBBBBBBBBBBBBB-",
         3: "CCCCCCCCCCCCCCCCCCCCCCCCCCC-"},
    )
    root = paths[4].parent
    for n in (1, 2, 3):
        leaf = root / f"Disc {n:02d}"
        leaf.mkdir()
        audio = leaf / "01 - Track.flac"
        audio.write_bytes(b"fake flac disc" + str(n).encode())
        manifest = {
            "status": "published_verified", "publish_id": f"{n:032x}",
            "release_id": RELEASE, "disc_number": n, "disc_total": 6,
            "files": [{
                "track": 1, "filename": audio.name,
                "sha256": hashlib.sha256(audio.read_bytes()).hexdigest(),
            }],
        }
        (leaf / "manifest.json").write_text(json.dumps(manifest))
        with catalog._connect() as db:
            db.execute(
                "INSERT INTO archive_items "
                "(archive_path,artist,title,year,musicbrainz_release_id,track_count,"
                "disc_number,disc_total,archive_status,imported_at,catalog_number) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (str(leaf), "Stravinsky; Pierre Boulez",
                 "Boulez Conducts Stravinsky", "2010", RELEASE,
                 1, n, 6, "published_verified", "2026", "6CD 477 8730 GB6"),
            )
        proposal = scan.scan("additions", str(leaf), lookup=lookup)["pending"][0]
        scan.decide(proposal["fingerprint"], "accept", lookup=lookup)
    after = boxset.preview(RELEASE, lookup=lookup)
    assert after["present_disc_numbers"] == [1, 2, 3, 4, 6]
    assert after["missing_disc_numbers"] == [5]
    assert after["all_present_discs_reviewed"] is True
    assert after["fingerprint"] != before["fingerprint"]
    assert after["apply_supported"] is False
    for n, leaf in paths.items():
        assert ((leaf / "01 - Track.flac").read_bytes(),
                (leaf / "manifest.json").read_bytes()) == originals[n]


def test_boxset_preview_refuses_unindexed_published_disc(prepared):
    paths, originals, lookup = prepared
    leaf = paths[4].parent / "Disc 01"
    leaf.mkdir()
    (leaf / "manifest.json").write_text('{"status":"published_verified"}')
    with pytest.raises(boxset.BoxsetReviewError, match="Unindexed published disc"):
        boxset.preview(RELEASE, lookup=lookup)
    for n, archived in paths.items():
        assert ((archived / "01 - Track.flac").read_bytes(),
                (archived / "manifest.json").read_bytes()) == originals[n]


def _approved_group(prepared, monkeypatch):
    """Two-disc synthetic publication fixture for group journaling, not audio QA."""
    import shutil
    import uuid
    from oscar import archive_revision_boxset_apply as engine
    from oscar import archive_revision as single
    paths, _, lookup = prepared
    for leaf in paths.values():
        pending = scan.scan("additions", str(leaf), lookup=lookup)["pending"]
        scan.decide(pending[0]["fingerprint"], "accept", lookup=lookup)
    monkeypatch.setenv("OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS", "1")

    def fake_copy(plan, temp, source):
        shutil.copytree(source, temp)
        manifest_path = temp / "manifest.json"
        data = json.loads(manifest_path.read_text())
        old_id = data["publish_id"]
        new_id = uuid.uuid4().hex
        data["publish_id"] = new_id
        data["revision"] = {
            "parent_publish_id": old_id,
            "parent_manifest_sha256": plan["original_manifest_sha256"],
        }
        audio = temp / data["files"][0]["filename"]
        audio.write_bytes(audio.read_bytes() + b" TAGGED")
        data["files"][0]["sha256"] = hashlib.sha256(audio.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(data))
        return new_id

    def synthetic_validation(path, entry, *, new):
        manifest = json.loads((path / "manifest.json").read_text())
        expected = entry["new_publish_id"] if new else entry["old_publish_id"]
        assert manifest["publish_id"] == expected
        if not new:
            assert hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest() == entry["old_manifest_sha256"]
        audio = path / manifest["files"][0]["filename"]
        assert hashlib.sha256(audio.read_bytes()).hexdigest() == manifest["files"][0]["sha256"]
        return manifest

    monkeypatch.setattr(single, "_copy_and_retag", fake_copy)
    monkeypatch.setattr(engine, "_validate_leaf", synthetic_validation)
    return paths, lookup, engine


def test_group_apply_requires_explicit_opt_in_and_confirmation(prepared, monkeypatch):
    from oscar import archive_revision_boxset_apply as engine
    paths, _, lookup = prepared
    for leaf in paths.values():
        pending = scan.scan("additions", str(leaf), lookup=lookup)["pending"]
        scan.decide(pending[0]["fingerprint"], "accept", lookup=lookup)
    review = boxset.preview(RELEASE, lookup=lookup)
    with pytest.raises(engine.BoxsetApplyError, match="disabled"):
        engine.apply(RELEASE, review["fingerprint"], "APPLY_COORDINATED_BOXSET_REVISION", lookup=lookup)
    monkeypatch.setenv("OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS", "1")
    with pytest.raises(engine.BoxsetApplyError, match="confirmation"):
        engine.apply(RELEASE, review["fingerprint"], "wrong", lookup=lookup)
    for leaf in paths.values():
        assert (leaf / "manifest.json").is_file()


def test_group_apply_versions_both_discs_and_commits_collection_together(prepared, monkeypatch):
    paths, lookup, engine = _approved_group(prepared, monkeypatch)
    review = boxset.preview(RELEASE, lookup=lookup)
    result = engine.apply(RELEASE, review["fingerprint"],
                          "APPLY_COORDINATED_BOXSET_REVISION", lookup=lookup)
    assert result["status"] == "completed"
    assert result["discs"] == [4, 6]
    for leaf in paths.values():
        assert (leaf / "01 - Track.flac").read_bytes().endswith(b" TAGGED")
    for name in result["originals_retained"]:
        assert (Path(name) / "01 - Track.flac").is_file()
        assert not (Path(name) / "01 - Track.flac").read_bytes().endswith(b" TAGGED")
    with engine._db() as db:
        operations = db.execute("SELECT status FROM boxset_revision_operations").fetchall()
        assert [r["status"] for r in operations] == ["completed"]
        proposals = db.execute("SELECT status FROM metadata_proposals").fetchall()
        assert [r["status"] for r in proposals] == ["applied", "applied"]
        rows = db.execute("SELECT label FROM archive_items ORDER BY disc_number").fetchall()
        assert [r["label"] for r in rows] == ["Deutsche Grammophon"] * 2


def test_group_failure_reconciles_after_one_promoted_disc(prepared, monkeypatch):
    paths, lookup, engine = _approved_group(prepared, monkeypatch)
    from oscar import archive_publish
    original_rename = archive_publish._rename_noreplace
    counter = {"n": 0}

    def fail_third_rename(source, dest):
        counter["n"] += 1
        if counter["n"] == 3:
            raise OSError("simulated crash after first disc promotion")
        return original_rename(source, dest)

    monkeypatch.setattr(archive_publish, "_rename_noreplace", fail_third_rename)
    review = boxset.preview(RELEASE, lookup=lookup)
    with pytest.raises(engine.BoxsetApplyError, match="reconciliation"):
        engine.apply(RELEASE, review["fingerprint"],
                     "APPLY_COORDINATED_BOXSET_REVISION", lookup=lookup)
    history = engine.operations()["items"]
    assert len(history) == 1 and history[0]["status"] == "prepared"
    with engine._db() as db:
        assert {r["status"] for r in db.execute("SELECT status FROM metadata_proposals")} == {"accepted"}
    monkeypatch.setattr(archive_publish, "_rename_noreplace", original_rename)
    assert engine.reconcile(history[0]["operation_id"])["status"] == "completed"
    assert all((leaf / "01 - Track.flac").read_bytes().endswith(b" TAGGED") for leaf in paths.values())
    with engine._db() as db:
        assert {r["status"] for r in db.execute("SELECT status FROM metadata_proposals")} == {"applied"}


def test_group_rejects_stale_fingerprint_without_mutation(prepared, monkeypatch):
    paths, lookup, engine = _approved_group(prepared, monkeypatch)
    review = boxset.preview(RELEASE, lookup=lookup)
    with pytest.raises(engine.BoxsetApplyError, match="Stale"):
        engine.apply(RELEASE, "0" * 64,
                     "APPLY_COORDINATED_BOXSET_REVISION", lookup=lookup)
    assert not engine.operations()["items"]
    for leaf in paths.values():
        assert (leaf / "01 - Track.flac").is_file()
