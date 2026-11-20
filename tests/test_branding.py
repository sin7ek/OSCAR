"""Branding remains presentation-only and safe when assets are absent."""
from fastapi.testclient import TestClient

from oscar.api import app
from oscar.web import PAGE


def test_branding_does_not_replace_navigation():
    for name in ("Go!", "Review", "Collection", "Settings"):
        assert name in PAGE
    assert 'id="oscar-tabs"' in PAGE
    assert 'src="/brand/OSCAR-header.png"' in PAGE
    assert 'id="oscar-brand-fallback"' in PAGE


def test_brand_assets_allowlist():
    client = TestClient(app)
    assert client.get("/brand/not-an-asset.png").status_code == 404
    assert client.get("/brand/../settings.json").status_code == 404


def test_brand_header_and_favicon_declared():
    assert '/brand/favicon-16.png' in PAGE
    assert '/brand/favicon-32.png' in PAGE
    assert '/brand/apple-touch-icon.png' in PAGE
    assert 'height:auto' in PAGE
