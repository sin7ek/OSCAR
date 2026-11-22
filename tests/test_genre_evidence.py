"""Genre Evidence v1: independent-source agreement, safe provenance and no writes."""
import copy
import json
import pytest
from fastapi.testclient import TestClient
from oscar import genre_evidence as g
from oscar.api import app


def claim(provider, values, *, group=None):
    return g._claim(provider, "release", f"https://example.com/{provider}",
                    values, group=group)


def test_one_musicbrainz_vote_not_called_secure_confidence():
    report = g.analyze([claim("musicbrainz", ["pop"])], workflow="secure")
    assert report["independent_sources_with_genres"] == 1
    assert report["findings"][0]["genre"] == "Pop"
    assert report["findings"][0]["confidence"] == "limited"
    assert report["findings"][0]["needs_review"] is True
    assert report["automatic_archive_write"] is False


def test_three_agreeing_sources_are_high_agreement_not_probability():
    report = g.analyze([
        claim("musicbrainz", ["jazz"]),
        claim("discogs", ["Jazz"]),
        claim("review", ["Jazz"]),
        claim("qobuz", ["Blues"]),
    ], workflow="best_guess")
    jazz = next(x for x in report["findings"] if x["genre"] == "Jazz")
    assert jazz["agreement_fraction"] == "3/4"
    assert jazz["agreement_percent"] == 75.0
    assert jazz["confidence"] == "high"
    assert jazz["needs_review"] is False
    assert report["automatic_archive_write"] is False


def test_no_genre_is_abstention_not_vote_against():
    report = g.analyze([
        claim("musicbrainz", []),
        claim("discogs", ["Jazz"]),
        claim("review", ["jazz"]),
        claim("qobuz", ["Jazz"]),
    ])
    assert report["independent_sources_with_genres"] == 3
    assert report["sources_without_applicable_genres"] == 1
    assert report["findings"][0]["agreement_fraction"] == "3/3"


def test_balanced_credible_sources_remain_in_conflict():
    report = g.analyze([claim("musicbrainz", ["Rock"]),
                        claim("discogs", ["Jazz"])])
    assert report["outcome"] == "review_required"
    assert {f["confidence"] for f in report["findings"]} == {"conflict"}


def test_duplicate_positive_provider_cluster_never_double_counts():
    with pytest.raises(g.GenreEvidenceError, match="same provider"):
        g.analyze([
            g._claim("musicbrainz", "release", "https://example.com/a", ["Pop"]),
            g._claim("musicbrainz", "release_group", "https://example.com/b", ["Pop"]),
        ])


def test_unknown_genres_not_invented():
    report = g.analyze([
        claim("musicbrainz", ["totally invented microgenre"]),
        claim("discogs", []),
    ])
    assert report["outcome"] == "unclassified"
    assert report["findings"] == []


def test_musicbrainz_exact_release_votes_and_release_group_fallback(monkeypatch):
    release_id = "4b370e6c-e6d2-36a5-8c47-5337a2d77d69"
    group_id = "11111111-2222-3333-4444-555555555555"
    def fake_fetch(request, **kwargs):
        if "/release-group/" in request.full_url:
            return {"id": group_id, "genres": [
                {"name": "pop", "count": 5},
                {"name": "unreviewed noise", "count": 6},
            ]}
        return {"id": release_id, "release-group": {"id": group_id}, "genres": [
            {"name": "rock", "count": 0},
        ]}
    monkeypatch.setattr(g, "fetch_json", fake_fetch)
    claims = g.musicbrainz_claims(release_id)
    assert claims[0]["genres"] == ["Pop"]
    assert claims[0]["scope"] == "release_group"
    assert claims[1]["status"] == "no_genre"
    assert g.analyze(claims)["independent_sources_with_genres"] == 1
    assert claims[0]["provider_details"]["positive_genre_votes"][0]["votes"] == 5


def test_musicbrainz_claim_never_follows_unrelated_release(monkeypatch):
    monkeypatch.setattr(g, "fetch_json", lambda *args, **kwargs: {
        "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"})
    with pytest.raises(g.GenreEvidenceError, match="identity differs"):
        g.musicbrainz_claims("4b370e6c-e6d2-36a5-8c47-5337a2d77d69")


def test_discogs_exact_catalog_cd_required(monkeypatch):
    def provider(path, **kwargs):
        return {
            "id": 12345,
            "genres": ["Jazz"], "styles": ["Vocal Jazz"],
            "labels": [{"catno": "CGi2010"}],
            "formats": [{"name": "CD"}],
            "identifiers": [{"type": "Barcode", "value": "1234567890123"}],
        }
    monkeypatch.setattr(g.discogs, "_get", provider)
    matched = g.discogs_claim(12345, catalog="CGi2010", barcode="1234567890123")
    assert matched["genres"] == ["Jazz"]
    assert matched["status"] == "classified"
    assert matched["provider_details"]["matched_barcode"] is True
    mismatched = g.discogs_claim(12345, catalog="WRONG")
    assert mismatched["status"] == "edition_unverified"
    assert mismatched["genres"] == []


def test_genre_evidence_api_requires_auth_and_has_ui(monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_TOKEN", "0123456789abcdef0123456789abcdef")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    assert client.post("/api/collection/genre-evidence/preview",
        json={"archive_path": "/archive/example"}).status_code == 403
    result = client.post("/api/collection/genre-evidence/preview",
        json={"archive_path": "/archive/example", "workflow": "guess_secure"},
        headers={"X-OSCAR-RIP-TOKEN": "0123456789abcdef0123456789abcdef"})
    assert result.status_code == 422
    html = client.get("/").text
    assert 'id="genre-evidence-preview"' in html
    assert "Compare genre sources (read-only)" in html
