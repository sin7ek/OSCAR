"""Explicit, single-drive cyanrip prototype; writes ONLY new staging jobs.

Never archives, deletes, overwrites, or modifies existing audio. Metadata and
audio verification have independent status. No hardware activity on import.
"""
import fcntl
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
_TRAY_BUSY = set()
_STOP_REQUESTED = set()
_PROCESSES = {}
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
        selected = plan.get("selected_tracks")
        if isinstance(selected, list) and selected:
            result["method"] = "selected_track_diagnostic"
            result["total_tracks"] = len(selected)
            result["current_track"] = selected[0]
            result["detail"] = "Diagnostic rip of selected tracks: " + ", ".join(str(n) for n in selected)
            # Do not show misleading full-CD track fraction or ETA for sparse tracks.
            return result
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
                match = re.match(r"^([0-9]{1,3}) - .+\.flac$", item.name, flags=re.I)
                if match and 1 <= int(match.group(1)) <= total:
                    files.append(int(match.group(1)))
                if len(files) > 120:
                    return result
        # File creation is not track completion. cyanrip creates the current
        # FLAC before its audio is fully written. Count only earlier tracks.
        available = set(files)
        current = 1 if 1 in available else None
        while current is not None and current + 1 in available:
            current += 1
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
        tray_busy = set(_TRAY_BUSY)
        jobs = [_snapshot(dict(job)) for job in _JOBS.values()]
    drives = []
    for stable_id, drive in configured.items():
        present = detected.get(stable_id) or {}
        relevant = sorted(
            [j for j in jobs if j["stable_id"] == stable_id],
            key=lambda j: j.get("created_at", 0), reverse=True)
        latest = relevant[0] if relevant else None
        if latest:
            latest = _with_working_title(latest)
            if latest.get("status") in {"queued", "running"}:
                latest["progress"] = _progress(latest)
        drives.append({
            "stable_id": stable_id, "label": drive.label,
            "device": present.get("device"), "present": bool(present),
            "offset_set": drive.offset_samples is not None,
            "status": "ripping" if stable_id in active else
                      "drive_control" if stable_id in tray_busy else
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


def control_tray(stable_id, action, *, opener=os.open, closer=os.close, ioctl=fcntl.ioctl):
    """Issue a Linux CD-ROM tray command only on a persistently identified idle drive.

    Never unmounts, shells out, modifies archive/staging, or permits a
    concurrent rip on this drive while the ioctl is in flight.
    """
    if action not in ("eject", "close"):
        raise RipError("Unsupported tray action")
    if not enabled():
        raise RipError("Experimental ripping disabled")
    with _LOCK:
        if stable_id in _ACTIVE or stable_id in _TRAY_BUSY:
            raise RipError("Drive busy; tray control is disabled")
        _TRAY_BUSY.add(stable_id)
    try:
        device, _offset = selected_drive(stable_id)
        fd = opener(device, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0))
        try:
            ioctl(fd, 0x5309 if action == "eject" else 0x5319)
        finally:
            closer(fd)
        return {"stable_id": stable_id, "action": action, "status": "command_sent"}
    except OSError as exc:
        raise RipError(f"Tray {action} failed or is unsupported: {exc}") from exc
    finally:
        with _LOCK:
            _TRAY_BUSY.discard(stable_id)


def stop(job_id):
    """Request cancellation of OSCAR's active cyanrip child only.

    This never removes a staging directory, partial audio, logs or a ledger
    record. The worker finishes the interrupted state before freeing the drive.
    """
    if not enabled():
        raise RipError("Experimental ripping disabled")
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise RipError("Invalid job ID")
    with _LOCK:
        job = _JOBS.get(job_id)
        if (not job or job.get("status") not in ("queued", "running")
                or job["stable_id"] not in _ACTIVE):
            raise RipError("Only an active OSCAR rip can be stopped")
        _STOP_REQUESTED.add(job_id)
        proc = _PROCESSES.get(job_id)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                pass
    return {"job_id": job_id, "status": "stop_requested",
            "note": "Partial staging retained. Wait for the worker to exit."}


def _validate_tracks(tracks, count):
    if tracks is None:
        return None
    if (not isinstance(tracks, (list, tuple)) or not tracks or len(tracks) > count
            or any(type(n) is not int or n < 1 or n > count for n in tracks)
            or len(set(tracks)) != len(tracks)):
        raise RipError("Selected tracks must be unique numbers from the inserted CD")
    return sorted(tracks)


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
                       "warning", "error", "files_sha256", "selected_tracks", "ctdb_automatic",
                       "cd_extra_data", "cd_extra_data_error")}


def _run(job, device, offset, workdir, runner, on_completed=None):
    try:
        job["status"] = "running"
        job["started_at"] = time.time()
        _atomic_json(workdir / "state.json", _snapshot(job))
        command = make_command(device, offset)
        if job.get("selected_tracks"):
            command += ["-l", ",".join(str(n) for n in job["selected_tracks"])]
        with open(workdir / "cyanrip-console.log", "xb") as log:
            if runner is subprocess.run:
                # Expose only our own child process to a deliberate Stop action.
                with _LOCK:
                    if job["id"] in _STOP_REQUESTED:
                        raise RipError("Rip stopped before extraction began")
                    proc = subprocess.Popen(command, cwd=str(workdir),
                                            stdout=log, stderr=subprocess.STDOUT)
                    _PROCESSES[job["id"]] = proc
                try:
                    returncode = proc.wait(timeout=10800)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=30)
                    raise
                finally:
                    with _LOCK:
                        _PROCESSES.pop(job["id"], None)
            else:
                # Existing offline fake runners keep the same injection contract.
                if job["id"] in _STOP_REQUESTED:
                    raise RipError("Rip stopped before extraction began")
                result = runner(command, cwd=str(workdir), stdout=log,
                                stderr=subprocess.STDOUT, timeout=10800, check=False)
                returncode = result.returncode
        job["returncode"] = returncode
        if job["id"] in _STOP_REQUESTED:
            raise RipError("Rip stopped by operator")
        if returncode:
            raise RipError(f"cyanrip exited with code {returncode}; inspect the console log")
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
        if not job.get("selected_tracks"):
            job["ctdb_automatic"] = True
            from oscar import cd_extra
            try:
                record = cd_extra.capture(workdir, device,
                                          cancelled=lambda: job["id"] in _STOP_REQUESTED)
                if record:
                    job["cd_extra_data"] = record
            except (OSError, ValueError, RuntimeError, KeyError) as exc:
                job["cd_extra_data_error"] = str(exc)[:250]
                if job["id"] in _STOP_REQUESTED:
                    raise RipError("Rip stopped by operator")
        job["status"] = "partial_diagnostic" if job.get("selected_tracks") else "needs_verification"
        job["warning"] = (
            "Selected-track diagnostic ONLY, not eligible for full-CD verification or Go publication."
            if job.get("selected_tracks") else
            "Files have SHA-256 hashes, NOT independent audio verification. "
            "After extraction OSCAR runs CTDB separately from cyanrip’s AccurateRip results.")
        if job.get("cd_extra_data_error"):
            job["warning"] += " CD-Extra data capture incomplete: " + job["cd_extra_data_error"]
    except subprocess.TimeoutExpired:
        stopped = job["id"] in _STOP_REQUESTED
        job["status"] = "interrupted" if stopped else "failed"
        job["error"] = ("Stopped by operator; partial staging retained" if stopped
                        else "Rip timed out; inspect staging files and log")
    except Exception as exc:
        stopped = job["id"] in _STOP_REQUESTED
        job["status"] = "interrupted" if stopped else "failed"
        job["error"] = ("Stopped by operator; partial staging retained" if stopped
                        else f"{type(exc).__name__}: {exc}"[:300])
    finally:
        job["finished_at"] = time.time()
        try:
            _atomic_json(workdir / "state.json", _snapshot(job))
            if job["status"] in {"needs_verification", "partial_diagnostic"}:
                from oscar import rip_working_title
                rip_working_title.display(job["id"], job.get("disc_id"), schedule=True)
            # This small metrics ledger persists independently of staging cleanup.
            # A database outage must NEVER turn a successful extraction into failure.
            try:
                from oscar.drivefit_history import record_rip
                plan_file = workdir / "plan.json"
                plan_data = json.loads(plan_file.read_text(encoding="utf-8"))
                record_rip(_snapshot(job), plan_data.get("track_count"), plan=plan_data)
            except Exception:
                # Diagnostics must never affect ripping success or preserve-state writes.
                pass
        finally:
            with _LOCK:
                _STOP_REQUESTED.discard(job["id"])
                _PROCESSES.pop(job["id"], None)
                _ACTIVE.discard(job["stable_id"])

    if job.get("ctdb_automatic"):
        from oscar import ctdb_verification
        ctdb_verification.automatic(job["id"], workdir)
    if on_completed is not None:
        try:
            on_completed(_snapshot(job))
        except Exception:
            # Callbacks must never alter the extraction verdict or staged audio.
            pass


def plan(stable_id, selected_tracks=None):
    if not enabled():
        raise RipError("Experimental ripping disabled")
    with _LOCK:
        if stable_id in _TRAY_BUSY or stable_id in _ACTIVE:
            raise RipError("Drive busy")
    device, offset = selected_drive(stable_id)
    root = staging_root()
    toc = read_toc(device)
    disc_id = toc["musicbrainz_disc_id"]
    if not _DISC.fullmatch(disc_id):
        raise RipError("Unexpected MusicBrainz Disc ID")
    selected = _validate_tracks(selected_tracks, len(toc["tracks"]))
    command = make_command(device, offset)
    if selected:
        command += ["-l", ",".join(str(n) for n in selected)]
    return {"stable_id": stable_id, "device": device, "offset_samples": offset,
            "disc_id": disc_id, "toc_string": toc.get("toc_string", ""),
            "track_count": len(toc["tracks"]), "selected_tracks": selected,
            "output_root": str(root), "command": command,
            "warning": ("Selected-track diagnostic ONLY; cannot enter Go or publish" if selected
                        else "Experimental extraction only; no verified archive or automatic cleanup")}


def start(stable_id, *, runner=subprocess.run, on_created=None, on_completed=None,
          selected_tracks=None):
    if selected_tracks is not None and (on_created is not None or on_completed is not None):
        raise RipError("Selected-track diagnostics cannot enter a Go workflow")
    information = plan(stable_id, selected_tracks=selected_tracks)
    root = staging_root()
    with _LOCK:
        if stable_id in _ACTIVE or stable_id in _TRAY_BUSY:
            raise RipError("A rip or tray action is already running on this drive")
        if len(_ACTIVE) >= max_concurrent_rips():
            raise RipError("All concurrent rip slots are in use; finish a rip before starting another")
        _ACTIVE.add(stable_id)
    try:
        job_id = uuid.uuid4().hex
        directory = root / ("oscar-" + job_id)
        directory.mkdir(mode=0o700)
        job = {"id": job_id, "stable_id": stable_id,
               "disc_id": information["disc_id"], "status": "queued",
               "selected_tracks": information["selected_tracks"],
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
        return _with_working_title(_snapshot(job))
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
    return _with_working_title(_snapshot(data))


def _with_working_title(job):
    from oscar import rip_working_title
    job["working_title"] = rip_working_title.display(
        job["id"], job.get("disc_id"), schedule=job.get("status") in {
            "needs_verification", "partial_diagnostic",
        })
    return job
