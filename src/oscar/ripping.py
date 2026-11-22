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



def _progress(job, *, now=None):
    """Read-only, conservative track-completion progress from rip staging.

    cyanrip v0.9.3 outputs do not provide a guaranteed structured progress
    stream. A file actively being written is NOT a completed track. At most
    N-1 track files are counted while cyanrip is still running. A 3+ minute
    ETA is only a rough estimate from completed tracks, never a promise.
    """
    if job.get("status") not in {"queued", "running"}:
        return None
    now = time.time() if now is None else now
    job_id = job.get("id", "")
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        return None
    result = {
        "method": "completed_track_files_estimate",
        "percent": None, "total_tracks": None, "completed_tracks": 0,
        "current_track": None, "elapsed_seconds": None,
        "eta_seconds": None, "eta_kind": "unavailable",
        "detail": "Waiting for completed tracks; an active FLAC is not counted.",
    }
    started = job.get("started_at")
    if isinstance(started, (float, int)) and now >= started:
        result["elapsed_seconds"] = int(now - started)
    # Never inspect arbitrary caller paths; use the bounded job ID under
    # OSCAR's own fixed staging root. Bad or missing files are non-fatal.
    try:
        folder = staging_root() / ("oscar-" + job_id)
        if folder.is_symlink() or not folder.is_dir():
            return result
        plan_file = folder / "plan.json"
        if plan_file.is_symlink() or not plan_file.is_file() or plan_file.stat().st_size > 100_000:
            return result
        plan = json.loads(plan_file.read_text(encoding="utf-8"))
        total = plan.get("track_count")
        if type(total) is not int or not 1 <= total <= 99:
            return result
        result["total_tracks"] = total
        audio = folder / "audio"
        files = []
        if audio.is_dir() and not audio.is_symlink():
            for item in audio.iterdir():
                if item.is_symlink() or not item.is_file() or not item.name.lower().endswith(".flac"):
                    continue
                match = re.match(r"^([0-9]{1,3}) - .+\\.flac$", item.name, flags=re.I)
                if match and 1 <= int(match.group(1)) <= total:
                    files.append(int(match.group(1)))
                if len(files) > 120:
                    return result
        # File creation is not track completion. cyanrip creates the current
        # FLAC before its audio is fully written. Count only earlier tracks.
        current = max(files) if files else None
        completed = max(0, current - 1) if current else 0
        result["completed_tracks"] = completed
        result["current_track"] = current or 1
        # This is deliberately a *track-based* metric, NOT sector progress.
        # Hold below 100% until the extraction worker has exited successfully.
        result["percent"] = min(99, round(completed * 100 / total, 1))
        result["detail"] = (
            f"{completed}/{total} tracks finished (estimated from next output file)"
            if current else f"0/{total} tracks finished; reading or preparing CD"
        )
        elapsed = result["elapsed_seconds"]
        if elapsed is not None and completed >= 2:
            seconds_per_track = elapsed / completed
            projected = round(seconds_per_track * (total - completed))
            if 0 < projected < 86400:
                result["eta_seconds"] = projected
                result["eta_kind"] = "rough_track_average"
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return result


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
        latest = relevant[0] if relevant else None
        if latest and latest.get("status") in {"queued", "running"}:
            latest["progress"] = _progress(latest)
        drives.append({
            "stable_id": stable_id, "label": drive.label,
            "device": present.get("device"), "present": bool(present),
            "offset_set": drive.offset_samples is not None,
            "status": "ripping" if stable_id in active else
                      "ready" if present and drive.offset_samples is not None else "not_ready",
            "job": latest,
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
