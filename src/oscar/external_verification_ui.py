"""Read-only library browsing and one background external verification at a time."""
import logging
import os
import threading
import uuid
from pathlib import Path

from mutagen import MutagenError

from oscar import external_verification

_LOG = logging.getLogger(__name__)
_LOCK = threading.Lock()
_JOB = {}


def _folder(relative):
    raw_root = os.getenv("OSCAR_EXTERNAL_LIBRARY_ROOT", "").strip()
    if not raw_root:
        raise ValueError("Set OSCAR_EXTERNAL_LIBRARY_ROOT to a read-only music library mount")
    root = Path(raw_root)
    if not root.is_absolute() or root == Path("/") or root.resolve() != root or not root.is_dir():
        raise ValueError("The configured external library root is unavailable or unsafe")
    folder = root
    if relative:
        for part in relative.split("/"):
            if not part or part.startswith(".") or "\0" in part:
                raise ValueError("Choose a visible folder inside the external library")
            folder = folder / part
            if folder.is_symlink() or not folder.is_dir():
                raise ValueError("The selected library folder is unavailable or unsafe")
    return folder


def folders(relative):
    folder = _folder(relative)
    children = sorted(
        (entry.name for entry in folder.iterdir()
         if not entry.name.startswith(".") and not entry.is_symlink() and entry.is_dir()),
        key=lambda name: (name.casefold(), name),
    )
    return {"folder": relative, "folders": children}


def _summary(report):
    discs = []
    for disc in report["discs"]:
        files = disc["file_integrity"]
        discs.append({
            "disc": disc["disc"],
            "passed": sum(result == "passed" for result in files.values()),
            "tracks": len(files),
            "integrity": disc["integrity"],
            "issues": {name: result for name, result in files.items() if result != "passed"},
            "ctdb": disc["ctdb"],
            "track_total_declared": disc["track_total_declared"],
        })
    return {
        "status": report["status"],
        "source_type": report["source_type"],
        "discs": discs,
        "disc_total_declared": report["disc_total_declared"],
        "assumed_single_disc": report["assumed_single_disc"],
    }


def _run(relative):
    try:
        result = _summary(external_verification.verify(_folder(relative)))
        outcome = {"status": "completed", "result": result}
    except (ValueError, OSError, MutagenError) as error:
        outcome = {"status": "failed", "error": str(error)[:400]}
    except Exception:
        _LOG.exception("External verification worker failed")
        outcome = {"status": "failed", "error": "External verification failed. See the OSCAR log."}
    with _LOCK:
        _JOB.update(outcome)


def start(relative):
    if not relative:
        raise ValueError("Open an album folder before starting verification")
    _folder(relative)
    with _LOCK:
        if _JOB.get("status") == "running":
            raise ValueError("An external album verification is already running")
        job = {"id": uuid.uuid4().hex, "folder": relative, "status": "running"}
        _JOB.clear()
        _JOB.update(job)
        try:
            threading.Thread(target=_run, args=(relative,), name="oscar-external-verification",
                             daemon=True).start()
        except RuntimeError:
            _JOB.clear()
            raise ValueError("Could not start external verification") from None
        return job


def status():
    with _LOCK:
        return dict(_JOB)
