"""Local OSCAR catalog, OpenDocument export and read-only Discogs tests."""
import csv
import io
import json
import sqlite3
import xml.etree.ElementTree as ET
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient

from oscar import collection_catalog as catalog
from oscar import discogs_readonly as discogs
from oscar.api import app

RELEASE = "4b370e6c-e6d2-36a5-8c47-5337a2d77d69"


@pytest.fixture
def archive(tmp_path, monkeypatch):
    root = tmp_path / "archive"
    album = root / "Anastacia" / "[504757 2] Freak of Nature (2001) [4b370e6c]"
    album.mkdir(parents=True)
    manifest = {"status": "published_verified", "release_id": RELEASE,
                "files": [{"track": i, "filename": f"{i:02}.flac"} for i in range(1, 13)]}
    (album / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    db = tmp_path / "config"
    db.mkdir()
    monkeypatch.setenv("OSCAR_ARCHIVE_ROOT", str(root))
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(db / "catalog.sqlite3"))
    return root, album, db


def test_import_is_idempotent_and_never_edits_archive(archive):
    root, album, _ = archive
    original = (album / "manifest.json").read_bytes()
    assert catalog.import_published()["imported"] == 1
    assert catalog.import_published()["imported"] == 0
    rows = catalog.list_items()
    assert rows["total"] == 1
    assert rows["items"][0]["catalog_number"] == "504757 2"
    assert rows["items"][0]["track_count"] == 12
    assert (album / "manifest.json").read_bytes() == original


def test_sort_and_filter_local_catalog(archive):
    catalog.import_published()
    assert catalog.list_items(search="Anastacia")["total"] == 1
    assert catalog.list_items(search="no match")["total"] == 0
    assert catalog.list_items(sort_by="year", descending=True)["total"] == 1
    with pytest.raises(catalog.CatalogError):
        catalog.list_items(sort_by="artist; DROP TABLE archive_items")


def test_csv_and_ods_round_trip_unicode_and_escape_formulas(archive):
    catalog.import_published()
    db = sqlite3.connect(catalog.database_path())
    db.execute("UPDATE archive_items SET artist=?, title=?",
               ("Händel", "=HYPERLINK(\"http://example.com\")"))
    db.commit()
    db.close()
    csv_bytes = catalog.export_csv()
    text = csv_bytes.decode("utf-8-sig")
    values = list(csv.DictReader(io.StringIO(text)))
    assert values[0]["artist"] == "Händel"
    assert values[0]["title"].startswith("'=HYPERLINK")
    ods = catalog.export_ods()
    with ZipFile(io.BytesIO(ods)) as z:
        assert z.namelist()[0] == "mimetype"
        assert z.read("mimetype") == b"application/vnd.oasis.opendocument.spreadsheet"
        root = ET.fromstring(z.read("content.xml"))
        xml = ET.tostring(root, encoding="unicode")
        assert "Händel" in xml and "'=HYPERLINK" in xml
        assert "Collection" in xml and "Export Metadata" in xml


def test_unknown_or_unpublished_manifests_ignored(archive):
    root, album, _ = archive
    (album / "manifest.json").write_text('{"status":"staging"}')
    assert catalog.import_published()["imported"] == 0
    assert catalog.list_items()["total"] == 0


def test_archive_import_does_not_follow_symlink_file(archive, tmp_path):
    root, album, _ = archive
    folder = root / "Trick" / "Release"
    folder.mkdir(parents=True)
    (folder / "manifest.json").symlink_to(album / "manifest.json")
    assert catalog.import_published()["imported"] == 1
    assert catalog.list_items()["total"] == 1


def test_ui_and_collection_endpoints_present(archive, monkeypatch):
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "0")
    page = TestClient(app).get("/").text
    assert "Collection Library (local)" in page
    assert "collection-ods" in page
    assert "discogs-check" in page
    assert TestClient(app).get("/api/collection").status_code == 403


class MockResponse:
    def __init__(self, obj):
        self.obj = obj
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, limit):
        return json.dumps(self.obj).encode()


def test_discogs_token_in_header_and_never_in_response(monkeypatch):
    token = "A"*48
    monkeypatch.setenv("OSCAR_DISCOGS_PAK", token)
    seen = []
    def opener(req, timeout):
        seen.append(req)
        if req.full_url.endswith("/oauth/identity"):
            return MockResponse({"username": "oscar_user"})
        return MockResponse({"folders": [{"id": 0, "name": "All", "count": 3},
                                         {"id": 1, "name": "Hardcore", "count": 2}]})
    result = discogs.account_summary(opener=opener)
    assert result["connected"] and len(result["folders"]) == 2
    assert seen[0].get_header("Authorization") == "Discogs token=" + token
    assert token not in json.dumps(result)
    assert seen[1].full_url.endswith("/users/oscar_user/collection/folders")


def test_discogs_absent_token_does_not_call_provider(monkeypatch):
    monkeypatch.delenv("OSCAR_DISCOGS_PAK", raising=False)
    assert not discogs.account_summary()["connected"]
