"""Opt-in irreversible deletion of ONE previously verified retained generation.

This is intentionally separate from normal archive revision and from Verify.
No cleanup runs on scanning, startup, acceptance, or normal archive publication.
A durable cleanup journal records intent *before* deleting history. Failures
remain in prepared state for manual investigation, never automatic retries.
"""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone

from oscar import archive_revision as revision
from oscar import archive_revision_verify as verify_engine
from oscar import collection_catalog as catalog


class ArchiveCleanupError(ValueError):
    pass


CONFIRM = "PERMANENTLY_DELETE_VERIFIED_ORIGINAL_VERSION"
_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_revision_cleanups (
 operation_id TEXT PRIMARY KEY,
 original_backup_path TEXT NOT NULL,
 verification_fingerprint TEXT NOT NULL,
 status TEXT NOT NULL,
 started_at TEXT NOT NULL,
 completed_at TEXT NOT NULL DEFAULT ''
);
"""


def _db():
    db = revision._db()
    db.executescript(_SCHEMA)
    return db


def cleanup_status(operation_id):
    with _db() as db:
        row = db.execute(
            "SELECT status,completed_at FROM archive_revision_cleanups WHERE operation_id=?",
            (operation_id,)
        ).fetchone()
    return dict(row) if row else None


def enabled():
    return os.environ.get("OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP") == "1"


def clean(operation_id, verification_fingerprint, confirmation,
          *, external_backup_confirmed=False):
    """Remove only the one retained original identified in completed journal.

    The entire independent Verify runs AGAIN, under the publisher's exclusive
    filesystem lock. A stale verification receipt cannot permit deletion.
    """
    if not enabled():
        raise ArchiveCleanupError(
            "Permanent history deletion is disabled. Explicitly enable "
            "OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP=1 after external backups."
        )
    if confirmation != CONFIRM or not external_backup_confirmed:
        raise ArchiveCleanupError(
            "Permanent archive deletion requires exact confirmation and an "
            "affirmation that an external recovery backup is available"
        )
    if not isinstance(operation_id, str) or not re.fullmatch(r"[a-f0-9]{32}", operation_id):
        raise ArchiveCleanupError("Invalid original-version operation ID")
    if not isinstance(verification_fingerprint, str) or not re.fullmatch(
        r"[a-f0-9]{64}", verification_fingerprint
    ):
        raise ArchiveCleanupError("Run Verify first; a valid content-bound receipt is required")
    root = catalog.archive_root()
    lock_path = root / ".oscar-publish.lock"
    if lock_path.is_symlink():
        raise ArchiveCleanupError("Unsafe publisher lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if cleanup_status(operation_id) is not None:
                raise ArchiveCleanupError(
                    "Cleanup already recorded, or interrupted; inspect the durable journal. "
                    "No automatic retry is permitted."
                )
            with _db() as db:
                row = db.execute(
                    "SELECT * FROM archive_revision_operations WHERE operation_id=?",
                    (operation_id,)
                ).fetchone()
                unfinished = db.execute(
                    "SELECT 1 FROM archive_revision_operations WHERE status='prepared' LIMIT 1"
                ).fetchone()
            if row is None or row["status"] != "completed" or unfinished:
                raise ArchiveCleanupError(
                    "Archive revision incomplete or another interrupted operation needs reconciliation"
                )
            # A superseded revision's published output is retained as the
            # original of its successor. Never delete its history through
            # an old verification receipt or a manually crafted API request.
            with _db() as db:
                successor = db.execute(
                    "SELECT 1 FROM archive_revision_operations "
                    "WHERE source_publish_id=? AND source_path=? LIMIT 1",
                    (row["new_publish_id"], row["dest_path"]),
                ).fetchone()
            if successor:
                raise ArchiveCleanupError(
                    "Historical revision is part of a later archive chain; "
                    "cleanup is prohibited"
                )
            with _db() as db:
                predecessor = db.execute(
                    "SELECT 1 FROM archive_revision_operations "
                    "WHERE new_publish_id=? AND dest_path=? AND status='completed' LIMIT 1",
                    (row["source_publish_id"], row["source_path"]),
                ).fetchone()
            if predecessor:
                raise ArchiveCleanupError(
                    "This retained original is a previous revision's output; "
                    "cleanup would break archived ancestry and is prohibited"
                )
            from oscar import archive_history
            backup = archive_history.retained(root, row["source_publish_id"], operation_id,
                                              recorded=row["backup_path"])
            if (not backup.is_dir() or backup.is_symlink()
                    or backup.resolve(strict=True) != backup
                    or backup.parent.is_symlink()
                    or backup.parent.parent.is_symlink()):
                raise ArchiveCleanupError("Refusing cleanup of unknown or unsafe archive directory")
            if not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
                raise ArchiveCleanupError("Safe fd-based recursive cleanup unavailable")
            # Reverify new and original FLAC audio, every tag, manifest SHA,
            # CUE/source evidence and Collection within this same lock.
            report = verify_engine._verify_locked(operation_id)
            if report["status"] != "verified" or report["verification_fingerprint"] != verification_fingerprint:
                raise ArchiveCleanupError("Verification receipt is stale; run Verify again")
            with _db() as db:
                db.execute(
                    "INSERT INTO archive_revision_cleanups "
                    "(operation_id,original_backup_path,verification_fingerprint,status,started_at) "
                    "VALUES (?,?,?,'prepared',?)",
                    (operation_id, str(backup), verification_fingerprint,
                     datetime.now(timezone.utc).isoformat()),
                )
            # This irrevocably destroys the *retained original generation*
            # after its content has been verified. Live archive is NEVER passed
            # to rmtree; a failure leaves prepared status for investigation.
            shutil.rmtree(backup)
            with _db() as db:
                db.execute(
                    "UPDATE archive_revision_cleanups SET status='completed',completed_at=? "
                    "WHERE operation_id=?",
                    (datetime.now(timezone.utc).isoformat(), operation_id),
                )
            for parent in (backup.parent, backup.parent.parent):
                try:
                    parent.rmdir()
                except OSError:
                    break
            return {
                "operation_id": operation_id,
                "status": "cleaned",
                "original_version_removed": str(backup),
                "live_publication_unchanged": True,
                "warning": "Original archived version deleted permanently. Recovery now depends on an external backup.",
            }
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
