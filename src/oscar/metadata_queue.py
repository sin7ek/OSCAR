"""Durable retry queue for transient MusicBrainz alias lookup failures.

Only metadata MBIDs are persisted; no optical drive or archive file operations.
Multiple workers can safely claim a job using SQLite's write transaction and
recover an expired claim after a crash.
"""
import json
import os
import sqlite3
import time
from pathlib import Path

from oscar.settings import config_path

VALID_TYPES = {"artist", "work"}
MAX_ATTEMPTS = 8
LEASE_SECONDS = 180


def queue_path() -> Path:
    return Path(os.environ.get("OSCAR_METADATA_QUEUE_PATH",
                               str(config_path().parent / "metadata_queue.sqlite3")))


def connect(path=None):
    path = Path(path) if path is not None else queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=20000")
    db.execute("""CREATE TABLE IF NOT EXISTS metadata_jobs (
       entity_type TEXT NOT NULL,
       entity_id TEXT NOT NULL,
       status TEXT NOT NULL,
       attempts INTEGER NOT NULL DEFAULT 0,
       available_at REAL NOT NULL,
       lease_until REAL,
       last_error TEXT,
       created_at REAL NOT NULL,
       updated_at REAL NOT NULL,
       PRIMARY KEY(entity_type, entity_id)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS metadata_jobs_due ON metadata_jobs(status, available_at)")
    return db


def _validated(entity_type, entity_id):
    from oscar.aliases import _ID
    if entity_type not in VALID_TYPES or not isinstance(entity_id, str) or not _ID.fullmatch(entity_id):
        raise ValueError("Invalid MusicBrainz artist/work MBID")
    return entity_type, entity_id.lower()


def enqueue(entity_type, entity_id, *, error="", path=None, now=None):
    entity_type, entity_id = _validated(entity_type, entity_id)
    now = time.time() if now is None else now
    with connect(path) as db:
        # Deduplicate existing pending/running/completed jobs and do not
        # automatically reactivate failed jobs that exceeded the retry limit.
        db.execute("""INSERT OR IGNORE INTO metadata_jobs
          (entity_type,entity_id,status,attempts,available_at,last_error,created_at,updated_at)
          VALUES(?,?,'pending',0,?,?,?,?)""",
                   (entity_type, entity_id, now, str(error)[:300], now, now))
    return {"entity_type": entity_type, "entity_id": entity_id}


def claim(*, path=None, now=None):
    now = time.time() if now is None else now
    with connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("""SELECT * FROM metadata_jobs
          WHERE (status='pending' AND available_at<=?)
             OR (status='running' AND lease_until<=?)
          ORDER BY available_at ASC LIMIT 1""", (now, now)).fetchone()
        if row is None:
            return None
        db.execute("""UPDATE metadata_jobs SET status='running', lease_until=?,
          attempts=attempts+1, updated_at=? WHERE entity_type=? AND entity_id=?""",
                   (now + LEASE_SECONDS, now, row["entity_type"], row["entity_id"]))
        return {"entity_type": row["entity_type"], "entity_id": row["entity_id"],
                "attempts": row["attempts"] + 1}


def complete(entity_type, entity_id, *, path=None, now=None):
    entity_type, entity_id = _validated(entity_type, entity_id)
    now = time.time() if now is None else now
    with connect(path) as db:
        db.execute("""UPDATE metadata_jobs SET status='done', lease_until=NULL,
          last_error=NULL, updated_at=? WHERE entity_type=? AND entity_id=?
          AND status='running'""", (now, entity_type, entity_id))


def fail(entity_type, entity_id, attempts, error, *, transient=True, path=None, now=None):
    entity_type, entity_id = _validated(entity_type, entity_id)
    now = time.time() if now is None else now
    retry = transient and attempts < MAX_ATTEMPTS
    # Start at >= 90s to respect the MusicBrainz cooldown; cap at one hour.
    delay = min(3600, 90 * 2 ** max(0, attempts - 1))
    with connect(path) as db:
        db.execute("""UPDATE metadata_jobs SET status=?, available_at=?,
          lease_until=NULL, last_error=?, updated_at=?
          WHERE entity_type=? AND entity_id=? AND status='running'""",
          ("pending" if retry else "failed", now + delay if retry else now,
           str(error)[:300], now, entity_type, entity_id))


def summary(*, path=None):
    with connect(path) as db:
        counts = {row["status"]: row["n"] for row in
                  db.execute("SELECT status, count(*) AS n FROM metadata_jobs GROUP BY status")}
    return {name: counts.get(name, 0) for name in ("pending", "running", "done", "failed")}


def process_one(*, path=None, fetcher=None, now=None):
    """Run one due retry. Caller can invoke repeatedly from a worker thread."""
    from oscar.alias_cache import get_alias, _transient_failure
    from oscar.musicbrainz import MusicBrainzError
    job = claim(path=path, now=now)
    if not job:
        return False
    typ, ident, attempts = job["entity_type"], job["entity_id"], job["attempts"]
    try:
        kw = {"fetcher": fetcher} if fetcher is not None else {}
        result = get_alias(typ, ident, **kw)
        if result.get("cache_status") == "stale":
            raise MusicBrainzError("MusicBrainz temporarily unavailable (cooldown)")
    except MusicBrainzError as exc:
        fail(typ, ident, attempts, str(exc), transient=_transient_failure(exc),
             path=path, now=now)
    except Exception as exc:
        # Worker safety: unexpected exceptions retain retryability, never disappear.
        fail(typ, ident, attempts, type(exc).__name__, path=path, now=now)
    else:
        complete(typ, ident, path=path, now=now)
    return True


def worker_loop(stop_event, *, path=None):
    """Cooperative worker: serialized metadata fetches and clean shutdown."""
    while not stop_event.is_set():
        did_work = process_one(path=path)
        if not did_work:
            stop_event.wait(5)
