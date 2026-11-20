"""Bounded, resumable-in-database archive-wide metadata scans.

The short-lived scan worker is process-local; durable proposals and human
decisions live in catalog.sqlite3 and survive restart. Failed individual albums
never stop the rest. No staging files or archive writes are performed.
"""
import re
import threading
import uuid
from datetime import datetime, timezone

from oscar import archive_metadata_scan as scanner, collection_catalog as catalog

_LOCK = threading.Lock()
_JOBS = {}
_RUNNING = None
_MAX_ALBUMS = 10000
_MAX_ERRORS = 100


def _leaves():
    """Only Collection-indexed archive leaves, bounded and deterministically ordered.

    Existing catalog import discovers published manifests. Explicitly require an
    import before a full scan so arbitrary folders are never inferred as releases.
    """
    with catalog._connect() as db:
        rows = db.execute(
            "SELECT archive_path FROM archive_items ORDER BY archive_path LIMIT ?",
            (_MAX_ALBUMS + 1,),
        ).fetchall()
    if len(rows) > _MAX_ALBUMS:
        raise scanner.ScanError("Archive exceeds the per-run safety limit; scan smaller batches")
    if not rows:
        raise scanner.ScanError("Collection is empty; import published archive records first")
    return [row["archive_path"] for row in rows]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _work(scan_id, paths, mode, *, scanner_fn=None):
    global _RUNNING
    scan_fn = scanner_fn or scanner.scan
    try:
        for path in paths:
            try:
                result = scan_fn(mode, path)
                with _LOCK:
                    job = _JOBS[scan_id]
                    job["detected"] += result["detected"]
                    job["suppressed"] += result["suppressed"]
                    job["completed"] += 1
            except Exception as exc:
                with _LOCK:
                    job = _JOBS[scan_id]
                    job["failed"] += 1
                    if len(job["errors"]) < _MAX_ERRORS:
                        job["errors"].append({
                            "archive_path": path,
                            "error": f"{type(exc).__name__}: {exc}"[:260],
                        })
            finally:
                with _LOCK:
                    _JOBS[scan_id]["processed"] += 1
        with _LOCK:
            _JOBS[scan_id]["status"] = "completed_with_errors" if _JOBS[scan_id]["failed"] else "completed"
            _JOBS[scan_id]["finished_at"] = _now()
    finally:
        with _LOCK:
            if _RUNNING == scan_id:
                _RUNNING = None


def start(mode):
    global _RUNNING
    if mode not in ("additions", "changes"):
        raise scanner.ScanError("Select metadata additions or changes")
    if not scanner.musicbrainz.lookup_enabled():
        raise scanner.ScanError("MusicBrainz lookups are disabled")
    with _LOCK:
        if _RUNNING is not None:
            raise scanner.ScanError("An archive-wide metadata scan is already running")
        # The collection query runs before a worker is started; no partial scan
        # is registered if the catalog is uninitialized or unexpectedly large.
        paths = _leaves()
        scan_id = uuid.uuid4().hex
        _JOBS[scan_id] = {
            "scan_id": scan_id, "mode": mode, "status": "running",
            "total": len(paths), "processed": 0, "completed": 0,
            "failed": 0, "detected": 0, "suppressed": 0, "errors": [],
            "started_at": _now(), "finished_at": None,
            "note": "Proposals and decisions are durable; worker progress is not persisted across container restarts.",
        }
        _RUNNING = scan_id
    worker = threading.Thread(target=_work, args=(scan_id, paths, mode),
                              name="oscar-archive-scan-"+scan_id[:8], daemon=True)
    try:
        worker.start()
    except Exception:
        with _LOCK:
            _JOBS.pop(scan_id, None)
            _RUNNING = None
        raise
    return status(scan_id)


def status(scan_id):
    if not isinstance(scan_id, str) or not re.fullmatch(r"[0-9a-f]{32}", scan_id):
        raise scanner.ScanError("Invalid archive metadata scan ID")
    with _LOCK:
        entry = _JOBS.get(scan_id)
        if entry is None:
            raise scanner.ScanError("Scan job not found in this worker process")
        return {**entry, "errors": list(entry["errors"])}


def current():
    with _LOCK:
        active = _RUNNING
    return status(active) if active else {"status": "idle"}
