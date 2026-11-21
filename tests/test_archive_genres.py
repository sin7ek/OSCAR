"""Controlled genre indexing and non-destructive Classical/Popular library sections."""
import json

import pytest
from fastapi.testclient import TestClient

from oscar import archive_genres
from oscar import collection_catalog as catalog
from oscar.api import app


def test_classical_baroque_and_popular_hardcore():
    assert archive_genres.classify(["Baroque"], profile="classical") == {
        "genres": "Classical; Baroque", "library_section": "Classical",
    }
    assert archive_genres.classify(["electronic; hardcore", "exotic custom tag"]) == {
        "genres": "Electronic; Hardcore", "library_section": "Popular",
    }


def test_no_inferred_historical_period_or_artist_genre():
    assert archive_genres.classify([], profile="classical") == {
        "genres": "Classical", "library_section": "Classical",
    }
    assert archive_genres.classify(["some microgenre", "concerted piano"], profile=None) == {
        "genres": "", "library_section": "Unclassified",
    }


def test_unknown_genre_does_not_mutate_album_or_index(tmp_path, monkeypatch):
    root = tmp_path / "archive"
    album = root / "Händel" / "[CAT1] Water Music (1999) [11111111]"
    album.mkdir(parents=True)
    manifest = {
        "status": "published_verified",
        "release_id": "11111111-1111-1111-1111-111111111111",
        "profile": "classical",
        "files": [{"filename": "01 - Work.flac", "track": 1}],
    }
    (album / "manifest.json").write_text(json.dumps(manifest))
    expected = (album / "manifest.json").read_bytes()
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(root))
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(config / "catalog.sqlite3"))
    assert catalog.import_published()["imported"] == 1
    classical = catalog.list_items(section="Classical")
    assert classical["total"] == 1
    assert classical["items"][0]["genres"] == "Classical"
    assert catalog.list_items(section="Popular")["total"] == 0
    assert catalog.list_items(search="Classical")["total"] == 1
    with pytest.raises(catalog.CatalogError):
        catalog.list_items(section="Classical'; DROP TABLE archive_items")
    assert (album / "manifest.json").read_bytes() == expected


def test_collection_ui_has_library_selection_and_genre_search():
    html = TestClient(app).get("/").text
    assert 'id="collection-section"' in html
    assert "'Genres','Library'" in html
