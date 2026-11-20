"""Archive-wide metadata scans and provider token naming regression tests."""
import json
import threading

import pytest
from fastapi.testclient import TestClient

from oscar import archive_metadata_bulk as bulk
from oscar.api import app


@pytest.fixture(autouse=True)
def reset_bulk_job():
    with bulk._LOCK:
        bulk._JOBS.clear()
        bulk._RUNNING = None
    yield
    with bulk._LOCK:
        bulk._JOBS.clear()
        bulk._RUNNING = None


def test_bulk_scan_processes_every_indexed_album_and_survives_individual_failure(monkeypatch):
    paths = ["/archive/good1", "/archive/bad", "/archive/good2"]
    monkeypatch.setattr(bulk, "_leaves", lambda: paths)
    monkeypatch.setattr(bulk.scanner.musicbrainz, "lookup_enabled", lambda: True)
    calls = []
    def scan(mode, path):
        calls.append((mode, path))
        if path == paths[1]:
            raise bulk.scanner.ScanError("MusicBrainz unavailable for this album")
        return {"detected": 2, "suppressed": 1}
    monkeypatch.setattr(bulk.scanner, "scan", scan)
    result = bulk.start("additions")
    scan_id = result["scan_id"]
    job = bulk.status(scan_id)
    # Join a real worker to avoid time-based flakes.
    for thread in threading.enumerate():
        if thread.name == "oscar-archive-scan-"+scan_id[:8]:
            thread.join(timeout=5)
    job = bulk.status(scan_id)
    assert job["status"] == "completed_with_errors"
    assert (job["total"], job["processed"], job["completed"], job["failed"]) == (3,3,2,1)
    assert (job["detected"], job["suppressed"]) == (4,2)
    assert len(job["errors"]) == 1
    assert calls == [("additions", p) for p in paths]
    assert bulk.current()["status"] == "idle"


def test_bulk_rejects_concurrent_jobs(monkeypatch):
    started = threading.Event()
    finish = threading.Event()
    monkeypatch.setattr(bulk, "_leaves", lambda: ["/archive/test"])
    monkeypatch.setattr(bulk.scanner.musicbrainz, "lookup_enabled", lambda: True)
    def blocking(mode, path):
        started.set()
        finish.wait(timeout=5)
        return {"detected": 0, "suppressed": 0}
    monkeypatch.setattr(bulk.scanner, "scan", blocking)
    try:
        run = bulk.start("changes")
        assert started.wait(2)
        with pytest.raises(bulk.scanner.ScanError, match="already running"):
            bulk.start("additions")
        assert bulk.current()["scan_id"] == run["scan_id"]
    finally:
        finish.set()
    for t in threading.enumerate():
        if t.name == "oscar-archive-scan-"+run["scan_id"][:8]:
            t.join(timeout=5)
    assert bulk.status(run["scan_id"])["status"] == "completed"


def test_bulk_requires_index_and_has_explicit_bound(monkeypatch, tmp_path):
    from oscar import collection_catalog as catalog
    parent = tmp_path / "config"
    parent.mkdir()
    monkeypatch.setenv("OSCAR_CATALOG_DB", str(parent / "catalog.sqlite3"))
    monkeypatch.setattr(bulk.scanner.musicbrainz, "lookup_enabled", lambda: True)
    with pytest.raises(bulk.scanner.ScanError, match="Collection is empty"):
        bulk.start("additions")
    monkeypatch.setattr(bulk, "_leaves", lambda: (_ for _ in ()).throw(
        bulk.scanner.ScanError("safety limit")))
    with pytest.raises(bulk.scanner.ScanError, match="safety limit"):
        bulk.start("changes")


def test_bulk_auth_and_primary_collection_buttons(monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_TOKEN", "0123456789abcdef0123456789abcdef")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    assert client.post("/api/collection/archive-metadata/scan-all",
                       json={"mode": "additions"}).status_code == 403
    assert client.get("/api/collection/archive-metadata/scan-all/status").status_code == 403
    html = client.get("/").text
    assert "Scan archive for metadata additions" in html
    assert "runArchiveBulkScan('additions')" in html
    assert "runArchiveBulkScan('changes')" in html
    assert "Legacy Collection label enrichment (advanced)" in html
    assert "OSCAR_DISCOGS_PAT" in html
    assert "OSCAR_DISCOGS_PAK" not in html
