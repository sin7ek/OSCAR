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
