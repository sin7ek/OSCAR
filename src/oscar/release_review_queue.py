"""Persist unresolved physical-release review tasks without touching the rip.

Missing or incorrect MusicBrainz editions are not rip failures. A verified rip
can be deferred, indexed by job ID, and reviewed later.
"""
from pathlib import Path
import re
import sqlite3
import time

from oscar.settings import config_path
from oscar import verification

_JOB = re.compile(r"[a-f0-9]{32}\Z")
_REASONS = {"missing_release", "wrong_edition", "ambiguous_edition", "incomplete_metadata"}


class RecoveryError(RuntimeError):
    pass


def database_path():
    return config_path().parent / "release_review.sqlite3"


def _db(path=None):
    path = Path(path) if path is not None else database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=20000")
    db.execute("""CREATE TABLE IF NOT EXISTS release_review (
        job_id TEXT PRIMARY KEY,
        reason TEXT NOT NULL,
        title TEXT NOT NULL,
        catalog_number TEXT NOT NULL,
        notes TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )""")
    return db


def defer(job_id, *, reason, title="", catalog_number="", notes="", path=None):
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise RecoveryError("Invalid verified staging job ID")
    if reason not in _REASONS:
        raise RecoveryError("Invalid release review reason")
    for name, value, limit in [("title", title, 200),
                                ("catalog_number", catalog_number, 100),
                                ("notes", notes, 1000)]:
        if not isinstance(value, str) or len(value) > limit or "\x00" in value:
            raise RecoveryError(f"Invalid {name}")
    try:
        verification._safe_job(job_id)
        report = verification.report(job_id)
    except (OSError, ValueError, RuntimeError) as exc:
        raise RecoveryError("Verified staging rip not accessible") from exc
    if report.get("status") != "checks_passed":
        raise RecoveryError("Rip must pass staging verification before deferral")
    now = int(time.time())
    with _db(path) as db:
        db.execute("""INSERT INTO release_review
          (job_id,reason,title,catalog_number,notes,status,created_at,updated_at)
          VALUES (?,?,?,?,?,'pending',?,?)
          ON CONFLICT(job_id) DO UPDATE SET reason=excluded.reason,
          title=excluded.title,catalog_number=excluded.catalog_number,
          notes=excluded.notes,status='pending',updated_at=excluded.updated_at""",
          (job_id, reason, title.strip(), catalog_number.strip(), notes.strip(), now, now))
    return {"status": "pending", "job_id": job_id, "reason": reason,
            "note": "Review task saved in /config. The original rip, CUE, FLACs and tags were not modified. No MusicBrainz edit has been submitted."}


def pending(*, path=None):
    with _db(path) as db:
        rows = db.execute("""SELECT job_id,reason,title,catalog_number,notes,
                                    status,created_at,updated_at
                             FROM release_review WHERE status='pending'
                             ORDER BY updated_at DESC LIMIT 100""").fetchall()
    return {"items": [dict(x) for x in rows], "status": "review_only"}


def resolve(job_id, *, path=None):
    if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
        raise RecoveryError("Invalid staging job ID")
    with _db(path) as db:
        result = db.execute(
            "UPDATE release_review SET status='resolved',updated_at=? WHERE job_id=? AND status='pending'",
            (int(time.time()), job_id))
        if not result.rowcount:
            raise RecoveryError("No pending review task found")
    return {"status": "resolved", "job_id": job_id,
            "note": "Only the follow-up task is closed; no audio or metadata changed."}
