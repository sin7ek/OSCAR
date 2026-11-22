"""Durable DriveFit measurements, independent of removable staging files.

This ledger records bounded non-secret job metrics only, never audio, album
metadata, Disc ID or file paths. Idempotent UPSERTs permit retry/restarts.
"""
from __future__ import annotations

from contextlib import closing
import math
from pathlib import Path
import re
import sqlite3
import time

from oscar.settings import config_path

_ID = re.compile(r"[a-f0-9]{32}\Z")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS drivefit_jobs (
 job_id TEXT PRIMARY KEY,
 stable_id TEXT NOT NULL,
 status TEXT NOT NULL,
 started_at REAL,
 finished_at REAL,
 duration_seconds REAL,
 tracks INTEGER,
 verification_status TEXT NOT NULL DEFAULT 'not_available',
 ripping_errors INTEGER,
 updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS drivefit_job_context (
 job_id TEXT PRIMARY KEY,
 audio_seconds REAL,
 diagnostic INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_drivefit_stable_finished
ON drivefit_jobs(stable_id,finished_at);
"""


def database_path():
    path = config_path().parent / "drivefit.sqlite3"
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Unsafe DriveFit history path")
    return path


def _db():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.executescript(_SCHEMA)
    return db


def _timestamp(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


def audio_seconds(plan):
    """Read the CD audio span in 75-Hz sectors from the saved libdiscid TOC."""
    try:
        first, last, leadout, *offsets = map(int, plan.get("toc_string", "").split())
    except (AttributeError, TypeError, ValueError):
        return None
    if (not 1 <= first <= last <= 99 or len(offsets) != last - first + 1
            or not 0 <= offsets[0] < leadout <= 450000
            or any(a >= b for a, b in zip(offsets, [*offsets[1:], leadout]))):
        return None
    return (leadout - offsets[0]) / 75


def record_rip(state, track_count=None, *, plan=None):
    """Upsert a completed or failed extraction event; no file contents saved."""
    job_id, stable_id = state.get("id"), state.get("stable_id")
    status = state.get("status")
    if (not isinstance(job_id, str) or not _ID.fullmatch(job_id)
            or not isinstance(stable_id, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", stable_id)
            or status not in ("needs_verification", "partial_diagnostic", "failed", "interrupted")):
        return False
    started = _timestamp(state.get("started_at"))
    finished = _timestamp(state.get("finished_at"))
    duration = round(finished - started, 1) if started and finished and 0 <= finished - started <= 10800 else None
    tracks = track_count if type(track_count) is int and 1 <= track_count <= 150 else None
    with closing(_db()) as db, db:
        db.execute(
            """INSERT INTO drivefit_jobs
                (job_id,stable_id,status,started_at,finished_at,duration_seconds,tracks,updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                status=excluded.status,
                finished_at=excluded.finished_at,
                started_at=excluded.started_at,
                duration_seconds=excluded.duration_seconds,
                tracks=COALESCE(excluded.tracks,drivefit_jobs.tracks),
                updated_at=excluded.updated_at
                WHERE drivefit_jobs.stable_id=excluded.stable_id""",
            (job_id, stable_id, status, started, finished, duration, tracks, time.time()),
        )
        if plan is not None:
            db.execute(
                """INSERT INTO drivefit_job_context
                   SELECT ?,?,? WHERE EXISTS (SELECT 1 FROM drivefit_jobs WHERE job_id=? AND stable_id=?)
                   ON CONFLICT(job_id) DO UPDATE SET
                   audio_seconds=excluded.audio_seconds, diagnostic=excluded.diagnostic""",
                (job_id, audio_seconds(plan), bool(plan.get("selected_tracks")), job_id, stable_id),
            )
    return True


def record_verification(job_id, report):
    """Update an existing completed rip row, never create unlinked data."""
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        return False
    if report.get("job_id") != job_id:
        return False
    status = report.get("status")
    if status not in ("checks_passed", "review_required"):
        return False
    errors = report.get("ripping_errors")
    if type(errors) is not int or not 0 <= errors <= 999999:
        errors = None
    with closing(_db()) as db, db:
        cursor = db.execute(
            """UPDATE drivefit_jobs SET verification_status=?,
                ripping_errors=?,updated_at=? WHERE job_id=?""",
            (status, errors, time.time(), job_id),
        )
    return cursor.rowcount == 1


def read_history(stable_ids, *, limit=5000):
    """Per-drive lightweight metrics, no user supplied SQL identifiers."""
    if not stable_ids or not database_path().exists():
        return []
    path = database_path()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as db:
        db.row_factory = sqlite3.Row
        has_context = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='drivefit_job_context'"
        ).fetchone()
        context = ("c.audio_seconds, c.diagnostic FROM drivefit_jobs j "
                   "LEFT JOIN drivefit_job_context c USING(job_id)" if has_context else
                   "NULL AS audio_seconds, NULL AS diagnostic FROM drivefit_jobs j")
        rows = db.execute(
            """SELECT j.job_id,j.stable_id,j.status,j.duration_seconds,j.tracks,j.verification_status,
                      j.ripping_errors,j.finished_at,""" + context + " ORDER BY j.finished_at DESC LIMIT ?",
            (max(1, min(int(limit), 5000)),),
        ).fetchall()
    return [dict(r) for r in rows if r["stable_id"] in stable_ids]
