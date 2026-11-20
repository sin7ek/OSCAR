"""Recoverable, explicitly approved group migration of present physical boxset CDs.

A directory tree cannot be atomically swapped across several leaf paths. This
engine prepares all leaves, journals intent, publishes under OSCAR's exclusive
lock and commits Collection updates only after every leaf verifies. On
interruption the operator must explicitly reconcile; no silent deletion.
"""
from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
import re
import threading
import uuid

from oscar import archive_metadata_scan as scanner
from oscar import archive_publish, archive_revision as single
from oscar import archive_revision_boxset as boxset
from oscar import collection_catalog as catalog

_CONFIRM = "APPLY_COORDINATED_BOXSET_REVISION"
_ID = re.compile(r"[0-9a-f]{32}\Z")
_JOBS = {}
_RUNNING = set()
_MUTEX = threading.Lock()
_SCHEMA = """
CREATE TABLE IF NOT EXISTS boxset_revision_operations (
 operation_id TEXT PRIMARY KEY,
 release_id TEXT NOT NULL,
 plan_fingerprint TEXT NOT NULL,
 status TEXT NOT NULL,
 entries_json TEXT NOT NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT NOT NULL DEFAULT '',
 error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_boxset_revision_release
 ON boxset_revision_operations(release_id,status);
"""


class BoxsetApplyError(ValueError):
    pass


def _db():
    db = single._db()
    db.executescript(_SCHEMA)
    return db


def _enabled():
    if os.environ.get("OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS") != "1":
        raise BoxsetApplyError(
            "Boxset Apply disabled; explicit OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS=1 required"
        )


def _entries(review, operation_id):
    root = catalog.archive_root()
    entries = []
    for disc in review["disc_reviews"]:
        if disc["label_status"] != "approved_for_review" or not disc["accepted_fingerprint"]:
            raise BoxsetApplyError(
                "Every present disc must have one current accepted LABEL change"
            )
        source = Path(disc["archive_path"])
        if source.is_symlink() or not source.is_dir():
            raise BoxsetApplyError("Unsafe original disc directory")
        with _db() as db:
            proposals = db.execute(
                "SELECT fingerprint,field,scope,track,before_json,after_json "
                "FROM metadata_proposals WHERE archive_path=? AND status='accepted'",
                (str(source),),
            ).fetchall()
        if len(proposals) != 1 or proposals[0]["fingerprint"] != disc["accepted_fingerprint"]:
            raise BoxsetApplyError("Unreviewed or extra metadata proposals on a disc")
        proposal = proposals[0]
        if proposal["field"] != "LABEL" or proposal["scope"] != "release" or proposal["track"] != 0:
            raise BoxsetApplyError("Group v1 supports approved release LABEL only")
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("publish_id") != disc["publication_id"]:
            raise BoxsetApplyError("Original publication changed")
        hidden = root / ".oscar-archive-versions" / disc["publication_id"] / (
            operation_id + "-disc-" + str(disc["disc"]).zfill(2)
        )
        temp = source.parent / (
            ".oscar-unpublished-boxset-" + operation_id + "-" + str(disc["disc"]).zfill(2)
        )
        entries.append({
            "disc": disc["disc"], "source": str(source), "backup": str(hidden),
            "temp": str(temp), "old_publish_id": disc["publication_id"],
            "old_manifest_sha256": disc["manifest_sha256"],
            "new_publish_id": "",
            "fingerprint": disc["accepted_fingerprint"],
            "before": json.loads(proposal["before_json"]),
            "after": json.loads(proposal["after_json"]),
        })
    return entries


def _validate_leaf(path, entry, *, new):
    if path.is_symlink() or not path.is_dir():
        raise BoxsetApplyError("Expected verified disc generation missing: " + str(path))
    manifest_path = path / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise BoxsetApplyError("Missing publication manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_id = entry["new_publish_id"] if new else entry["old_publish_id"]
    if manifest.get("publish_id") != expected_id:
        raise BoxsetApplyError("Disc publication identity differs from group journal")
    if not new and scanner._digest(manifest_path) != entry["old_manifest_sha256"]:
        raise BoxsetApplyError("Retained-original manifest SHA-256 differs")
    if new:
        rev = manifest.get("revision") or {}
        if (rev.get("parent_publish_id") != entry["old_publish_id"]
                or rev.get("parent_manifest_sha256") != entry["old_manifest_sha256"]):
            raise BoxsetApplyError("New disc does not link to exact original")
    single._verify_preserved_evidence(path, manifest)
    files = manifest.get("files") or []
    if not files:
        raise BoxsetApplyError("No published FLACs for disc")
    for item in files:
        name = item.get("filename", "")
        if not isinstance(name, str) or Path(name).name != name:
            raise BoxsetApplyError("Unsafe FLAC filename in publication")
        audio = path / name
        if audio.is_symlink() or not audio.is_file() or scanner._digest(audio) != item.get("sha256"):
            raise BoxsetApplyError("FLAC does not match published SHA-256")
        if new:
            from mutagen.flac import FLAC
            actual = FLAC(str(audio))
            if scanner._canonical(actual.get("LABEL") or []) != scanner._canonical(entry["after"]):
                raise BoxsetApplyError("New FLAC LABEL does not match approved values")
            import subprocess
            result = subprocess.run(["flac", "-t", "--silent", str(audio)],
                                    capture_output=True, timeout=180, check=False)
            if result.returncode:
                raise BoxsetApplyError("New FLAC failed independent decoding")
    return manifest


def _advance(entries):
    """Idempotent, no-overwrite promotion; invoked only under archive lock."""
    for entry in entries:
        source, backup, temp = (Path(entry[k]) for k in ("source", "backup", "temp"))
        root = catalog.archive_root()
        history = root / ".oscar-archive-versions"
        if history.is_symlink() or (history.exists() and not history.is_dir()):
            raise BoxsetApplyError("Unsafe retained-history parent")
        if backup.parent.is_symlink() or (
            backup.parent.exists() and not backup.parent.is_dir()
        ):
            raise BoxsetApplyError("Unsafe retained-history publication directory")
        if source.is_symlink() or backup.is_symlink() or temp.is_symlink():
            raise BoxsetApplyError("Unsafe symbolic link in group publication")
        if backup.exists():
            _validate_leaf(backup, entry, new=False)
        if source.exists():
            live_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
            live_id = live_manifest.get("publish_id")
            if live_id == entry["new_publish_id"]:
                if not backup.exists() or temp.exists():
                    raise BoxsetApplyError("Promoted leaf has inconsistent original/staging state")
                _validate_leaf(source, entry, new=True)
                continue
            if live_id != entry["old_publish_id"] or backup.exists():
                raise BoxsetApplyError("Ambiguous old and retained disc generations")
            _validate_leaf(source, entry, new=False)
            _validate_leaf(temp, entry, new=True)
            backup.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists() or backup.is_symlink():
                raise BoxsetApplyError("Original history destination collision")
            archive_publish._rename_noreplace(source, backup)
        else:
            if not backup.exists():
                raise BoxsetApplyError("Disc missing without a retained original")
        _validate_leaf(temp, entry, new=True)
        archive_publish._rename_noreplace(temp, source)
        _validate_leaf(source, entry, new=True)


def _verify_audio_pair(entry):
    """Check independent decoded-audio identity of retained and new generations."""
    from mutagen.flac import FLAC
    from oscar.metadata_staging import _streaminfo_md5_hex
    old = Path(entry["backup"])
    new = Path(entry["source"])
    original_manifest = json.loads((old / "manifest.json").read_text(encoding="utf-8"))
    new_manifest = json.loads((new / "manifest.json").read_text(encoding="utf-8"))
    if ((original_manifest.get("release_id"), original_manifest.get("disc_number"),
         original_manifest.get("disc_total")) !=
        (new_manifest.get("release_id"), new_manifest.get("disc_number"),
         new_manifest.get("disc_total"))):
        raise BoxsetApplyError("Physical release/medium identity changed in revised generation")
    original_files = {x["filename"]: x for x in original_manifest.get("files") or []}
    revised_files = {x["filename"]: x for x in new_manifest.get("files") or []}
    if not original_files or set(original_files) != set(revised_files):
        raise BoxsetApplyError("Published track count/names differ from original CD")
    for filename in original_files:
        original_audio = _streaminfo_md5_hex(FLAC(str(old / filename)).info.md5_signature)
        revised_audio = _streaminfo_md5_hex(FLAC(str(new / filename)).info.md5_signature)
        if original_audio != revised_audio:
            raise BoxsetApplyError("Decoded-audio STREAMINFO MD5 differs from retained CD rip")
    return True


def _finalize(operation_id, entries):
    for entry in entries:
        _validate_leaf(Path(entry["backup"]), entry, new=False)
        _validate_leaf(Path(entry["source"]), entry, new=True)
        _verify_audio_pair(entry)
    with _db() as db:
        db.execute("BEGIN IMMEDIATE")
        operation = db.execute(
            "SELECT status FROM boxset_revision_operations WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        if operation is None or operation["status"] != "prepared":
            raise BoxsetApplyError("Group operation no longer awaiting finalization")
        for entry in entries:
            item = db.execute(
                "SELECT status,archive_path FROM metadata_proposals WHERE fingerprint=?",
                (entry["fingerprint"],),
            ).fetchone()
            if item is None or item["status"] != "accepted" or item["archive_path"] != entry["source"]:
                raise BoxsetApplyError("Group approval changed before database commit")
            row = db.execute(
                "SELECT label,label_provenance FROM archive_items WHERE archive_path=?",
                (entry["source"],),
            ).fetchone()
            if row is None:
                raise BoxsetApplyError("Disc disappeared from Collection")
            permitted = ("", "archive_manifest_label_info", "archived_flac_label_tag",
                         "musicbrainz_exact_release_catalog_match",
                         "archive_revision_approved_labels")
            if row["label"] and row["label_provenance"] not in permitted:
                raise BoxsetApplyError("Manual Collection label cannot be overwritten")
            db.execute(
                "UPDATE archive_items SET label=?,label_provenance=? WHERE archive_path=?",
                ("; ".join(entry["after"]), "archive_revision_approved_labels", entry["source"]),
            )
            db.execute(
                "UPDATE metadata_proposals SET status='applied',decided_at=? WHERE fingerprint=?",
                (single._now(), entry["fingerprint"]),
            )
            db.execute(
                "INSERT INTO metadata_decision_events "
                "(fingerprint,decision,happened_at,archive_revision) VALUES (?,?,?,?)",
                (entry["fingerprint"], "applied", single._now(), entry["old_manifest_sha256"]),
            )
        db.execute(
            "UPDATE boxset_revision_operations SET status='completed',finished_at=?,error='' "
            "WHERE operation_id=?", (single._now(), operation_id),
        )
        db.commit()


def apply(release_id, fingerprint, confirmation, *, lookup=None):
    _enabled()
    if confirmation != _CONFIRM:
        raise BoxsetApplyError("Explicit group migration confirmation required")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise BoxsetApplyError("Invalid group preview fingerprint")
    root = catalog.archive_root()
    lock_path = root / ".oscar-publish.lock"
    if lock_path.is_symlink():
        raise BoxsetApplyError("Unsafe archive lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with _db() as db:
            pending = db.execute(
                "SELECT operation_id FROM boxset_revision_operations "
                "WHERE release_id=? AND status='prepared'", (release_id,),
            ).fetchone()
        if pending:
            raise BoxsetApplyError("An interrupted group must be reconciled before another Apply")
        review = boxset.preview(release_id, lookup=lookup)
        if review["fingerprint"] != fingerprint:
            raise BoxsetApplyError("Stale group preview: recheck newly published discs and approvals")
        if not review["all_present_discs_reviewed"]:
            raise BoxsetApplyError("Not all present discs are approved")
        operation_id = uuid.uuid4().hex
        entries = _entries(review, operation_id)
        # No published original is moved until ALL candidate FLACs/evidence pass.
        for entry in entries:
            source, temp, backup = (Path(entry[k]) for k in ("source","temp","backup"))
            if temp.exists() or temp.is_symlink() or backup.exists() or backup.is_symlink():
                raise BoxsetApplyError("Group stage or retained-original path collision")
            plan = {
                "accepted_changes": [{
                    "scope": "release", "track": 0, "field": "LABEL",
                    "before": entry["before"], "after": entry["after"],
                    "fingerprint": entry["fingerprint"],
                }],
                "original_publish_id": entry["old_publish_id"],
                "original_manifest_sha256": entry["old_manifest_sha256"],
                "source_path": entry["source"],
            }
            entry["new_publish_id"] = single._copy_and_retag(plan, temp, source)
            _validate_leaf(temp, entry, new=True)
        with _db() as db:
            db.execute(
                "INSERT INTO boxset_revision_operations "
                "(operation_id,release_id,plan_fingerprint,status,entries_json,started_at) "
                "VALUES (?,?,?,'prepared',?,?)",
                (operation_id, release_id, fingerprint, json.dumps(entries), single._now()),
            )
        try:
            _advance(entries)
            _finalize(operation_id, entries)
        except Exception as exc:
            # Keep the complete journal and all generations for explicit recovery.
            with _db() as db:
                db.execute(
                    "UPDATE boxset_revision_operations SET error=? WHERE operation_id=?",
                    (str(exc)[:300], operation_id),
                )
            raise BoxsetApplyError(
                "Group publication requires operator reconciliation; do not move or delete files: "
                + str(exc)[:180]
            ) from exc
        return {"operation_id": operation_id, "status": "completed",
                "discs": [e["disc"] for e in entries],
                "originals_retained": [e["backup"] for e in entries]}


def reconcile(operation_id):
    _enabled()
    if not isinstance(operation_id, str) or not _ID.fullmatch(operation_id):
        raise BoxsetApplyError("Invalid group operation ID")
    root = catalog.archive_root()
    with (root / ".oscar-publish.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with _db() as db:
            row = db.execute(
                "SELECT * FROM boxset_revision_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
        if row is None:
            raise BoxsetApplyError("Group operation not found")
        if row["status"] == "completed":
            return {"operation_id": operation_id, "status": "completed"}
        if row["status"] != "prepared":
            raise BoxsetApplyError("Group is not eligible for recovery")
        entries = json.loads(row["entries_json"])
        _advance(entries)
        _finalize(operation_id, entries)
        return {"operation_id": operation_id, "status": "completed",
                "discs": [e["disc"] for e in entries]}


def operations():
    with _db() as db:
        rows = db.execute(
            "SELECT operation_id,release_id,status,started_at,finished_at,error "
            "FROM boxset_revision_operations ORDER BY started_at DESC LIMIT 100"
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


def start(release_id, fingerprint, confirmation):
    """Run potentially long FLAC verification without relying on proxy timeout."""
    _enabled()
    if confirmation != _CONFIRM:
        raise BoxsetApplyError("Explicit group migration confirmation required")
    # Verify a preview exists, including the exact currently indexed physical discs.
    review = boxset.preview(release_id)
    if review["fingerprint"] != fingerprint or not review["apply_supported"]:
        raise BoxsetApplyError("Group plan changed or is not approved for Apply")
    task_id = uuid.uuid4().hex
    with _MUTEX:
        if _RUNNING:
            raise BoxsetApplyError("A coordinated boxset migration is already running")
        _RUNNING.add(release_id)
        _JOBS[task_id] = {
            "task_id": task_id, "status": "running",
            "release_id": release_id, "result": None, "error": None,
        }

    def work():
        try:
            result = apply(release_id, fingerprint, confirmation)
            with _MUTEX:
                _JOBS[task_id].update(status="completed", result=result)
        except Exception as exc:
            with _MUTEX:
                _JOBS[task_id].update(
                    status="failed", error=f"{type(exc).__name__}: {exc}"[:400]
                )
        finally:
            with _MUTEX:
                _RUNNING.discard(release_id)

    try:
        threading.Thread(target=work, daemon=True,
                         name="oscar-boxset-"+task_id[:8]).start()
    except Exception:
        with _MUTEX:
            _RUNNING.discard(release_id)
            _JOBS.pop(task_id, None)
        raise
    return task_status(task_id)


def task_status(task_id):
    if not isinstance(task_id, str) or not _ID.fullmatch(task_id):
        raise BoxsetApplyError("Invalid group task ID")
    with _MUTEX:
        item = _JOBS.get(task_id)
        if item is None:
            raise BoxsetApplyError(
                "Worker unavailable after restart; inspect durable group operation journal"
            )
        return dict(item)
