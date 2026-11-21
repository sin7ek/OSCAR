"""MusicBrainz controlled GENRE suggestions, reviewed FLAC staging and migration."""
import json
from pathlib import Path

from oscar import archive_genres, boxsets, metadata_staging

from test_archive_revision import fixture as archival_fixture
from oscar import archive_metadata_scan as scan
from oscar import archive_revision as revision
from oscar import collection_catalog as catalog


def test_curated_genre_sources_and_freeform_are_ignored():
    raw = {
        "genres": [
            {"name": "baroque", "count": 4},
            {"name": "classical", "count": 8},
            {"name": "free-form micro subgenre", "count": 55},
            {"name": "rock", "count": 0},
            {"name": "electronic", "count": -2},
        ],
        "tags": [{"name": "x", "count": 80}],
    }
    assert archive_genres.musicbrainz_genres(raw) == ["Classical", "Baroque"]
    assert archive_genres.musicbrainz_genres({"tags": raw["tags"]}) == []
    assert archive_genres.normalize_genres(["Electronic", "Hardcore"]) == ["Electronic", "Hardcore"]


def test_new_rip_preview_writes_multivalue_genre_only_from_curated_release():
    from test_metadata_staging import medium_payload
    info = medium_payload()
    info["genres"] = ["Classical", "Baroque"]
    info["genre_source"] = "musicbrainz_release_group"
    plan = metadata_staging.build_preview(
        info, "f41806152a614b1a9006b10456b9bbd4",
        "ROkQlooU5tDdgVZOkfXXTy.S4oU-", 2
    )
    assert plan["album"]["genre_source"] == "musicbrainz_release_group"
    assert plan["tracks"][0]["tags"]["GENRE"] == ["Classical", "Baroque"]
    assert plan["tracks"][1]["tags"]["GENRE"] == ["Classical", "Baroque"]
    assert "GENRE" not in metadata_staging.build_preview(
        medium_payload(), "f41806152a614b1a9006b10456b9bbd4",
        "ROkQlooU5tDdgVZOkfXXTy.S4oU-", 2
    )["tracks"][0]["tags"]


def test_reviewed_archive_genre_migration_only_versions_approved_flacs(fixture, monkeypatch):
    root, old, initial, original_lookup = fixture
    def genre_lookup(*args):
        result = original_lookup(*args)
        result["genres"] = ["Jazz", "Blues"]
        result["genre_source"] = "musicbrainz_release_group"
        return result
    monkeypatch.setattr(scan, "lookup_release_medium", genre_lookup)
    preview = scan.scan("additions", str(old), lookup=genre_lookup)
    genre_proposals = [r for r in preview["pending"] if r["field"] == "GENRE"]
    assert len(genre_proposals) == 1
    assert genre_proposals[0]["after"] == ["Jazz", "Blues"]
    assert scan.decide(genre_proposals[0]["fingerprint"], "accept", lookup=genre_lookup)["status"] == "accepted"
    plan = revision.preview(str(old))
    assert len(plan["accepted_changes"]) == 1
    assert plan["accepted_changes"][0]["field"] == "GENRE"
    result = revision.apply(str(old), plan["fingerprint"], "APPLY_VERIFIED_ARCHIVE_REVISION")
    assert result["status"] == "completed"
    current = Path(result["archive_path"])
    original = Path(result["original_retained_at"])
    from test_archive_revision import FakeFlac
    for name, payload in initial.items():
        assert (original / name).read_bytes() == payload
        assert FakeFlac(current / name).get("GENRE") == ["Jazz", "Blues"]
    row = catalog.list_items()["items"][0]
    assert row["genres"] == "Jazz; Blues"
    assert row["library_section"] == "Popular"
    assert not [r for r in scan.scan("additions", str(current), lookup=genre_lookup)["pending"]
                if r["field"] == "GENRE"]


def test_genre_review_rejects_conflicting_track_tags(fixture, monkeypatch):
    root, old, original, lookup = fixture
    from test_archive_revision import FakeFlac
    first = old / "01 - Song.flac"
    obj = FakeFlac(first)
    obj["GENRE"] = ["Jazz"]
    obj.save()
    manifest = json.loads((old / "manifest.json").read_text())
    manifest["files"][0]["sha256"] = scan._digest(first)
    (old / "manifest.json").write_text(json.dumps(manifest))
    def genre_lookup(*args):
        value = lookup(*args)
        value["genres"] = ["Jazz"]
        return value
    import pytest
    with pytest.raises(scan.ScanError, match="Inconsistent GENRE"):
        scan.scan("additions", str(old), lookup=genre_lookup)
