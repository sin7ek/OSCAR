"""Explicit, single-drive cyanrip prototype; writes ONLY new staging jobs.

Never archives, deletes, overwrites, or modifies existing audio. Metadata and
audio verification have independent status. No hardware activity on import.
"""
import hashlib
import hmac
import json
import os
import re
import stat
import subprocess
import threading
import time
import uuid
from pathlib import Path

from oscar.settings import discover_settings, inspect_drives
from oscar.toc import read_toc

_LOCK = threading.Lock()
_ACTIVE = set()
_JOBS = {}
_DISC = re.compile(r"^[A-Za-z0-9._-]{28}$")


class RipError(RuntimeError):
    pass


def max_concurrent_rips():
    """Operator-controlled safety cap for independent optical drives (1–16)."""
    raw = os.environ.get("OSCAR_MAX_CONCURRENT_RIPS", "3")
    if not re.fullmatch(r"[1-9][0-9]?", raw) or not 1 <= int(raw) <= 16:
        raise RipError("OSCAR_MAX_CONCURRENT_RIPS must be between 1 and 16")
    return int(raw)


def dashboard():
    """Show enabled detected optical drives and in-memory running rip jobs."""
    configured = {d.stable_id: d for d in discover_settings().drives if d.enabled}
    detected = {str(d["stable_id"]): d for d in inspect_drives()}
    with _LOCK:
        active = set(_ACTIVE)
        jobs = [_snapshot(dict(job)) for job in _JOBS.values()]
    drives = []
    for stable_id, drive in configured.items():
        present = detected.get(stable_id) or {}
        relevant = sorted(
            [j for j in jobs if j["stable_id"] == stable_id],
            key=lambda j: j.get("created_at", 0), reverse=True)
        drives.append({
            "stable_id": stable_id, "label": drive.label,
            "device": present.get("device"), "present": bool(present),
            "offset_set": drive.offset_samples is not None,
            "status": "ripping" if stable_id in active else
                      "ready" if present and drive.offset_samples is not None else "not_ready",
            "job": relevant[0] if relevant else None,
        })
    return {
        "max_concurrent_rips": max_concurrent_rips(),
        "active_count": len(active),
        "slots_available": max(0, max_concurrent_rips() - len(active)),
        "drives": drives,
        "note": "Parallel ripping is supported per distinct enabled drive. This is not a persistent queue; active jobs may be interrupted by service restarts.",
    }


def enabled():
    return os.environ.get("OSCAR_ENABLE_RIPPING") == "1"


def authorize(token):
    configured = os.environ.get("OSCAR_RIP_TOKEN", "")
    if len(configured) < 24 or not token or not hmac.compare_digest(configured, token):
        raise RipError("Rip token missing or incorrect (minimum 24 characters configured)")


def staging_root():
    root = Path(os.environ.get("OSCAR_RIP_ROOT", "/staging"))
    # Never accept user-specified paths, root/home, or the existing music share.
    if not root.is_absolute() or root == Path("/") or root == Path("/config"):
        raise RipError("Invalid staging root")
    if not root.exists() or not root.is_dir() or root.is_symlink():
        raise RipError("Staging root must be an existing real directory")
    return root.resolve(strict=True)


def selected_drive(stable_id):
    configured = {d.stable_id: d for d in discover_settings().drives if d.enabled}
    present = {str(d["stable_id"]): d for d in inspect_drives()}
    preference = configured.get(stable_id)
    drive = present.get(stable_id)
    if preference is None or drive is None or not drive.get("identity_persistent"):
        raise RipError("Drive must be enabled, detected and persistently identified")
    device = str(drive["device"])
    if not re.fullmatch(r"/dev/sr\d+", device):
        raise RipError("Invalid optical device")
    if preference.offset_samples is None:
        raise RipError("Set and save a measured drive read offset before ripping")
    if not stat.S_ISBLK(os.stat(device).st_mode):
        raise RipError("Optical device not accessible as a block device")
    return device, preference.offset_samples


def make_command(device, offset):
    """Debian cyanrip 0.9.3-compatible flags; do not use newer -B.

    AccurateRip remains enabled (no -A). The -N flag disables MusicBrainz,
    which avoids automatic AcoustID metadata submission on older builds.
    """
    return ["cyanrip", "-d", device, "-s", str(offset),
            "-o", "flac", "-D", "audio", "-F", "{track} - {title}",
            "-N", "-U", "-G", "-K", "-W"]


def _atomic_json(path, data):
    temp = path.with_name(path.name + ".tmp")
    with open(temp, "x", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)


def _snapshot(job):
    return {key: value for key, value in job.items()
            if key in ("id", "stable_id", "disc_id", "status", "created_at",
                       "started_at", "finished_at", "returncode", "flac_count",
                       "warning", "error", "files_sha256")}


def _run(job, device, offset, workdir, runner, on_completed=None):
    try:
        job["status"] = "running"
        job["started_at"] = time.time()
        _atomic_json(workdir / "state.json", _snapshot(job))
        command = make_command(device, offset)
        with open(workdir / "cyanrip-console.log", "xb") as log:
            # No shell. Hard timeout requires subprocess.run; default 3 hours.
            result = runner(command, cwd=str(workdir), stdout=log,
                            stderr=subprocess.STDOUT, timeout=10800, check=False)
        job["returncode"] = result.returncode
        if result.returncode:
            raise RipError(f"cyanrip exited with code {result.returncode}; inspect the console log")
        hashes = {}
        for file in sorted((workdir / "audio").rglob("*.flac")) if (workdir / "audio").exists() else []:
            if not file.is_file() or file.is_symlink():
                raise RipError("Unexpected audio output file")
            digest = hashlib.sha256()
            with open(file, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            hashes[str(file.relative_to(workdir))] = digest.hexdigest()
        if not hashes:
            raise RipError("No FLAC output was found; keep logs for inspection")
        job["flac_count"] = len(hashes)
        job["files_sha256"] = hashes
        job["status"] = "needs_verification"
        job["warning"] = ("Files have SHA-256 hashes, NOT independent audio verification. "
                          "Review cyanrip's log and AccurateRip results manually; CTDB not integrated.")
    except subprocess.TimeoutExpired:
        job["status"] = "failed"
        job["error"] = "Rip timed out; inspect staging files and log"
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        job["finished_at"] = time.time()
        try:
            _atomic_json(workdir / "state.json", _snapshot(job))
            # This small metrics ledger persists independently of staging cleanup.
            # A database outage must NEVER turn a successful extraction into failure.
            try:
                from oscar.drivefit_history import record_rip
                plan_file = workdir / "plan.json"
                plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
                record_rip(_snapshot(job), plan_data.get("track_count"))
            except Exception:
                # Diagnostics must never affect ripping success or preserve-state writes.
                pass
            if on_completed is not None:
                try:
                    on_completed(_snapshot(job))
                except Exception:
                    # A post-rip callback must never change a successful
                    # extraction into an apparent rip failure or alter audio.
                    pass
        finally:
            with _LOCK:
                _ACTIVE.discard(job["stable_id"])


def plan(stable_id):
    if not enabled():
        raise RipError("Experimental ripping disabled")
    device, offset = selected_drive(stable_id)
    root = staging_root()
    toc = read_toc(device)
    disc_id = toc["musicbrainz_disc_id"]
    if not _DISC.fullmatch(disc_id):
        raise RipError("Unexpected MusicBrainz Disc ID")
    return {"stable_id": stable_id, "device": device, "offset_samples": offset,
            "disc_id": disc_id, "toc_string": toc.get("toc_string", ""),
            "track_count": len(toc["tracks"]),
            "output_root": str(root), "command": make_command(device, offset),
            "warning": "Experimental extraction only; no verified archive or automatic cleanup"}


def start(stable_id, *, runner=subprocess.run, on_created=None, on_completed=None):
    information = plan(stable_id)
    root = staging_root()
    with _LOCK:
        if stable_id in _ACTIVE:
            raise RipError("A rip is already running on this drive")
        if len(_ACTIVE) >= max_concurrent_rips():
            raise RipError("All concurrent rip slots are in use; finish a rip before starting another")
        _ACTIVE.add(stable_id)
    try:
        job_id = uuid.uuid4().hex
        directory = root / ("oscar-" + job_id)
        directory.mkdir(mode=0o700)
        job = {"id": job_id, "stable_id": stable_id,
               "disc_id": information["disc_id"], "status": "queued",
               "created_at": time.time()}
        _atomic_json(directory / "plan.json", information)
        # Record durable workflow state before any extraction worker starts.
        # A callback failure prevents cyanrip from starting; staging remains
        # for examination and is never deleted automatically.
        if on_created is not None:
            on_created(_snapshot(job))
        _JOBS[job_id] = job
        worker = threading.Thread(target=_run,
                                  args=(job, information["device"],
                                        information["offset_samples"], directory, runner, on_completed),
                                  daemon=True, name="oscar-rip-" + job_id[:8])
        worker.start()
        return _snapshot(job)
    except Exception:
        with _LOCK:
            _ACTIVE.discard(stable_id)
        raise


def status(job_id):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise RipError("Invalid job ID")
    job = _JOBS.get(job_id)
    if job is not None:
        return _snapshot(job)
    root = staging_root()
    record = root / ("oscar-" + job_id) / "state.json"
    if not record.is_file() or record.is_symlink():
        raise RipError("Rip job not found")
    with open(record, encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("id") != job_id:
        raise RipError("Invalid job record")
    if data.get("status") in {"queued", "running"}:
        data["status"] = "interrupted"
        data["warning"] = "The service restarted during extraction; inspect partial files manually"
    return _snapshot(data)
