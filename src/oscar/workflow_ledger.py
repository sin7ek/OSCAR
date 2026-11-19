"""Persistent, non-destructive per-rip OSCAR workflow ledger.

Phase-one scheduler foundation: records verified staging jobs and immutable
identification policy snapshots. Never auto-tags, publishes, deletes or
claims that a MusicBrainz physical release has been established.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3

from oscar import verification
from oscar.settings import discover_settings

_JOB_ID = re.compile(r"[a-f0-9]{32}\Z")
_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_jobs (
  job_id TEXT PRIMARY KEY,
  disc_id TEXT NOT NULL DEFAULT '',
  identification_mode TEXT NOT NULL,
  secure_review_level TEXT NOT NULL,
  phase TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  proposed_release_id TEXT NOT NULL DEFAULT '',
  release_evidence TEXT NOT NULL DEFAULT '',
  candidate_options TEXT NOT NULL DEFAULT '[]',
  accepted_release_id TEXT NOT NULL DEFAULT '',
  release_approved_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS workflow_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL REFERENCES workflow_jobs(job_id),
  phase_before TEXT NOT NULL,
  phase_after TEXT NOT NULL,
  reason TEXT NOT NULL,
  happened_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS workflow_events_by_job ON workflow_events(job_id, id);
"""


class WorkflowError(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _db():
    path = Path(os.environ.get("OSCAR_WORKFLOW_DB", "/config/workflow.sqlite3"))
    if not path.is_absolute() or path.name != "workflow.sqlite3" or path.is_symlink():
        raise WorkflowError("Workflow database must be absolute workflow.sqlite3 path")
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise WorkflowError("Persistent workflow database directory is not available")
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(_SCHEMA)
    existing = {row[1] for row in db.execute("PRAGMA table_info(workflow_jobs)")}
    for name in ("proposed_release_id", "release_evidence", "candidate_options",
                 "accepted_release_id", "release_approved_at"):
        if name not in existing:
            db.execute("ALTER TABLE workflow_jobs ADD COLUMN " + name + " TEXT NOT NULL DEFAULT ''")
    return db


def _state(job_id):
    if not _JOB_ID.fullmatch(job_id):
        raise WorkflowError("Invalid rip job ID")
    root = verification._safe_job(job_id)
    statefile = root / "state.json"
    if statefile.is_symlink():
        raise WorkflowError("Staging rip state is unsafe")
    if not statefile.is_file():
        # Go registers before spawning the extraction worker. A browser may
        # poll during that brief window, before its first state.json exists.
        # Only a real in-memory newly-created job qualifies for this fallback.
        from oscar import ripping
        live = ripping._JOBS.get(job_id)
        if not live or live.get("status") not in {"queued", "running"}:
            raise WorkflowError("Staging rip state is missing")
        state = ripping._snapshot(live)
    else:
        state = json.loads(statefile.read_text(encoding="utf-8"))
    if state.get("id") != job_id:
        raise WorkflowError("Staging job ID differs from saved state")
    return state


def _observed_phase(job_id, state):
    phase = state.get("status")
    if phase == "failed":
        return "RIP_FAILED"
    if phase == "interrupted":
        return "RIP_INTERRUPTED"
    if phase in ("queued", "running"):
        return "RIP_IN_PROGRESS"
    if phase != "needs_verification" or state.get("returncode") != 0:
        raise WorkflowError("Unexpected staged rip state; cannot infer workflow status")
    report = verification.report(job_id)
    if report.get("status") == "checks_passed" and report.get("job_id") == job_id:
        return "RELEASE_REVIEW_PENDING"
    return "VERIFICATION_PENDING"


def _view(db, job_id):
    row = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row:
        raise WorkflowError("Workflow job is not registered")
    result = dict(row)
    result["events"] = [dict(x) for x in db.execute(
        "SELECT phase_before,phase_after,reason,happened_at FROM workflow_events "
        "WHERE job_id=? ORDER BY id", (job_id,))]
    result["automated_actions_enabled"] = False
    result["release_physically_verified"] = False
    result["candidate_options"] = json.loads(result.get("candidate_options") or "[]")
    result["release_match_status"] = (
        "INFERRED_OPERATOR_ACCEPTED" if result.get("accepted_release_id")
        else "INFERRED_NOT_PHYSICALLY_VERIFIED" if result.get("proposed_release_id")
        else "UNRESOLVED")
    result["next_action"] = {
        "RIP_IN_PROGRESS": "Wait for the rip to finish, then refresh this record",
        "RIP_FAILED": "Review the extraction failure; do not publish",
        "RIP_INTERRUPTED": "Service restarted during extraction; inspect staging; no automatic rerip",
        "VERIFICATION_PENDING": "Run staging verification; original files remain untouched",
        "RELEASE_REVIEW_PENDING": "Review release evidence; no release approved automatically",
        "RELEASE_ACCEPTED": "Operator accepted an inferred release; tagging and archive publication remain manual and disabled in Go",
        "DEFERRED_REVIEW": "Resume review when the physical edition has been resolved",
    }.get(result["phase"], "Manual review required")
    return result


def _transition(db, job_id, before, after, reason):
    if before == after:
        return
    stamp = _now()
    result = db.execute("UPDATE workflow_jobs SET phase=?,updated_at=? WHERE job_id=? AND phase=?",
                        (after,stamp,job_id,before))
    if result.rowcount != 1:
        raise WorkflowError("Concurrent workflow state changed; refresh")
    db.execute("INSERT INTO workflow_events (job_id,phase_before,phase_after,reason,happened_at)"
               " VALUES (?,?,?,?,?)", (job_id,before,after,reason,stamp))



def register_created(job):
    """Capture the identification policy at *rip creation*, before cyanrip starts.

    Intended only as the on_created hook for the new Go controller.
    Failure aborts the ripping worker rather than leaving an untracked rip.
    """
    job_id = job.get("id")
    if not isinstance(job_id, str) or not _JOB_ID.fullmatch(job_id):
        raise WorkflowError("Invalid created rip ID")
    if job.get("status") != "queued":
        raise WorkflowError("Go registration must occur before extraction starts")
    settings = discover_settings()
    stamp = _now()
    with _db() as db:
        existing = db.execute("SELECT 1 FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if existing:
            raise WorkflowError("Go rip ID already registered; refusing duplicate start")
        db.execute("""INSERT INTO workflow_jobs
            (job_id,disc_id,identification_mode,secure_review_level,phase,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)""",
            (job_id,str(job.get("disc_id") or "")[:28],settings.identification_mode,
             settings.secure_review_level,"RIP_IN_PROGRESS",stamp,stamp))
        db.execute("""INSERT INTO workflow_events
            (job_id,phase_before,phase_after,reason,happened_at) VALUES (?,?,?,?,?)""",
            (job_id,"UNREGISTERED","RIP_IN_PROGRESS","go_created_before_extraction",stamp))
        return _view(db,job_id)

def register(job_id):
    """Operator attaches a saved rip; settings are snapshotted ONCE.

    This is *not yet* called automatically by the extraction engine.
    """
    state = _state(job_id)
    observed = _observed_phase(job_id,state)
    with _db() as db:
        old = db.execute("SELECT job_id FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not old:
            settings = discover_settings()
            stamp = _now()
            db.execute("""INSERT INTO workflow_jobs
                (job_id,disc_id,identification_mode,secure_review_level,phase,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?)""", (job_id,str(state.get("disc_id") or "")[:28],
                settings.identification_mode, settings.secure_review_level, observed,stamp,stamp))
            db.execute("""INSERT INTO workflow_events
                (job_id,phase_before,phase_after,reason,happened_at) VALUES (?,?,?,?,?)""",
                (job_id,"UNREGISTERED",observed,"manual_staging_registration",stamp))
        return _view(db,job_id)


def refresh(job_id):
    """Reconcile durable state with saved rip/verification evidence only."""
    state = _state(job_id)
    from oscar import ripping
    active = ripping.status(job_id)
    if active.get("status") == "interrupted":
        state["status"] = "interrupted"
    observed = _observed_phase(job_id,state)
    with _db() as db:
        existing = db.execute("SELECT phase FROM workflow_jobs WHERE job_id=?",
                              (job_id,)).fetchone()
        if not existing:
            raise WorkflowError("Register the staging job first")
        phase = existing["phase"]
        if phase in {"RIP_IN_PROGRESS","VERIFICATION_PENDING"} and observed in {
                "VERIFICATION_PENDING","RELEASE_REVIEW_PENDING","RIP_FAILED","RIP_INTERRUPTED"}:
            _transition(db,job_id,phase,observed,"source_staging_reconciliation")
        return _view(db,job_id)



def remember_suggestion(job_id, release_id, evidence):
    """Store an *inferred candidate only*, never approve a physical edition."""
    if not _JOB_ID.fullmatch(job_id):
        raise WorkflowError("Invalid job ID")
    if not re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", release_id):
        raise WorkflowError("Invalid MusicBrainz release UUID")
    if evidence not in {"inferred_disc_id_unique", "inferred_disc_id_ranked"}:
        raise WorkflowError("Unknown candidate evidence")
    with _db() as db:
        item = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not item or item["phase"] != "RELEASE_REVIEW_PENDING":
            raise WorkflowError("Verified rip review required before saving candidate")
        if item["identification_mode"] != "best_guess":
            raise WorkflowError("Cannot infer a physical release in Secure mode")
        if item["proposed_release_id"]:
            return _view(db,job_id)
        stamp = _now()
        db.execute("""UPDATE workflow_jobs SET proposed_release_id=?,
            release_evidence=?,updated_at=? WHERE job_id=?""",
            (release_id,evidence,stamp,job_id))
        db.execute("""INSERT INTO workflow_events
            (job_id,phase_before,phase_after,reason,happened_at) VALUES (?,?,?,?,?)""",
            (job_id,item["phase"],item["phase"],"read_only_inferred_candidate_"+evidence,stamp))
        return _view(db,job_id)

def remember_semi_candidates(job_id, candidates, evidence):
    """Freeze a server-discovered option set; require per-job operator approval.

    The first successful snapshot wins across polls and restarts. It is a
    read-only metadata decision and is not a physical edition assertion.
    """
    if not _JOB_ID.fullmatch(job_id):
        raise WorkflowError("Invalid rip job ID")
    if evidence not in {"inferred_disc_id_unique", "inferred_disc_id_ranked"}:
        raise WorkflowError("Invalid candidate evidence")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 250:
        raise WorkflowError("Invalid or oversized release candidate set")
    safe = []
    ids = set()
    for item in candidates:
        release_id = item.get("release_id") if isinstance(item, dict) else None
        if not isinstance(release_id, str) or not re.fullmatch(
                r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", release_id):
            raise WorkflowError("Invalid discovered release ID")
        if release_id not in ids:
            safe.append({"release_id": release_id,
                         "title": str(item.get("title") or "")[:300],
                         "date": str(item.get("date") or "")[:30],
                         "score": int(item.get("score") or 0)})
            ids.add(release_id)
    with _db() as db:
        item = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not item or item["identification_mode"] != "semi_automatic" or item["phase"] != "RELEASE_REVIEW_PENDING":
            raise WorkflowError("Semi Automatic verified review is required")
        if item["proposed_release_id"]:
            return _view(db, job_id)
        stamp = _now()
        result = db.execute("""UPDATE workflow_jobs SET proposed_release_id=?,
            release_evidence=?,candidate_options=?,updated_at=?
            WHERE job_id=? AND proposed_release_id='' AND phase='RELEASE_REVIEW_PENDING'""",
            (safe[0]["release_id"], evidence, json.dumps(safe), stamp, job_id))
        if result.rowcount != 1:
            return _view(db, job_id)
        db.execute("""INSERT INTO workflow_events
            (job_id,phase_before,phase_after,reason,happened_at) VALUES (?,?,?,?,?)""",
            (job_id, "RELEASE_REVIEW_PENDING", "RELEASE_REVIEW_PENDING",
             "semi_automatic_candidates_proposed", stamp))
        return _view(db, job_id)


def accept_semi_release(job_id, release_id, confirmation):
    """Approve an inferred release explicitly, without tagging or publishing."""
    if not _JOB_ID.fullmatch(job_id):
        raise WorkflowError("Invalid rip job ID")
    if confirmation != "ACCEPT_INFERRED_RELEASE":
        raise WorkflowError("Explicit inferred-release risk acceptance required")
    if not isinstance(release_id, str) or not re.fullmatch(
            r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", release_id):
        raise WorkflowError("Invalid MusicBrainz release UUID")
    # Always check live saved verification before accepting identity.
    current = refresh(job_id)
    with _db() as db:
        item = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not item or item["identification_mode"] != "semi_automatic":
            raise WorkflowError("Only Semi Automatic jobs can accept inferred releases")
        if item["phase"] == "RELEASE_ACCEPTED":
            if item["accepted_release_id"] == release_id:
                return _view(db, job_id)
            raise WorkflowError("Release was already accepted; cannot silently replace it")
        if item["phase"] != "RELEASE_REVIEW_PENDING" or current["phase"] != "RELEASE_REVIEW_PENDING":
            raise WorkflowError("Successful verified audio review required")
        candidates = json.loads(item["candidate_options"])
        if release_id not in {x["release_id"] for x in candidates}:
            raise WorkflowError("Only a saved server-discovered candidate may be accepted")
        stamp = _now()
        result = db.execute("""UPDATE workflow_jobs SET accepted_release_id=?,
            release_approved_at=?,updated_at=? WHERE job_id=? AND
            accepted_release_id='' AND phase='RELEASE_REVIEW_PENDING'""",
            (release_id, stamp, stamp, job_id))
        if result.rowcount != 1:
            raise WorkflowError("Concurrent release review changed; refresh")
        _transition(db, job_id, "RELEASE_REVIEW_PENDING", "RELEASE_ACCEPTED",
                    "operator_accepted_inferred_release")
        return _view(db, job_id)


def review_action(job_id, action):
    """The only manual transitions in v1: defer/resume edition review."""
    if action not in {"defer", "resume"}:
        raise WorkflowError("Unsupported review action")
    after = "DEFERRED_REVIEW" if action == "defer" else "RELEASE_REVIEW_PENDING"
    before = "RELEASE_REVIEW_PENDING" if action == "defer" else "DEFERRED_REVIEW"
    with _db() as db:
        existing = db.execute("SELECT phase FROM workflow_jobs WHERE job_id=?",
                              (job_id,)).fetchone()
        if not existing:
            raise WorkflowError("Register the staging job first")
        if existing["phase"] not in {before,after}:
            raise WorkflowError("This workflow cannot be deferred or resumed in its current phase")
        _transition(db,job_id,existing["phase"],after,"operator_"+action)
        return _view(db,job_id)


def list_jobs(limit=100):
    if not 1 <= limit <= 250:
        raise WorkflowError("Invalid workflow listing limit")
    with _db() as db:
        rows = [dict(x) for x in db.execute(
            "SELECT job_id,disc_id,phase,identification_mode,secure_review_level,updated_at "
            "FROM workflow_jobs ORDER BY updated_at DESC LIMIT ?", (limit,))]
    return {"jobs":rows, "engine_running":False,
            "notice":"Persistent ledger only; automatic rip-to-archive orchestration not implemented."}
