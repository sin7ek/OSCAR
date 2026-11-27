import threading
import time

import pytest
from fastapi.testclient import TestClient

from oscar import external_verification_ui as web
from oscar.api import app

ROUTE = "/api/collection/external-verification"
TOKEN = "a" * 32
AUTH = {"X-OSCAR-RIP-TOKEN": TOKEN}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "music"
    root.mkdir()
    album = root / "Label" / "Album [123]"
    album.mkdir(parents=True)
    (root / ".hidden").mkdir()
    (root / "linked").symlink_to(album)
    monkeypatch.setenv("OSCAR_EXTERNAL_LIBRARY_ROOT", str(root))
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "0")
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    monkeypatch.setattr(web, "_JOB", {})
    return TestClient(app), album


def test_browse_is_authenticated_and_stays_inside_library(setup, monkeypatch):
    client, _ = setup
    assert client.get(ROUTE + "/folders").status_code == 403
    assert client.post(ROUTE, json={"folder": "Label/Album [123]"}).status_code == 403
    assert client.get(ROUTE).status_code == 403
    assert client.get(ROUTE + "/folders", headers=AUTH).json() == {
        "folder": "", "folders": ["Label"],
    }
    assert client.get(ROUTE + "/folders", params={"folder": "Label"}, headers=AUTH).json() == {
        "folder": "Label", "folders": ["Album [123]"],
    }
    for folder in ("../outside", "/etc", "Label/../Label", "Label//Album [123]", "linked", ".hidden"):
        assert client.get(ROUTE + "/folders", params={"folder": folder}, headers=AUTH).status_code == 409
        assert client.post(ROUTE, json={"folder": folder}, headers=AUTH).status_code == 409
    monkeypatch.delenv("OSCAR_EXTERNAL_LIBRARY_ROOT")
    response = client.get(ROUTE + "/folders", headers=AUTH)
    assert response.status_code == 409
    assert "OSCAR_EXTERNAL_LIBRARY_ROOT" in response.json()["detail"]


def _wait_for_result(client):
    for _ in range(100):
        result = client.get(ROUTE, headers=AUTH).json()
        if result["status"] != "running":
            return result
        time.sleep(0.01)
    pytest.fail("Verifier did not return a final status")


def test_background_check_returns_per_disc_summary(setup, monkeypatch):
    client, album = setup
    active = threading.Event()
    finish = threading.Event()

    def verify(path):
        assert path == album
        active.set()
        assert finish.wait(3)
        return {
            "source_type": "external", "status": "database_matched_candidate_layout",
            "disc_total_declared": True, "assumed_single_disc": False,
            "discs": [{
                "disc": 1, "integrity": "passed", "file_integrity": {"01.flac": "passed"},
                "files_sha256": {"01.flac": "a" * 64},
                "track_total_declared": True,
                "ctdb": {"status": "matched", "confidence": 5, "total": 7},
            }],
        }

    monkeypatch.setattr(web.external_verification, "verify", verify)
    album_path = {"folder": "Label/Album [123]"}
    try:
        response = client.post(ROUTE, json=album_path, headers=AUTH)
        assert response.status_code == 200
        assert active.wait(1)
        initial = response.json()
        assert client.get(ROUTE, headers=AUTH).json() == initial
        assert client.post(ROUTE, json=album_path, headers=AUTH).status_code == 409
    finally:
        finish.set()
    completed = _wait_for_result(client)
    assert completed["id"] == initial["id"]
    assert completed["status"] == "completed"
    assert completed["result"]["discs"] == [{
        "disc": 1, "passed": 1, "tracks": 1, "integrity": "passed", "issues": {},
        "track_total_declared": True, "ctdb": {"status": "matched", "confidence": 5, "total": 7},
    }]


def test_worker_failure_is_reported_and_retry_is_possible(setup, monkeypatch):
    client, _ = setup

    def verify(_):
        raise ValueError("No FLAC files found in the album")

    monkeypatch.setattr(web.external_verification, "verify", verify)
    body = {"folder": "Label/Album [123]"}
    first = client.post(ROUTE, json=body, headers=AUTH).json()
    result = _wait_for_result(client)
    assert result["status"] == "failed"
    assert result["error"] == "No FLAC files found in the album"
    second = client.post(ROUTE, json=body, headers=AUTH).json()
    assert first["id"] != second["id"]
    assert _wait_for_result(client)["status"] == "failed"


def test_collection_has_external_verification_controls(setup):
    client, _ = setup
    html = client.get("/").text
    assert "Verify an existing FLAC album" in html
    assert "Verify this album against CTDB" in html
    assert "Show latest check" in html
