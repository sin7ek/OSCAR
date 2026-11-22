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
from oscar.pressing_evidence import observed_matrix
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
  release_approved_at TEXT NOT NULL DEFAULT '',
  matrix_runout TEXT NOT NULL DEFAULT '',
  metadata_copy_id TEXT NOT NULL DEFAULT '',
  metadata_fingerprint TEXT NOT NULL DEFAULT '',
  metadata_release_id TEXT NOT NULL DEFAULT '',
  archive_publish_id TEXT NOT NULL DEFAULT '',
  archive_fingerprint TEXT NOT NULL DEFAULT '',
  archive_relative_directory TEXT NOT NULL DEFAULT '',
  archive_release_id TEXT NOT NULL DEFAULT '',
  archive_automatic INTEGER NOT NULL DEFAULT 0,
  archive_catalog_status TEXT NOT NULL DEFAULT ''
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
                 "accepted_release_id", "release_approved_at", "matrix_runout", "metadata_copy_id",
                 "metadata_fingerprint", "metadata_release_id",
                 "archive_publish_id", "archive_fingerprint",
                 "archive_relative_directory", "archive_release_id",
                 "archive_catalog_status", "archive_automatic"):
        if name not in existing:
            if name == "archive_automatic":
                db.execute("ALTER TABLE workflow_jobs ADD COLUMN archive_automatic INTEGER NOT NULL DEFAULT 0")
            else:
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
    if phase == "partial_diagnostic":
        raise WorkflowError("Selected-track diagnostic cannot enter Go workflow")
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
    result["automated_actions_enabled"] = (
        result["identification_mode"] == "best_guess"
        and os.environ.get("OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH") == "1"
        and os.environ.get("OSCAR_ENABLE_ARCHIVE_PUBLISH") == "1")
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
        "RELEASE_ACCEPTED": "Operator accepted inferred release; Go can prepare a separate tagged staging copy",
        "METADATA_COPY_RUNNING": "Isolated tagged copy is being generated and verified",
        "METADATA_READY": "Tagged staging copy is verified; review before separate archive publication",
        "METADATA_REVIEW_REQUIRED": "Metadata handoff failed or was interrupted; source remains untouched",
        "ARCHIVE_PUBLISH_RUNNING": "Archive publication reserved. Await verification and manifest; no automatic retry",
        "ARCHIVE_PUBLISHED": "Verified archive publication recorded; original staging preserved",
        "ARCHIVE_REVIEW_REQUIRED": "Archive publication interrupted, invalid or failed; inspect archive and staging",
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


def register_recovery(job_id):
    """Register a successfully independently verified recovery for manual review.

    Recovery is deliberately Semi Automatic irrespective of current Best Guess
    configuration; a recovered CD never inherits unattended archive approval.
    """
    state = _state(job_id)
    report = verification.report(job_id)
    directory = verification._safe_job(job_id)
    plan_path = directory / "plan.json"
    if plan_path.is_symlink() or not plan_path.is_file():
        raise WorkflowError("Recovery plan missing")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    recovery = plan.get("recovery") or {}
    if (recovery.get("format") != "OSCAR_TRACK_RECOVERY_V1"
            or state.get("status") != "needs_verification"
            or state.get("returncode") != 0
            or report.get("status") != "checks_passed"
            or report.get("verification_method") != "independent_trackverify_R_v1_v2"
            or report.get("job_id") != job_id
            or len(report.get("tracks") or []) != plan.get("track_count")
            or not all(track.get("checks_passed") for track in report["tracks"])):
        raise WorkflowError("Recovery lacks fully verified independent AccurateRip evidence")
    settings = discover_settings()
    stamp = _now()
    with _db() as db:
        if db.execute("SELECT 1 FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone():
            raise WorkflowError("Recovered workflow already registered")
        db.execute("""INSERT INTO workflow_jobs
            (job_id,disc_id,identification_mode,secure_review_level,phase,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)""",
            (job_id, state["disc_id"], "semi_automatic", settings.secure_review_level,
             "RELEASE_REVIEW_PENDING", stamp, stamp))
        db.execute("""INSERT INTO workflow_events
            (job_id,phase_before,phase_after,reason,happened_at) VALUES (?,?,?,?,?)""",
            (job_id, "UNREGISTERED", "RELEASE_REVIEW_PENDING",
             "independently_verified_track_recovery_manual_release_review", stamp))
        return _view(db, job_id)


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


def accept_semi_release(job_id, release_id, confirmation, *, matrix_runout=None):
    """Approve an inferred release explicitly, without tagging or publishing."""
    if not _JOB_ID.fullmatch(job_id):
        raise WorkflowError("Invalid rip job ID")
    if confirmation != "ACCEPT_INFERRED_RELEASE":
        raise WorkflowError("Explicit inferred-release risk acceptance required")
    if not isinstance(release_id, str) or not re.fullmatch(
            r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", release_id):
        raise WorkflowError("Invalid MusicBrainz release UUID")
    matrix = observed_matrix(matrix_runout)
    # Always check live saved verification before accepting identity.
    current = refresh(job_id)
    with _db() as db:
        item = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not item or item["identification_mode"] != "semi_automatic":
            raise WorkflowError("Only Semi Automatic jobs can accept inferred releases")
        if item["phase"] == "RELEASE_ACCEPTED":
            if item["accepted_release_id"] == release_id and item["matrix_runout"] == matrix:
                return _view(db, job_id)
            raise WorkflowError("Release was already accepted; cannot silently replace it")
        if item["phase"] != "RELEASE_REVIEW_PENDING" or current["phase"] != "RELEASE_REVIEW_PENDING":
            raise WorkflowError("Successful verified audio review required")
        candidates = json.loads(item["candidate_options"])
        if release_id not in {x["release_id"] for x in candidates}:
            raise WorkflowError("Only a saved server-discovered candidate may be accepted")
        stamp = _now()
        result = db.execute("""UPDATE workflow_jobs SET accepted_release_id=?,
            release_approved_at=?,matrix_runout=?,updated_at=? WHERE job_id=? AND
            accepted_release_id='' AND phase='RELEASE_REVIEW_PENDING'""",
            (release_id, stamp, matrix, stamp, job_id))
        if result.rowcount != 1:
            raise WorkflowError("Concurrent release review changed; refresh")
        _transition(db, job_id, "RELEASE_REVIEW_PENDING", "RELEASE_ACCEPTED",
                    "operator_accepted_inferred_release")
        return _view(db, job_id)



def reserve_metadata_copy(job_id, release_id, fingerprint):
    """Reserve exactly one copy ID durably before launching any metadata worker.

    Best Guess may use its snapshotted inferred candidate; Semi Automatic
    must already have an explicitly accepted release. Secure cannot use
    inference-only Go handoff. No second copy is scheduled on repeat polls.
    """
    import uuid
    if not _JOB_ID.fullmatch(job_id):
        raise WorkflowError("Invalid job ID")
    if not re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", release_id):
        raise WorkflowError("Invalid release ID")
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise WorkflowError("Invalid metadata fingerprint")
    # Re-evaluate source verification before using the operator's approved ID.
    observed = refresh(job_id)
    if observed["phase"] not in {"RELEASE_REVIEW_PENDING", "RELEASE_ACCEPTED",
                                  "METADATA_COPY_RUNNING", "METADATA_READY",
                                  "METADATA_REVIEW_REQUIRED"}:
        raise WorkflowError("Verified source required before metadata handoff")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        item = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not item:
            raise WorkflowError("Workflow job not registered")
        if item["identification_mode"] == "best_guess":
            expected = item["proposed_release_id"]
            valid_phase = "RELEASE_REVIEW_PENDING"
        elif item["identification_mode"] == "semi_automatic":
            expected = item["accepted_release_id"]
            valid_phase = "RELEASE_ACCEPTED"
        else:
            raise WorkflowError("Secure Go metadata handoff requires physical edition verification")
        if expected != release_id or not expected:
            raise WorkflowError("Release differs from snapshotted inference or operator approval")
        if item["metadata_copy_id"]:
            if item["metadata_release_id"] != release_id:
                raise WorkflowError("A different release copy has already been reserved")
            return _view(db, job_id)
        if item["phase"] != valid_phase:
            raise WorkflowError("Current workflow phase cannot initiate metadata handoff")
        copy_id = uuid.uuid4().hex
        stamp = _now()
        result = db.execute("""UPDATE workflow_jobs SET metadata_copy_id=?,
            metadata_fingerprint=?,metadata_release_id=?,updated_at=?
            WHERE job_id=? AND metadata_copy_id='' AND phase=?""",
            (copy_id, fingerprint, release_id, stamp, job_id, valid_phase))
        if result.rowcount != 1:
            raise WorkflowError("Concurrent metadata reservation; reload")
        _transition(db, job_id, valid_phase, "METADATA_COPY_RUNNING",
                    "metadata_copy_reserved_before_worker")
        return _view(db, job_id)


def complete_metadata_copy(job_id, copy_id, *, checked, reason):
    """Record read-back result against one durable reserved copy."""
    if not _JOB_ID.fullmatch(job_id) or not _JOB_ID.fullmatch(copy_id):
        raise WorkflowError("Invalid job/copy ID")
    if reason not in {"tagged_copy_inspected", "tagged_copy_invalid_or_interrupted"}:
        raise WorkflowError("Invalid metadata status reason")
    next_phase = "METADATA_READY" if checked else "METADATA_REVIEW_REQUIRED"
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        item = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not item or item["metadata_copy_id"] != copy_id:
            raise WorkflowError("Unknown or changed metadata copy reservation")
        if item["phase"] == next_phase:
            return _view(db, job_id)
        if item["phase"] != "METADATA_COPY_RUNNING":
            raise WorkflowError("Cannot change finalized metadata copy result")
        _transition(db, job_id, item["phase"], next_phase, reason)
        return _view(db, job_id)




def adopt_refreshed_metadata_copy(job_id, old_copy_id, new_copy_id, release_id,
                                  new_fingerprint, confirmation):
    """Atomically use an already verified isolated copy for first Go publication.

    The prior copy is retained. A pending or completed publication reservation
    permanently closes this path, even if the archive is not currently visible.
    """
    if confirmation != "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION":
        raise WorkflowError("Explicit refreshed-copy adoption confirmation required")
    if not all(isinstance(value, str) and _JOB_ID.fullmatch(value)
               for value in (job_id, old_copy_id, new_copy_id)):
        raise WorkflowError("Invalid metadata copy or rip job ID")
    if old_copy_id == new_copy_id:
        raise WorkflowError("Refreshed copy must differ from original")
    if not isinstance(release_id, str) or not re.fullmatch(
            r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", release_id):
        raise WorkflowError("Invalid accepted release UUID")
    if not isinstance(new_fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", new_fingerprint):
        raise WorkflowError("Invalid new copy preview fingerprint")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row or row["phase"] != "METADATA_READY":
            raise WorkflowError("Only ready, unpublished Go jobs can select a refreshed copy")
        if row["identification_mode"] != "semi_automatic" or row["accepted_release_id"] != release_id:
            raise WorkflowError("The original accepted Semi Automatic release must remain unchanged")
        if row["metadata_release_id"] != release_id or row["metadata_copy_id"] != old_copy_id:
            raise WorkflowError("Existing metadata copy/release changed; refresh Go before retrying")
        if row["archive_publish_id"]:
            raise WorkflowError("An archive publication was already reserved; adoption prohibited")
        stamp = _now()
        updated = db.execute("""UPDATE workflow_jobs
            SET metadata_copy_id=?,metadata_fingerprint=?,updated_at=?
            WHERE job_id=? AND metadata_copy_id=? AND metadata_release_id=?
              AND phase='METADATA_READY' AND archive_publish_id=''""",
            (new_copy_id, new_fingerprint, stamp, job_id, old_copy_id, release_id))
        if updated.rowcount != 1:
            raise WorkflowError("Concurrent metadata or publication change; retry review")
        db.execute("""INSERT INTO workflow_events
            (job_id,phase_before,phase_after,reason,happened_at)
            VALUES (?,?,?,?,?)""", (job_id, "METADATA_READY", "METADATA_READY",
                "operator_adopted_refreshed_copy:" + old_copy_id + "->" + new_copy_id, stamp))
        return _view(db, job_id)


def reserve_archive_publish(job_id, copy_id, release_id, fingerprint,
                            relative_directory, *, automatic=False):
    """Single durable publication reservation, committed before any archive worker.

    A reserved publication is never started again after a restart. The only
    recovery route is validating the exact archive manifest or manual review.
    """
    import uuid
    if not _JOB_ID.fullmatch(job_id) or not _JOB_ID.fullmatch(copy_id):
        raise WorkflowError("Invalid job/copy ID")
    if not re.fullmatch(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}", release_id):
        raise WorkflowError("Invalid release UUID")
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise WorkflowError("Invalid publication fingerprint")
    if (not isinstance(relative_directory, str) or not relative_directory
            or len(relative_directory) > 1000 or relative_directory.startswith("/")
            or any(part in {"", ".", ".."} for part in relative_directory.split("/"))):
        raise WorkflowError("Invalid archive relative directory")
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise WorkflowError("Workflow not registered")
        if row["archive_publish_id"]:
            raise WorkflowError("Publication already reserved; never start a second worker")
        if row["phase"] != "METADATA_READY" or row["metadata_copy_id"] != copy_id or row["metadata_release_id"] != release_id:
            raise WorkflowError("Exact verified metadata copy required before archive reservation")
        if row["identification_mode"] == "secure":
            raise WorkflowError("Secure cannot publish inferred metadata")
        if row["identification_mode"] == "semi_automatic":
            if automatic or row["accepted_release_id"] != release_id:
                raise WorkflowError("Semi Automatic requires explicit review and release acceptance")
        elif row["identification_mode"] == "best_guess":
            if row["proposed_release_id"] != release_id:
                raise WorkflowError("Best Guess candidate changed")
            if automatic and (row["release_evidence"] != "inferred_disc_id_unique"
                    or os.environ.get("OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH") != "1"
                    or os.environ.get("OSCAR_ENABLE_ARCHIVE_PUBLISH") != "1"):
                raise WorkflowError("Unambiguous, explicitly enabled Best Guess required")
        else:
            raise WorkflowError("Unsupported archive publication mode")
        publish_id = uuid.uuid4().hex
        stamp = _now()
        db.execute("""UPDATE workflow_jobs SET
            archive_publish_id=?,archive_fingerprint=?,archive_relative_directory=?,
            archive_release_id=?,archive_automatic=?,updated_at=? WHERE job_id=?""",
            (publish_id, fingerprint, relative_directory, release_id, int(automatic), stamp, job_id))
        _transition(db, job_id, "METADATA_READY", "ARCHIVE_PUBLISH_RUNNING",
                    "automatic_archive_reserved" if automatic else "operator_archive_reserved")
        return _view(db, job_id)


def complete_archive_publish(job_id, publish_id, *, published, catalog_status="", reason=""):
    if not _JOB_ID.fullmatch(job_id) or not _JOB_ID.fullmatch(publish_id):
        raise WorkflowError("Invalid archive publication ID")
    if reason not in {"manifest_reconciled", "publisher_result_verified",
                      "publisher_failed_or_interrupted"}:
        raise WorkflowError("Invalid archive completion reason")
    if catalog_status not in {"", "indexed", "index_required"}:
        raise WorkflowError("Invalid catalog status")
    after = "ARCHIVE_PUBLISHED" if published else "ARCHIVE_REVIEW_REQUIRED"
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM workflow_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row or row["archive_publish_id"] != publish_id:
            raise WorkflowError("Publication reservation identity changed")
        if row["phase"] == after:
            return _view(db, job_id)
        if row["phase"] != "ARCHIVE_PUBLISH_RUNNING":
            raise WorkflowError("Publication already finalized; review required")
        db.execute("UPDATE workflow_jobs SET archive_catalog_status=? WHERE job_id=?",
                   (catalog_status, job_id))
        _transition(db, job_id, "ARCHIVE_PUBLISH_RUNNING", after, reason)
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
            "SELECT job_id,disc_id,phase,identification_mode,secure_review_level,"
            "created_at,updated_at,proposed_release_id,accepted_release_id,"
            "candidate_options FROM workflow_jobs ORDER BY updated_at DESC LIMIT ?", (limit,))]
    # Display-only evidence, never physical-edition proof or an approval action.
    # All candidate titles originate from previously persisted MusicBrainz results;
    # never perform network lookups while listing jobs.
    for row in rows:
        try:
            candidates = json.loads(row.pop("candidate_options") or "[]")
        except (ValueError, TypeError):
            candidates = []
        selected = row["accepted_release_id"] or row["proposed_release_id"]
        match = next((c for c in candidates if isinstance(c, dict)
                      and c.get("release_id") == selected), None)
        row["candidate_title"] = str(match.get("title") or "")[:300] if match else ""
        row["candidate_date"] = str(match.get("date") or "")[:30] if match else ""
        row["candidate_count"] = len(candidates)
        row["match_status"] = ("INFERRED_OPERATOR_ACCEPTED" if row["accepted_release_id"]
                               else "INFERRED_NOT_PHYSICALLY_VERIFIED" if selected
                               else "UNRESOLVED")
    return {"jobs":rows, "engine_running":False,
            "notice":"Persistent Go archive reservations and safe reconciliation; no automatic retry after interruption."}
