"""Classical v2 must not invent CD sections or ship test-disc controls."""
from fastapi.testclient import TestClient
import pytest

from oscar import classical_v2
from oscar.api import app


def test_empty_sections_are_valid_and_unassigned():
    assert classical_v2.validate_sections([], 32) == ([], {})


def test_sections_still_require_full_coverage():
    with pytest.raises(classical_v2.ClassicalError, match="cover every track"):
        classical_v2.validate_sections([{"start": 1, "end": 2, "name": "First"}], 3)


def test_classical_v2_no_sections_preserves_works_and_does_not_set_tag(monkeypatch):
    source = {
        "release_id": "423f636d-742d-47b0-9ba2-51515a6fdfd2",
        "fingerprint": "fake-fingerprint",
        "tracks": [
            {"number": 1, "original_file": "audio/01 - Song.flac",
             "tags": {"TITLE": ["Song"], "WORK": ["Three Japanese Lyrics"], "GROUPING": ["Song Cycle"]},
             "works": [{"id": "work-id", "parents": [{"id": "parent-id", "title": "Three Japanese Lyrics"}]}],
             "performers": [], "composers": []},
            {"number": 2, "original_file": "audio/02 - Other.flac",
             "tags": {"TITLE": ["Other"], "WORK": ["Other Work"]},
             "works": [], "performers": [], "composers": []},
        ],
    }
    monkeypatch.setattr(classical_v2, "_validated_source",
                        lambda job_id, copy_id: (None, source, {"track_count": 2}))
    monkeypatch.setattr(classical_v2, "_alias", lambda *args: None)
    preview = classical_v2.create_preview("a"*32, "b"*32, [], {})
    assert preview["sections"] == []
    assert all(t["release_section"] is None for t in preview["tracks"])
    assert all("RELEASE_SECTION" not in t["tags"] for t in preview["tracks"])
    assert all("GROUPING" not in t["tags"] for t in preview["tracks"])
    assert preview["tracks"][0]["tags"]["WORK_PARENT"] == ["Three Japanese Lyrics"]
    assert preview["tracks"][1]["tags"]["WORK"] == ["Other Work"]
    assert preview["track_count"] == 2


def test_classical_preview_api_accepts_empty_sections_before_auth(monkeypatch):
    from oscar import api
    monkeypatch.setattr(api, "_rip_auth", lambda *args, **kwargs: None)
    monkeypatch.setattr(classical_v2, "create_preview",
                        lambda job, copy, sections, movements: {
                            "sections": sections, "movements": movements})
    response = TestClient(app).post(
        "/api/rip/jobs/" + "a"*32 + "/metadata/copies/" + "b"*32 +
        "/classical-v2/preview", json={"sections": [], "movements": {}})
    assert response.status_code == 200
    assert response.json()["sections"] == []


def test_browser_has_no_personal_disc_example_and_explains_optional_sections():
    html = TestClient(app).get("/").text
    assert "v2-handel-example" not in html
    assert "review-handel-example" not in html
    assert "Fill example for first Handel CD" not in html
    assert "Sections are not required" in html
