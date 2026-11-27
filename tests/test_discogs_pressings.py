import json
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

from oscar.discogs_readonly import search_pressings


def test_discogs_compares_pressing_identifiers_by_variant(monkeypatch):
    monkeypatch.setenv("OSCAR_DISCOGS_PAT", "test_token_not_a_secret")

    def opener(request, timeout):
        url = urlsplit(request.full_url)
        if url.path == "/database/search":
            assert parse_qs(url.query)["barcode"] == ["093624590125"]
            assert parse_qs(url.query)["format"] == ["CD"]
            payload = {"results": [{"id": 443973}], "pagination": {"items": 1}}
        else:
            assert url.path == "/releases/443973"
            payload = {
                "id": 443973, "formats": [{"name": "CD"}],
                "identifiers": [
                    {"type": "Matrix / Runout", "value": "936245901-2.2 WME",
                     "description": "Variant 14"},
                    {"type": "Mastering SID Code", "value": "IFPI L011",
                     "description": "Variant 14"},
                    {"type": "Mould SID Code", "value": "IFPI 0545",
                     "description": "Variant 2"},
                ],
            }
        return BytesIO(json.dumps(payload).encode())

    data = search_pressings(catalog="9362-45901-2", barcode="0 9362-45901-2 5",
                           matrix="936245901-2.2 WME", mastering_sid="IFPI L011",
                           mould_sid="IFPI 0545", opener=opener)
    first, second = data["releases"][0]["variants"]
    assert first["comparison"] == {"Matrix / Runout": "matches",
                                   "Mastering SID Code": "matches",
                                   "Mould SID Code": "not_documented"}
    assert second["comparison"]["Matrix / Runout"] == "not_documented"
    assert second["comparison"]["Mould SID Code"] == "matches"


def test_combined_search_inspects_past_first_five_and_includes_known_id(monkeypatch):
    monkeypatch.setenv("OSCAR_DISCOGS_PAT", "test_token_not_a_secret")
    queries = []
    ids = [11725689, 3105625, 3783070, 39063929, 4475220, 4709815]

    def opener(request, timeout):
        url = urlsplit(request.full_url)
        if url.path == "/database/search":
            query = parse_qs(url.query)
            queries.append(query)
            assert query["per_page"] == ["20"]
            payload = {"results": [{"id": n} for n in ids], "pagination": {"items": len(ids)}}
        else:
            release_id = int(url.path.rsplit("/", 1)[1])
            payload = {"id": release_id, "formats": [{"name": "CD"}], "identifiers": [
                {"type": "Barcode", "value": "3 259180 002527"},
                {"type": "Matrix / Runout", "value": "800 025-2 02", "description": "Variant 1"},
            ]}
        return BytesIO(json.dumps(payload).encode())

    values = {"catalog": "800 025-2", "barcode": "3259180002527",
              "matrix": "800 025-2 02", "mastering_sid": "", "mould_sid": ""}
    data = search_pressings(**values, expanded=True, opener=opener)
    assert data["releases"][-1]["id"] == 4709815
    assert queries[0]["barcode"] == ["3259180002527"]
    assert "catno" not in queries[0]
    data = search_pressings(**values, discogs_release="https://www.discogs.com/release/4709815-Jean-Michel-Jarre-Equinoxe",
                           expanded=True, opener=opener)
    assert data["releases"][0]["id"] == 4709815
    assert len(data["releases"]) == len(ids)
