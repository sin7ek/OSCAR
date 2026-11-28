import json

from fastapi.testclient import TestClient

from oscar import genre_evidence, web_genre_evidence as web
from oscar.api import app


def source(title, text, key="review"):
    return {"title": title, "url": f"https://example.org/{key}", "content": text}


def test_local_preview_retains_explicit_album_and_band_scopes(monkeypatch):
    monkeypatch.setattr(web.genre_vocabulary, "names", lambda: {
        "thrash metal": "Thrash Metal", "alternative pop": "Alternative Pop",
    })
    artist, title = "Flotsam and Jetsam", "Rats in the Temple"
    rows = [
        source(f"{artist} – {title}", f"{title} is a fierce, focused thrash metal triumph.", "album"),
        source(f"{artist} – {title}", "Arizona-based power/thrash metal trailblazers had careers.", "band"),
        source(f"{artist} – {title}", "This aggressive album sounds loud."),
        {**source(f"{artist} – {title}", "This is a jazz album."), "url": "javascript:alert(1)"},
    ]
    calls = []

    def post(url, data, **kwargs):
        calls.append((url, data))
        if url.endswith("/search"):
            return {"results": rows}
        return {"message": {"content": json.dumps({"claims": [
            {"genre": "thrash metal", "evidence_id": 1, "scope": "band"},
            {"genre": "power/thrash metal", "evidence_id": 2, "scope": "album"},
            {"genre": "aggressive metal", "evidence_id": 3, "scope": "album"},
        ]})}}

    monkeypatch.setattr(web, "_post", post)
    result = web.preview({"artist": artist, "title": title, "archive_path": "/ignored"}, "local")
    assert [x["genre"] for x in result["claims"]] == ["Thrash Metal", "power/thrash metal"]
    assert [x["scope"] for x in result["claims"]] == ["album", "band"]
    assert all(x["scope_basis"] == "explicit_wording" for x in result["claims"])
    assert result["claims"][0]["evidence"] == rows[0]["content"]
    assert result["automatic_archive_write"] is False
    assert "/ignored" not in json.dumps(calls)


def test_alt_pop_and_empty_mahler_preview(monkeypatch):
    monkeypatch.setattr(web.genre_vocabulary, "names", lambda: {"alternative pop": "Alternative Pop"})
    responses = iter([
        {"results": [source("Nessa Barrett – Tough Love", "Read reviews of the Alt-Pop album.")]},
        {"message": {"content": "{malformed"}},
        {"results": [source("Mahler – Symphony No. 6 – Classical Music", "The orchestra plays well.")]},
        {"message": {"content": '{"claims":[{"genre":"Classical","scope":"album","evidence_id":1}]}' }},
    ])
    monkeypatch.setattr(web, "_post", lambda *args, **kwargs: next(responses))
    nessa = web.preview({"artist": "Nessa Barrett", "title": "Tough Love"}, "local")
    assert nessa["status"] == "analysis_unavailable"
    assert nessa["claims"][0]["genre"] == "Alternative Pop"
    assert nessa["claims"][0]["original_genre"] == "Alt-Pop"

    mahler = web.preview({"artist": "Mahler", "title": "Symphony No. 6"}, "local")
    assert mahler["status"] == "no_evidence"
    assert mahler["claims"] == []


def test_mistral_uses_only_identifiable_original_excerpts(monkeypatch):
    monkeypatch.setenv("OSCAR_AI_API_KEY", "fake")
    row = source("Nessa Barrett – Tough Love", "Tough Love is a dreamy art-pop experiment.")
    evidence = {"search-result://1": {**row, "description": row["content"]}}

    def post(url, data, **kwargs):
        assert url == "https://api.mistral.ai/v1/conversations"
        assert kwargs["token"] == "fake"
        assert data["tools"] == [{"type": "web_search"}] and data["store"] is False
        return {"outputs": [
            {"type": "tool.execution", "name": "web_search", "info": {"result": json.dumps(evidence)}},
            {"type": "message.output", "content": [
                {"type": "text", "text": json.dumps({"claims": [
                    {"genre": "art-pop", "quote": "a dreamy art-pop experiment", "scope": "album", "url": row["url"]},
                    {"genre": "metal", "quote": "a metal album", "scope": "album", "url": row["url"]},
                ]})},
            ]},
        ]}

    monkeypatch.setattr(web, "_post", post)
    result = web.preview({"artist": "Nessa Barrett", "title": "Tough Love"}, "mistral")
    assert len(result["claims"]) == 1
    assert result["claims"][0]["original_genre"] == "art-pop"
    assert result["claims"][0]["url"] == row["url"]


def test_web_api_requires_auth_and_opt_in(monkeypatch):
    token = "0123456789abcdef0123456789abcdef"
    monkeypatch.setenv("OSCAR_RIP_TOKEN", token)
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    monkeypatch.delenv("OSCAR_ENABLE_WEB_GENRE_EVIDENCE", raising=False)
    client = TestClient(app)
    path = "/api/collection/genre-evidence/web-preview"
    body = {"archive_path": "/archive/example", "provider": "mistral"}
    headers = {"X-OSCAR-RIP-TOKEN": token}
    assert client.post(path, json=body).status_code == 403
    assert client.post(path, json=body, headers=headers).status_code == 403
    monkeypatch.setenv("OSCAR_ENABLE_WEB_GENRE_EVIDENCE", "1")
    monkeypatch.setattr(genre_evidence, "indexed_archive", lambda value: (
        {"release_id": "release-id"}, {"artist": "Artist", "title": "Album"}))
    monkeypatch.setattr(web, "preview", lambda identity, provider: {
        "album": identity, "provider": provider, "automatic_archive_write": False,
    })
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["provider"] == "mistral"
    assert response.json()["musicbrainz_release_id"] == "release-id"
    assert 'id="web-genre-preview"' in client.get("/").text
