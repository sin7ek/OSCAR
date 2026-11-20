"""Explicit, staging-independent, versioned archive metadata migration.

Opt-in only. Original published generation is moved, without mutation, to a
hidden retained archive version. The reviewed replacement is independently
verified before promotion. A durable SQLite journal allows interrupted
filesystem/Collection transitions to be reconciled without deleting audio.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import uuid
from datetime import datetime, timezone

from mutagen.flac import FLAC

from oscar import archive_metadata_scan as scanner
from oscar import archive_publish, collection_catalog as catalog
from oscar.archive_naming import safe_component
from oscar.metadata_staging import _streaminfo_md5_hex

_ALLOWED_FIELDS = {"CATALOGNUMBER", "LABEL", "BARCODE", "TITLE", "ARTIST"}
_CONFIRM = "APPLY_VERIFIED_ARCHIVE_REVISION"
_WORKER_LOCK = threading.Lock()
_RUNNING = set()
_WORKERS = {}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_revision_operations (
  operation_id TEXT PRIMARY KEY,
  source_path TEXT NOT NULL,
  dest_path TEXT NOT NULL,
  backup_path TEXT NOT NULL,
  stage_path TEXT NOT NULL,
  source_manifest_sha256 TEXT NOT NULL,
  source_publish_id TEXT NOT NULL,
  new_publish_id TEXT NOT NULL,
  proposal_fingerprints TEXT NOT NULL,
  target_catalog TEXT NOT NULL,
  target_label TEXT NOT NULL,
  plan_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_archive_revision_source ON archive_revision_operations(source_path,status);
"""


class RevisionError(ValueError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat()


def _db():
    db = scanner._db()
    db.executescript(_SCHEMA)
    return db


def _assert_opt_in():
    if os.environ.get("OSCAR_ENABLE_ARCHIVE_REVISIONS") != "1":
        raise RevisionError("Archive revisions disabled: set OSCAR_ENABLE_ARCHIVE_REVISIONS=1 after review")


def _plan(archive_path, *, lookup=None):
    snapshot = scanner._archive_snapshot(archive_path)
    root = catalog.archive_root()
    album_path = Path(snapshot["path"])
    if len(album_path.relative_to(root).parts) != 2:
        raise RevisionError("v1 archive migration supports single-CD album leaves only; multidisc requires a coordinated boxset migration")
    if scanner._digest(album_path / "manifest.json") != snapshot["manifest_sha256"]:
        raise RevisionError("Archive manifest changed during migration preview")
    source_manifest = json.loads((album_path / "manifest.json").read_text(encoding="utf-8"))
    if source_manifest.get("disc_total", 1) != 1:
        raise RevisionError("v1 migration cannot split or partially migrate a boxset")
    with _db() as db:
        rows = db.execute(
            "SELECT * FROM metadata_proposals WHERE archive_path=? AND status='accepted' ORDER BY fingerprint",
            (snapshot["path"],),
        ).fetchall()
        inflight = db.execute(
            "SELECT 1 FROM archive_revision_operations WHERE source_path=? AND status='prepared'",
            (snapshot["path"],),
        ).fetchone()
        indexed = db.execute("SELECT 1 FROM archive_items WHERE archive_path=?", (snapshot["path"],)).fetchone()
    if inflight:
        raise RevisionError("A previous archive revision needs reconciliation before another migration")
    if not indexed:
        raise RevisionError("Published album must first be imported into Collection")
    if not rows:
        raise RevisionError("There are no accepted metadata changes for this published album")
    candidates = scanner._fresh_values(snapshot, lookup or scanner.lookup_release_medium)
    accepted = []
    for row in rows:
        if (row["archive_revision"] != snapshot["manifest_sha256"]
                or row["publish_id"] != snapshot["publish_id"]
                or row["release_id"] != snapshot["release_id"]
                or row["field"] not in _ALLOWED_FIELDS):
            raise RevisionError("Accepted proposal is stale or not supported by archive revision v1")
        before, after = json.loads(row["before_json"]), json.loads(row["after_json"])
        matches = [
            entry for entry in candidates
            if entry[0] == row["scope"] and entry[1] == row["track"]
            and entry[2] == row["field"]
            and scanner._canonical(entry[3]) == before
            and scanner._canonical(entry[4]) == after
        ]
        if len(matches) != 1 or not isinstance(after, list) or not after:
            raise RevisionError("Accepted metadata differs from current MusicBrainz; rescan and review")
        if row["scope"] == "release" and row["field"] not in {"CATALOGNUMBER", "LABEL", "BARCODE"}:
            raise RevisionError("Unsupported release-scope metadata change")
        if row["scope"] == "track" and (row["field"] not in {"TITLE", "ARTIST"}
                or not 1 <= row["track"] <= len(snapshot["tracks"])):
            raise RevisionError("Unsupported track-scope metadata change")
        accepted.append({
            "fingerprint": row["fingerprint"], "scope": row["scope"],
            "track": row["track"], "field": row["field"],
            "before": before, "after": after,
        })
    parsed = catalog._metadata_from_path(album_path, source_manifest)
    catalog_now = parsed["catalog_number"]
    values = [item["after"] for item in accepted if item["field"] == "CATALOGNUMBER"]
    if len(values) > 1 or (values and len(values[0]) != 1):
        raise RevisionError("Catalog folder naming requires exactly one reviewed catalog number")
    desired_catalog = values[0][0] if values else catalog_now
    if desired_catalog and (safe_component(desired_catalog) != desired_catalog
                            or len(desired_catalog) > 110):
        raise RevisionError("Catalog number cannot safely be represented in the archive folder")
    label_values = [item["after"] for item in accepted if item["field"] == "LABEL"]
    if len(label_values) > 1:
        raise RevisionError("Conflicting label proposals")
    target_label = "; ".join(label_values[0]) if label_values else ""
    album_name = ((f"[{desired_catalog}] " if desired_catalog else "") +
                  parsed["title"] + " (" + parsed["year"] + ") [" +
                  snapshot["release_id"].split("-")[0] + "]")
    destination = root / album_path.parent.name / album_name
    if destination != album_path and (destination.exists() or destination.is_symlink()):
        raise RevisionError("Proposed catalog-based destination already exists: refusing collision")
    plan_core = {
        "source_path": snapshot["path"], "dest_path": str(destination),
        "original_manifest_sha256": snapshot["manifest_sha256"],
        "original_publish_id": snapshot["publish_id"],
        "release_id": snapshot["release_id"],
        "catalog_number": desired_catalog,
        "label": target_label,
        "track_count": len(snapshot["tracks"]),
        "accepted_changes": accepted,
    }
    plan_core["fingerprint"] = hashlib.sha256(
        scanner._stable_json(plan_core).encode("utf-8")
    ).hexdigest()
    plan_core["status"] = "requires_explicit_migration_approval"
    plan_core["note"] = (
        "No changes yet. Opt-in migration retains original archive in hidden history; "
        "creates fully verified tagged copies and updates Collection atomically. "
        "Only a single-CD leaf is supported."
    )
    return plan_core


def preview(archive_path):
    return _plan(archive_path)


def _verify_preserved_evidence(base, manifest):
    """Validate non-audio publication evidence, independent of original staging."""
    cue = manifest.get("cue") or {}
    filename = cue.get("filename")
    digest = cue.get("sha256")
    if (not isinstance(filename, str) or Path(filename).name != filename
            or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
        raise RevisionError("Original archive CUE lacks a verified manifest digest")
    path = base / filename
    if path.is_symlink() or not path.is_file() or scanner._digest(path) != digest:
        raise RevisionError("Original published CUE changed or is missing")
    for evidence in manifest.get("source_evidence") or []:
        if not isinstance(evidence, dict):
            raise RevisionError("Invalid archived extraction evidence manifest")
        relative = evidence.get("filename")
        wanted = evidence.get("sha256")
        if (not isinstance(relative, str) or not relative.startswith("ExtractionEvidence/")
                or Path(relative).is_absolute() or ".." in Path(relative).parts
                or not isinstance(wanted, str) or not re.fullmatch(r"[a-f0-9]{64}", wanted)):
            raise RevisionError("Unsafe original extraction evidence filename/hash")
        source = base / relative
        if (source.is_symlink() or not source.is_file()
                or scanner._digest(source) != wanted
                or source.stat().st_size != evidence.get("size")):
            raise RevisionError("Archived extraction CUE/log differs from original evidence")
    return True


def _copy_and_retag(plan, temp, source, *, flac_factory=None, runner=None):
    factory = flac_factory or FLAC
    command = runner or subprocess.run
    # Fail closed for symlinks anywhere in the original tree, including evidence.
    for base, dirs, files in os.walk(source, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(base) / name
            if path.is_symlink() or (not path.is_file() and not path.is_dir()):
                raise RevisionError("Unsafe linked or special file in original archive")
    shutil.copytree(source, temp, symlinks=False)
    manifest_path = temp / "manifest.json"
    original_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _verify_preserved_evidence(source, original_manifest)
    _verify_preserved_evidence(temp, original_manifest)
    changes = plan["accepted_changes"]
    files = original_manifest["files"]
    release_fields = {x["field"]: x["after"] for x in changes if x["scope"] == "release"}
    for entry in files:
        number = entry["track"]
        path = temp / entry["filename"]
        original_file = source / entry["filename"]
        if scanner._digest(original_file) != entry["sha256"]:
            raise RevisionError("Original archive FLAC changed during migration")
        flac = factory(str(path))
        audio_md5 = _streaminfo_md5_hex(flac.info.md5_signature)
        expected_audio = entry.get("streaminfo_audio_md5")
        if expected_audio and expected_audio != audio_md5:
            raise RevisionError("Archived audio STREAMINFO MD5 differs from publication evidence")
        modifications = {**release_fields}
        for item in changes:
            if item["scope"] == "track" and item["track"] == number:
                modifications[item["field"]] = item["after"]
        for field, values in modifications.items():
            flac[field] = values
        if modifications:
            flac.save()
        inspected = factory(str(path))
        if _streaminfo_md5_hex(inspected.info.md5_signature) != audio_md5:
            raise RevisionError("FLAC audio integrity changed while retagging")
        for field, values in modifications.items():
            actual = [str(x) for x in (inspected.get(field) or [])]
            if actual != values:
                raise RevisionError("Written FLAC metadata does not match reviewed proposal")
        checked = command(
            ["flac", "-t", "--silent", str(path)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            timeout=180, check=False,
        )
        if checked.returncode:
            raise RevisionError("Retagged FLAC failed audio-decoding verification")
        entry["sha256"] = scanner._digest(path)
        entry["streaminfo_audio_md5"] = audio_md5
    if "LABEL" in release_fields:
        old = original_manifest.get("label_info") or []
        names = set(release_fields["LABEL"])
        old_numbers = {str(i.get("name")): i.get("catalog_number")
                       for i in old if isinstance(i, dict) and i.get("name")}
        original_manifest["label_info"] = [
            {"name": name, "catalog_number": old_numbers.get(name)}
            for name in release_fields["LABEL"]
        ]
    if "CATALOGNUMBER" in release_fields:
        catalog_value = release_fields["CATALOGNUMBER"][0]
        original_manifest["label_info"] = [
            {**item, "catalog_number": catalog_value}
            for item in original_manifest.get("label_info") or [] if isinstance(item, dict)
        ]
    original_manifest["publish_id"] = uuid.uuid4().hex
    original_manifest["revision"] = {
        "parent_publish_id": plan["original_publish_id"],
        "parent_manifest_sha256": plan["original_manifest_sha256"],
        "source_archive_path": plan["source_path"],
        "proposal_fingerprints": [x["fingerprint"] for x in changes],
        "created_at": _now(),
        "type": "operator_approved_metadata_only",
        "audio_bytes_unchanged_verified_by_streaminfo_md5": True,
    }
    new_manifest = json.dumps(original_manifest, ensure_ascii=False, indent=2) + "\n"
    manifest_path.write_text(new_manifest, encoding="utf-8")
    # Verify every new FLAC against its NEW whole-file digest and manifest,
    # before any published directory is moved.
    for entry in files:
        if scanner._digest(temp / entry["filename"]) != entry["sha256"]:
            raise RevisionError("New archive FLAC hash validation failed")
    return original_manifest["publish_id"]


def _finalize(db, row, *, snapshot_verified=True):
    # Caller must have a verified promoted destination and retained original.
    source, dest = row["source_path"], row["dest_path"]
    fingerprints = json.loads(row["proposal_fingerprints"])
    if not fingerprints:
        raise RevisionError("Migration contains no approved changes")
    db.execute("BEGIN IMMEDIATE")
    current = db.execute("SELECT 1 FROM archive_items WHERE archive_path=?", (source,)).fetchone()
    if current:
        collisions = db.execute("SELECT 1 FROM archive_items WHERE archive_path=?", (dest,)).fetchone()
        if collisions and dest != source:
            raise RevisionError("Collection destination already indexed; cannot reconcile")
        db.execute(
            "UPDATE archive_items SET archive_path=?, catalog_number=?,"
            "label=CASE WHEN label='' THEN ? ELSE label END WHERE archive_path=?",
            (dest, row["target_catalog"], row["target_label"], source),
        )
    elif db.execute("SELECT 1 FROM archive_items WHERE archive_path=?", (dest,)).fetchone() is None:
        raise RevisionError("Neither old nor new Collection archive entry exists")
    for fp in fingerprints:
        item = db.execute("SELECT status,archive_revision FROM metadata_proposals WHERE fingerprint=?", (fp,)).fetchone()
        if item is None or item["status"] not in {"accepted", "applied"}:
            raise RevisionError("Approved metadata decision is missing during reconciliation")
        if item["status"] == "accepted":
            db.execute("UPDATE metadata_proposals SET status='applied',decided_at=? WHERE fingerprint=?",
                       (_now(), fp))
            db.execute(
                "INSERT INTO metadata_decision_events "
                "(fingerprint,decision,happened_at,archive_revision) VALUES (?,?,?,?)",
                (fp, "applied", _now(), item["archive_revision"]),
            )
    db.execute(
        "UPDATE archive_revision_operations SET status='completed',finished_at=?,error='' WHERE operation_id=?",
        (_now(), row["operation_id"]),
    )
    db.commit()


def _verify_promoted(row):
    dest = Path(row["dest_path"])
    old = Path(row["backup_path"])
    if not dest.is_dir() or dest.is_symlink() or not old.is_dir() or old.is_symlink():
        raise RevisionError("Promoted revision and retained original not both available")
    source_manifest = old / "manifest.json"
    if scanner._digest(source_manifest) != row["source_manifest_sha256"]:
        raise RevisionError("Retained original manifest hash mismatch")
    snapshot = scanner._archive_snapshot(str(dest))
    if snapshot["publish_id"] != row["new_publish_id"] or snapshot["release_id"] != json.loads((old / "manifest.json").read_text())["release_id"]:
        raise RevisionError("Published revision identity differs from journal")
    return snapshot


def _journal(row):
    with _db() as db:
        db.execute("""INSERT INTO archive_revision_operations
          (operation_id,source_path,dest_path,backup_path,stage_path,
          source_manifest_sha256,source_publish_id,new_publish_id,
          proposal_fingerprints,target_catalog,target_label,plan_fingerprint,status,started_at)
          VALUES (:operation_id,:source_path,:dest_path,:backup_path,:stage_path,
          :source_manifest_sha256,:source_publish_id,:new_publish_id,
          :proposal_fingerprints,:target_catalog,:target_label,:plan_fingerprint,'prepared',:started_at)""", row)


def apply(archive_path, fingerprint, confirmation):
    _assert_opt_in()
    if confirmation != _CONFIRM:
        raise RevisionError("Explicit archive revision confirmation required")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise RevisionError("Invalid reviewed migration fingerprint")
    root = catalog.archive_root()
    lock_path = root / ".oscar-publish.lock"
    if lock_path.is_symlink():
        raise RevisionError("Unsafe archive publisher lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        plan = _plan(archive_path)
        if plan["fingerprint"] != fingerprint:
            raise RevisionError("Archive or MusicBrainz metadata changed since migration preview")
        old = Path(plan["source_path"])
        dest = Path(plan["dest_path"])
        operation_id = uuid.uuid4().hex
        temp = old.parent / (".oscar-unpublished-revision-" + operation_id)
        history_parent = root / ".oscar-archive-versions" / plan["original_publish_id"]
        if (history_parent.is_symlink() or history_parent.parent.is_symlink()
                or history_parent.parent.exists() and not history_parent.parent.is_dir()):
            raise RevisionError("Unsafe archive revision history directory")
        history_parent.mkdir(parents=True, exist_ok=True)
        hidden = history_parent / operation_id
        for path in (temp, hidden):
            if path.exists() or path.is_symlink():
                raise RevisionError("Archive revision path already exists")
        if dest != old and (dest.exists() or dest.is_symlink()):
            raise RevisionError("Archive destination collision")
        moved = False
        try:
            new_publish_id = _copy_and_retag(plan, temp, old)
            fields = {
                "operation_id": operation_id,
                "source_path": str(old), "dest_path": str(dest),
                "backup_path": str(hidden), "stage_path": str(temp),
                "source_manifest_sha256": plan["original_manifest_sha256"],
                "source_publish_id": plan["original_publish_id"],
                "new_publish_id": new_publish_id,
                "proposal_fingerprints": json.dumps([x["fingerprint"] for x in plan["accepted_changes"]]),
                "target_catalog": plan["catalog_number"],
                "target_label": plan["label"],
                "plan_fingerprint": plan["fingerprint"],
                "started_at": _now(),
            }
            _journal(fields)
            archive_publish._rename_noreplace(old, hidden)
            moved = True
            archive_publish._rename_noreplace(temp, dest)
            with _db() as db:
                row = db.execute(
                    "SELECT * FROM archive_revision_operations WHERE operation_id=?",
                    (operation_id,),
                ).fetchone()
                _verify_promoted(row)
                _finalize(db, row)
            return {"operation_id": operation_id, "status": "completed",
                    "archive_path": str(dest), "original_retained_at": str(hidden),
                    "new_publish_id": new_publish_id, "source_preserved": True,
                    "note": "Approved metadata applied to verified archive revision; no staging files used."}
        except Exception as exc:
            # If publication failed before the new destination appeared, restore
            # original live path, retaining the isolated staging candidate.
            if moved and not dest.exists() and hidden.exists() and not old.exists():
                try:
                    archive_publish._rename_noreplace(hidden, old)
                    with _db() as db:
                        db.execute(
                            "UPDATE archive_revision_operations SET status='rolled_back',"
                            "finished_at=?,error=? WHERE operation_id=?",
                            (_now(), str(type(exc).__name__)[:100], operation_id),
                        )
                except Exception:
                    pass
            raise RevisionError(
                "Archive revision not fully completed; check/reconcile the durable revision journal "
                "before starting another operation: " + str(exc)[:200]
            ) from exc
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def reconcile(operation_id):
    """Operator-invoked crash recovery: finalize verified publication or restore old."""
    _assert_opt_in()
    if not re.fullmatch(r"[a-f0-9]{32}", operation_id or ""):
        raise RevisionError("Invalid archive revision operation")
    root = catalog.archive_root()
    with (root / ".oscar-publish.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with _db() as db:
            row = db.execute(
                "SELECT * FROM archive_revision_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
        if row is None:
            raise RevisionError("Archive revision operation does not exist")
        if row["status"] == "completed":
            return {"operation_id": operation_id, "status": "completed"}
        if row["status"] != "prepared":
            raise RevisionError("Archive revision is not awaiting reconciliation")
        old, new, backup = (Path(row[key]) for key in ("source_path","dest_path","backup_path"))
        if new.is_dir() and backup.is_dir():
            _verify_promoted(row)
            with _db() as db:
                _finalize(db, row)
            return {"operation_id": operation_id, "status": "completed"}
        if not new.exists() and backup.is_dir() and not old.exists():
            archive_publish._rename_noreplace(backup, old)
        if old.is_dir() and not backup.exists() and (old == new or not new.exists()):
            with _db() as db:
                db.execute(
                    "UPDATE archive_revision_operations SET status='rolled_back',finished_at=? "
                    "WHERE operation_id=?", (_now(), operation_id),
                )
            return {"operation_id": operation_id, "status": "rolled_back"}
        raise RevisionError("Ambiguous archive filesystem state; do not rename or delete manually")


def start(archive_path, fingerprint, confirmation):
    """Start one reviewed migration in a background worker; no proxy timeout."""
    _assert_opt_in()
    if confirmation != _CONFIRM:
        raise RevisionError("Explicit archive revision confirmation required")
    plan = _plan(archive_path)
    if plan["fingerprint"] != fingerprint:
        raise RevisionError("Archive metadata preview has changed; review again")
    key = plan["source_path"]
    task_id = uuid.uuid4().hex
    with _WORKER_LOCK:
        if _RUNNING:
            raise RevisionError("Another metadata archive revision is currently running")
        _RUNNING.add(key)
        _WORKERS[task_id] = {
            "task_id": task_id, "archive_path": key, "status": "running",
            "result": None, "error": None,
        }
    def work():
        try:
            result = apply(key, fingerprint, confirmation)
            with _WORKER_LOCK:
                _WORKERS[task_id].update(status="completed", result=result)
        except Exception as exc:
            with _WORKER_LOCK:
                _WORKERS[task_id].update(
                    status="failed", error=f"{type(exc).__name__}: {exc}"[:350])
        finally:
            with _WORKER_LOCK:
                _RUNNING.discard(key)
    try:
        threading.Thread(target=work, daemon=True,
                         name="oscar-archive-revision-"+task_id[:8]).start()
    except Exception:
        with _WORKER_LOCK:
            _RUNNING.discard(key)
            _WORKERS.pop(task_id, None)
        raise
    return task_status(task_id)


def task_status(task_id):
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-f0-9]{32}", task_id):
        raise RevisionError("Invalid archive revision worker ID")
    with _WORKER_LOCK:
        item = _WORKERS.get(task_id)
        if item is None:
            raise RevisionError("Worker status unavailable after restart; inspect durable revision operations")
        return dict(item)


def operations():
    with _db() as db:
        rows = db.execute(
            "SELECT operation_id,source_path,dest_path,backup_path,status,started_at,finished_at "
            "FROM archive_revision_operations ORDER BY started_at DESC LIMIT 100"
        ).fetchall()
    return {"items": [dict(row) for row in rows]}
