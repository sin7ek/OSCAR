"""Inventory disposable copies and recheck each selected item before removal."""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil

from mutagen.flac import FLAC

from oscar import (archive_audit, archive_history, archive_publish, cd_extra,
                   collection_catalog, ripping, workflow_ledger)

_ID = re.compile(r"[a-f0-9]{32}")
_JOB = re.compile(r"oscar-([a-f0-9]{32})")
_EXCLUDED = {archive_history.LEGACY, "old-publications", "ExtractionEvidence",
             "CD-Extra", "Verification", "FailedAttempts"}
_ERRORS = (OSError, ValueError, RuntimeError, KeyError, TypeError)
_ACTIVE = {"RIP_IN_PROGRESS", "METADATA_COPY_RUNNING", "ARCHIVE_PUBLISH_RUNNING"}
CONFIRM = "CLEAN_SELECTED_OSCAR_ITEMS"
LOG = logging.getLogger(__name__)


def _digest(path):
    return archive_audit._sha256(path)


def _safe_tree(path):
    if path.is_symlink() or not path.is_dir() or path.resolve() != path:
        raise ValueError("Unsafe cleanup directory")
    files = {}
    for directory, dirs, names in os.walk(path, onerror=_walk_error):
        base = Path(directory)
        for name in dirs:
            if (base / name).is_symlink():
                raise ValueError("Directory contains a symbolic link")
        for name in names:
            file = base / name
            if file.is_symlink() or not file.is_file():
                raise ValueError("Directory contains a link or special file")
            info = file.stat()
            files[file.relative_to(path).as_posix()] = (info.st_size, info.st_mtime_ns, info.st_ino)
    return files


def _walk_error(error):
    raise error


def _archive_index(root):
    by_job, by_disc = {}, {}
    for directory, dirs, names in os.walk(root, onerror=_walk_error):
        base = Path(directory)
        dirs[:] = [name for name in dirs if name not in _EXCLUDED
                   and not name.startswith(".") and not (base / name).is_symlink()]
        if "manifest.json" not in names:
            continue
        try:
            manifest = collection_catalog._read_manifest(base)
        except _ERRORS:
            continue
        if manifest:
            by_job.setdefault(manifest.get("job_id"), []).append((base, manifest))
            key = (manifest["release_id"], manifest.get("disc_number", 1))
            by_disc.setdefault(key, []).append((base, manifest))
    return by_job, by_disc


def _verify_archive(path, manifest):
    result = archive_audit.audit_release(path)
    if result["status"] == "FAIL" or any(w["code"] in {"EVIDENCE_NOT_EMBEDDED", "MISSING_CUE"}
                                        for w in result["warnings"]):
        raise ValueError("Active archive failed integrity or extraction-evidence checks")
    if artwork := manifest.get("artwork"):
        cover = archive_audit._safe_file(path, "folder.jpg")
        if cover is None or _digest(cover) != artwork.get("sha256"):
            raise ValueError("Archive artwork differs from its manifest")


def _live_worker(job):
    from oscar import classical_v2, metadata_staging, track_recovery, verification

    return (ripping._JOBS.get(job, {}).get("status") in {"queued", "running"}
            or any(job in worker._RUNNING for worker in (classical_v2, metadata_staging, track_recovery, verification))
            or any(key[0] == job for key in tuple(archive_publish._RUNNING)))


def _staging_candidate(path, job, files, matches, workflows, dependencies, *, verify):
    if _live_worker(job) or workflows.get(job, {}).get("phase") in _ACTIVE:
        raise ValueError("Job has active or unresolved work")
    if job in dependencies:
        raise ValueError("Job provides evidence for another staged Track Recovery")
    state = json.loads((path / "state.json").read_text(encoding="utf-8"))
    if state.get("id") != job or state.get("status") != "needs_verification":
        raise ValueError("Staging job has no completed extraction to match")
    if len(matches) != 1:
        raise ValueError("Expected one matching active archive for this exact staging job")
    destination, manifest = matches[0]
    if manifest.get("source_type") != "PHYSICAL_CD_RIP":
        raise ValueError("Special publication or recovery source requires separate review")
    audio = state.get("files_sha256") or {}
    entries = manifest["files"]
    if len(audio) != len(entries) or any(
            not re.fullmatch(r"audio/\d+ - [^/]+\.flac", name) for name in audio):
        raise ValueError("Staged audio inventory differs from the publication")
    archived_evidence = {e["original_staging_path"]: e["sha256"]
                         for e in manifest.get("source_evidence", [])}
    required = {name for name in files if name.endswith((".cue", ".log")) and
                len(Path(name).parts) <= 2 and ("/" not in name or name.startswith("audio/"))}
    required.update(name for name in ("verification-report.json", "ctdb-report.json")
                    if name in files)
    if not any(name.endswith(".cue") for name in required) or not required <= archived_evidence.keys():
        raise ValueError("Staging has original evidence missing from Archive")
    if any(name.startswith("audio/") and name not in audio and name not in required
           and not name.lower().endswith((".bin", ".bin.partial", ".iso")) for name in files):
        raise ValueError("Staging contains unrecognized files in the audio folder")
    from oscar import edition_provenance

    provenance = manifest.get("provenance") or {}
    generated = {"state.json", "plan.json", "working-title.json", ".ctdb.lock"}
    search_files = set(edition_provenance._FILES.values()) & files.keys()
    if search_files:
        current = edition_provenance.for_release(path, job, state.get("disc_id"), manifest["release_id"])
        if current != provenance.get("edition_search"):
            raise ValueError("Edition search evidence differs from Archive")
        if current:
            generated.update(edition_provenance._FILES[item["method"]] for item in current)
    for name in files.keys() - required - audio.keys() - generated:
        if (name.startswith("audio/") or re.fullmatch(r"verification-report-previous-[a-f0-9]{32}\.json", name)
                or re.fullmatch(r"metadata-(?:copy|v2)-[a-f0-9]{32}/(?:audio/[^/]+\.flac|"
                                r"(?:metadata|classical-v2)-(?:manifest|preview)\.json|"
                                r"\.reviewed-front-cover\.json)", name)):
            continue
        raise ValueError("Staging contains unrecognized or unarchived evidence: " + name)
    data_files = [name for name in files if name.lower().endswith((".bin", ".bin.partial", ".iso"))]
    # A trailing data session may still need a new read, even with only a placeholder BIN.
    for name in files:
        if Path(name).name == ".reviewed-front-cover.json":
            selected = json.loads((path / name).read_text(encoding="utf-8"))
            if selected.get("sha256") != (manifest.get("artwork") or {}).get("sha256"):
                raise ValueError("Staging has selected artwork missing from Archive")
    if data_files or provenance.get("excluded_data_track") or state.get("cd_extra_data_error"):
        record = cd_extra.archived_record(destination, manifest) or {}
        captured = state.get("cd_extra_data") or {}
        if (record.get("status") != "included" or not captured.get("sha256")
                or record.get("sha256") != captured["sha256"] or data_files != [captured.get("source")]):
            raise ValueError("CD-Extra data still needs verification or preservation")
        if verify and _digest(path / data_files[0]) != captured["sha256"]:
            raise ValueError("Staged CD-Extra image changed")
    if verify:
        _verify_archive(destination, manifest)
        for name in sorted(required):
            if _digest(path / name) != archived_evidence[name]:
                raise ValueError("Staged extraction evidence differs from Archive")
        tracks = {entry["track"]: entry for entry in entries}
        for name, digest in audio.items():
            source = path / name
            number = int(source.name.split(" ", 1)[0])
            md5 = f"{FLAC(source).info.md5_signature:032x}"
            if (not int(md5, 16) or _digest(source) != digest or
                    tracks[number].get("streaminfo_audio_md5") != md5):
                raise ValueError("Staged audio differs from verified Archive")
    return destination


def _old_candidate(path, files, index, *, verify):
    manifest = collection_catalog._read_manifest(path)
    if manifest is None:
        raise ValueError("Old publication has no verified manifest")
    matches = index.get((manifest["release_id"], manifest.get("disc_number", 1)), [])
    if len(matches) != 1:
        raise ValueError("Expected one matching active archive for this release and disc")
    destination, active_manifest = matches[0]
    active = _safe_tree(destination)
    if not set(files) <= active.keys() or any(files[name][0] != active[name][0] for name in files):
        raise ValueError("Old publication contains different or unique files")
    if verify:
        _verify_archive(destination, active_manifest)
        if any(_digest(path / name) != _digest(destination / name) for name in files):
            raise ValueError("Old publication differs from Archive")
    return destination


def _candidate(kind, path, checker):
    row = {"kind": kind, "path": str(path), "bytes": 0, "reason": "", "eligible": False}
    try:
        files = _safe_tree(path)
        row["bytes"] = sum(info[0] for info in files.values())
        destination = checker(files)
        if _safe_tree(path) != files:
            raise ValueError("Files changed during cleanup evaluation")
        row["archive"] = str(destination)
        row["eligible"] = True
        row["fingerprint"] = hashlib.sha256(json.dumps(
            [kind, str(path), str(destination), files], sort_keys=True).encode()).hexdigest()
        row["reason"] = "Archive match found. File integrity is checked before deletion."
    except _ERRORS as exc:
        row["reason"] = str(exc)
    return row


def _context():
    archive = collection_catalog.archive_root()
    if archive.resolve() != archive:
        raise ValueError("Unsafe live archive root")
    stage = ripping.staging_root()
    by_job, by_disc = _archive_index(archive)
    with workflow_ledger._db() as db:
        workflows = {row["job_id"]: dict(row) for row in db.execute(
            "SELECT job_id, phase, updated_at, archive_relative_directory, archived_at FROM workflow_jobs")}
    dependencies = set()
    for path in stage.glob("oscar-*/recovery-sources.json"):
        if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > 2_000_000:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            dependencies.update(data.get(key) for key in ("original_job_id", "diagnostic_job_id"))
        except _ERRORS:
            continue
    return archive, stage, by_job, by_disc, workflows, dependencies


def scan(*, verify=False):
    from oscar import archive_revision

    archive, stage, by_job, by_disc, workflows, dependencies = _context()
    items = []
    for path in sorted(stage.iterdir()):
        if match := _JOB.fullmatch(path.name):
            job = match[1]
            row = _candidate("staging", path, lambda files: _staging_candidate(
                path, job, files, by_job.get(job, []), workflows, dependencies, verify=verify))
            items.append({**row, "job_id": job})
        elif path.name.startswith(".oscar-cleanup-"):
            row = _candidate("interrupted_cleanup", path, lambda _: archive)
            row.update(eligible=False, reason="Review this interrupted cleanup before removing remaining files")
            items.append(row)
    old = archive / "old-publications"
    if old.is_dir() and not old.is_symlink():
        for directory, dirs, names in os.walk(old, onerror=_walk_error):
            path = Path(directory)
            dirs[:] = sorted(name for name in dirs if not (path / name).is_symlink())
            if path.name.startswith(".oscar-cleanup-"):
                dirs.clear()
                row = _candidate("interrupted_cleanup", path, lambda _: archive)
                row.update(eligible=False, reason="Review this interrupted cleanup before removing remaining files")
                items.append(row)
                continue
            if path != old and ("manifest.json" in names or not dirs):
                dirs.clear()
                items.append(_candidate("old_publication", path, lambda files: _old_candidate(
                    path, files, by_disc, verify=verify)))
    for item in archive_revision.operations()["items"]:
        if item["cleanup_status"]:
            continue
        path = Path(item["backup_path"])
        try:
            path = archive_history.retained(archive, path.parent.name, path.name, recorded=path)
        except _ERRORS as exc:
            items.append({"kind": "history", "path": str(path), "bytes": 0,
                          "eligible": False, "reason": str(exc)})
            continue
        if not path.is_dir():
            continue
        row = _candidate("history", path, lambda _: Path(item["dest_path"]))
        row.update(operation_id=item["operation_id"], eligible=False,
                   reason="Use Verify & Clean to review this retained revision")
        items.append(row)
    listed = {row["path"] for row in items}
    for history in {archive / archive_history.LEGACY, archive_history.root(archive)}:
        if not history.is_dir() or history.is_symlink():
            continue
        for path in sorted(history.glob("*/*")):
            if path.is_dir() and str(path) not in listed:
                row = _candidate("history", path, lambda _: archive)
                row.update(eligible=False, reason="Retained generation requires review of its revision journal")
                items.append(row)
    jobs = workflow_ledger.list_jobs(limit=250, include_archived=True)["jobs"]
    with workflow_ledger._db() as db:
        events = [dict(row) for row in db.execute(
            "SELECT path, target_archive, bytes, status, happened_at FROM cleanup_events ORDER BY id DESC LIMIT 25")]
    return {"items": items, "jobs": jobs, "auto_days": _auto_days(),
            "events": events,
            "history_root": str(archive_history.root(archive)),
            "history_relocation_available": (archive / archive_history.LEGACY).is_dir()
            and archive_history.root(archive) != archive / archive_history.LEGACY}


@contextmanager
def _locked(archive):
    fd = os.open(archive / ".oscar-publish.lock", os.O_NOFOLLOW | os.O_CREAT | os.O_NONBLOCK | os.O_RDWR, 0o600)
    with os.fdopen(fd, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


@contextmanager
def _staging_idle(path, job):
    from oscar import classical_v2, metadata_staging, track_recovery, verification

    # CTDB can run for a published job independently of the Go! workers.
    lock = path / ".ctdb.lock"
    fd = os.open(lock, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK) if lock.exists() else None
    try:
        if fd is not None:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (ripping._LOCK, verification._LOCK, metadata_staging._LOCK,
              classical_v2._LOCK, track_recovery._RUN_LOCK, archive_publish._LOCK):
            if _live_worker(job):
                raise ValueError("Staging worker started during cleanup")
            yield
    finally:
        if fd is not None:
            os.close(fd)


def remove(items, confirmation):
    if confirmation != CONFIRM:
        raise ValueError("Confirm permanent removal of the selected copies")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise ValueError("Safe recursive removal is unavailable")
    archive = collection_catalog.archive_root()
    results = []
    with _locked(archive):
        archive, stage, by_job, by_disc, workflows, dependencies = _context()
        for item in items:
            path = Path(item["path"])
            match = _JOB.fullmatch(path.name)
            if item["kind"] == "staging" and path.parent == stage and match:
                job = match[1]
                checker = lambda files: _staging_candidate(
                    path, job, files, by_job.get(job, []), workflows, dependencies, verify=True)
            elif (item["kind"] == "old_publication" and path != archive / "old-publications"
                  and path.is_relative_to(archive / "old-publications")):
                job = None
                checker = lambda files: _old_candidate(path, files, by_disc, verify=True)
            else:
                raise ValueError("Invalid cleanup selection")
            if archive.is_relative_to(path) or path.is_relative_to(archive_history.root(archive)):
                raise ValueError("Cleanup selection overlaps archive storage")
            row = _candidate(item["kind"], path, checker)
            if not row["eligible"] or row.get("fingerprint") != item["fingerprint"]:
                results.append({"path": str(path), "status": "blocked",
                                "reason": row["reason"] if not row["eligible"] else "Selection changed since scan"})
                continue
            # Move this exact directory away from readers before recursive removal.
            tomb = path.with_name(".oscar-cleanup-" + item["fingerprint"])
            try:
                if (job and _live_worker(job)) or tomb.exists() or tomb.is_symlink():
                    raise ValueError("Active worker or interrupted cleanup")
                with workflow_ledger._db() as db:
                    event = db.execute(
                        "INSERT INTO cleanup_events(path,target_archive,bytes,status,happened_at) VALUES(?,?,?,?,?)",
                        (str(path), row["archive"], row["bytes"], "prepared", workflow_ledger._now())).lastrowid
                if job:
                    with _staging_idle(path, job):
                        archive_publish._rename_noreplace(path, tomb)
                else:
                    archive_publish._rename_noreplace(path, tomb)
                shutil.rmtree(tomb)
                with workflow_ledger._db() as db:
                    db.execute("UPDATE cleanup_events SET status='removed' WHERE id=?", (event,))
                if job and job in workflows:
                    workflow_ledger.set_archived(job, True)
                results.append({"path": str(path), "status": "removed", "bytes": row["bytes"]})
            except _ERRORS as exc:
                results.append({"path": str(path), "status": "blocked", "reason": str(exc)})
    return {"results": results}


def relocate_history(confirmation):
    from oscar import archive_revision, archive_revision_boxset_apply

    if confirmation != "MOVE_OSCAR_HISTORY":
        raise ValueError("Confirm moving retained archive history")
    archive = collection_catalog.archive_root()
    target = archive_history.root(archive)
    old = archive / archive_history.LEGACY
    if target == old:
        raise ValueError("Configure OSCAR_ARCHIVE_HISTORY_ROOT outside the live archive")
    with _locked(archive):
        for module, table in ((archive_revision, "archive_revision_operations"),
                              (archive_revision_boxset_apply, "boxset_revision_operations")):
            with module._db() as db:
                if db.execute(f"SELECT 1 FROM {table} WHERE status='prepared' LIMIT 1").fetchone():
                    raise ValueError("Reconcile the interrupted revision before moving history")
        _safe_tree(old)
        archive_history.move(archive, old, target)
    return {"history_root": str(target)}


def update_job(job_id, action):
    from oscar import go_controller

    if action in {"hide", "restore"}:
        if action == "hide" and _live_worker(job_id):
            raise ValueError("Job still has an active worker")
        return workflow_ledger.set_archived(job_id, action == "hide")
    if action != "reconcile":
        raise ValueError("Unknown cleanup job action")
    state = workflow_ledger.refresh(job_id)
    if state["phase"] == "ARCHIVE_PUBLISH_RUNNING":
        with _locked(collection_catalog.archive_root()):
            if _live_worker(job_id):
                return {"job_id": job_id, "phase": state["phase"]}
            if go_controller._read_published_archive(job_id, state):
                return go_controller.reconcile_archive(job_id)
        raise ValueError("No verified completed publication found. Inspect the job in Go! before cleanup.")
    return {"job_id": job_id, "phase": state["phase"]}


def _auto_days():
    value = os.environ.get("OSCAR_STAGING_CLEANUP_DAYS", "")
    return int(value) if len(value) <= 4 and value.isdecimal() and 1 <= int(value) <= 3650 else None


def worker(stop):
    while not stop.wait(3600):
        try:
            cutoff = datetime.now(timezone.utc).timestamp() - _auto_days() * 86400
            items = [row for row in scan()["items"] if row["kind"] == "staging" and row["eligible"]
                     and (Path(row["archive"]) / "manifest.json").stat().st_mtime < cutoff]
            if items:
                remove(items, CONFIRM)
        except _ERRORS:
            LOG.exception("Automatic OSCAR staging cleanup did not complete")
