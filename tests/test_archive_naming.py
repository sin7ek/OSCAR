"""Archive naming previews must remain safe and never write to a share."""
import pytest
from fastapi.testclient import TestClient

from oscar.api import app
from oscar.archive_naming import archive_preview


def test_classical_single_composer_and_release_catalogue():
    data=archive_preview(profile="classical",album_title="Water Music / Royal Fireworks",
         release_year="1999",catalog_number="ES 99220",
         composers=["George Frideric Handel"], track_number=2,
         track_title="Menuet I")
    assert data["directory"]=="Classical/George Frideric Handel/[ES 99220] Water Music Royal Fireworks (1999)"
    assert data["track_path"].endswith("/01-02 - Menuet I.flac")


def test_classical_multiple_composers_not_misassigned():
    data=archive_preview(profile="classical",album_title="Great Works",
         composers=["Stravinsky","Tchaikovsky"])
    assert data["directory"]=="Classical/Various Composers/Great Works"


def test_no_catalogue_no_fake_placeholder():
    data=archive_preview(profile="album",album_title="Unknown release",
         album_artist="Example")
    assert data["directory"]=="Example/Unknown release"
    assert "[" not in data["directory"]


def test_compilation_filename_uses_track_artist():
    data=archive_preview(profile="compilation",album_title="Hardcore",
         catalog_number="RUF 001",track_artist="Artist X",track_title="Track Y",
         disc_number=2, track_number=7)
    assert data["track_path"]=="Various Artists/[RUF 001] Hardcore/02-07 - Artist X - Track Y.flac"


def test_untrusted_paths_are_components_not_destinations():
    data=archive_preview(profile="classical",album_title="../../some\\other",
         composers=["../Händel"],track_title="../../evil")
    assert ".." not in data["track_path"]
    assert not data["track_path"].startswith("/")


def test_preview_api_does_not_require_ripping(tmp_path,monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_RIPPING",raising=False)
    r=TestClient(app).post("/api/archive/name-preview",json={
        "profile":"classical","album_title":"Symphony no. 5",
        "composers":["Pyotr Ilyich Tchaikovsky"],
        "release_year":"1991","track_title":"I. Andante"
    })
    assert r.status_code==200
    assert "Classical/Pyotr Ilyich Tchaikovsky" in r.json()["track_path"]


def test_invalid_year_rejected():
    r=TestClient(app).post("/api/archive/name-preview",json={
       "profile":"album","album_title":"A","release_year":"../"
    })
    assert r.status_code==422
