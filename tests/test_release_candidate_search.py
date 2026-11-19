"""Release search must not mistake catalog/title discovery for physical validation."""
import json
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from oscar import musicbrainz
from oscar.api import app


RELEASE = "4b370e6c-e6d2-36a5-8c47-5337a2d77d69"


class Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, max_bytes):
        return json.dumps({"releases": [{
            "id": RELEASE, "title": "Freak of Nature",
            "date": "2001-11-26", "barcode": "5099750475720",
            "artist-credit": [{"name": "Anastacia"}],
            "label-info": [{"label": {"name": "Epic"}, "catalog-number": "504757 2"}],
            "score": 100,
        }]}).encode()


def test_catalog_search_is_explicitly_only_discovery(monkeypatch):
    import oscar.mb_client as mb_client
    seen = []
    def opener(request, timeout):
        seen.append(request.full_url)
        return Response()
    monkeypatch.setattr(mb_client.mb.time, "monotonic", lambda: 900000.0)
    monkeypatch.setattr(mb_client.mb.time, "sleep", lambda duration: None)
    data = musicbrainz.search_release_candidates(catalog_number="CCC 97001", opener=opener)
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)
    assert query["query"] == ['catno:"CCC 97001"']
    assert data["query_kind"] == "catno"
    assert data["requires_review"] is True
    assert data["disc_id_compared"] is False
    assert data["physical_edition_approved"] is False
    assert data["releases"][0]["id"] == RELEASE
    assert data["releases"][0]["labels"][0]["catalog_number"] == "504757 2"


def test_title_search_does_not_claim_a_cd_match(monkeypatch):
    import oscar.mb_client as mb_client
    seen = []
    def opener(request, timeout):
        seen.append(request.full_url)
        return Response()
    monkeypatch.setattr(mb_client.mb.time, "monotonic", lambda: 900000.0)
    monkeypatch.setattr(mb_client.mb.time, "sleep", lambda duration: None)
    data = musicbrainz.search_release_candidates(title="Essential Dance Traxx", opener=opener)
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(seen[0]).query)
    assert query["query"] == ['release:"Essential Dance Traxx"']
    assert not data["disc_id_compared"]


def test_search_input_validation():
    for value in ("", "x" * 101, "evil\nquery"):
        with pytest.raises(musicbrainz.MusicBrainzError):
            musicbrainz.search_release_candidates(catalog_number=value)
    with pytest.raises(musicbrainz.MusicBrainzError):
        musicbrainz.search_release_candidates(catalog_number="CCC 97001", title="Essential Dance Traxx")
    with pytest.raises(musicbrainz.MusicBrainzError):
        musicbrainz.search_release_candidates()


def test_release_search_respects_musicbrainz_opt_in(monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_MUSICBRAINZ", raising=False)
    response = TestClient(app).get("/api/release-search", params={"catalog_number": "CCC 97001"})
    assert response.status_code == 403


def test_release_search_panel_has_both_routes():
    html = TestClient(app).get("/").text
    assert 'id="catalog-search-button"' in html
    assert 'id="title-search-button"' in html
    assert "No physical edition or Disc ID has been verified." in html
