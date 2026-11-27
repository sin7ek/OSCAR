"""Read-only library browsing and one background external verification at a time."""
import json
import logging
import sqlite3
from contextlib import closing
import os
import threading
import uuid
from pathlib import Path

from mutagen import MutagenError

from oscar import collection_catalog, external_verification

_LOG = logging.getLogger(__name__)
_LOCK = threading.Lock()
_JOB = {}
_REPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS external_verification_reports (
    root TEXT NOT NULL,
    folder TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    report_json TEXT NOT NULL,
    PRIMARY KEY (root, folder)
)
"""


def _library_root():
    raw_root = os.getenv("OSCAR_EXTERNAL_LIBRARY_ROOT", "").strip()
    if not raw_root:
        raise ValueError("Set OSCAR_EXTERNAL_LIBRARY_ROOT to a read-only music library mount")
    root = Path(raw_root)
    if not root.is_absolute() or root == Path("/") or root.resolve() != root or not root.is_dir():
        raise ValueError("The configured external library root is unavailable or unsafe")
    return root


def _folder(relative, root=None):
    folder = root if root is not None else _library_root()
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


def _connect():
    path = collection_catalog.database_path()
    if path.parent.is_symlink() or not path.parent.is_dir():
        raise collection_catalog.CatalogError("Persistent database directory must exist and not be a symlink")
    return sqlite3.connect(path, timeout=10)


def _read_report(db, root, relative):
    row = db.execute(
        "SELECT report_json FROM external_verification_reports WHERE root=? AND folder=?",
        (str(root), relative),
    ).fetchone()
    return json.loads(row[0]) if row else None


def _saved_report(root, relative):
    if not collection_catalog.database_path().is_file():
        return None
    with closing(_connect()) as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='external_verification_reports'"
        ).fetchone()
        return _read_report(db, root, relative) if exists else None


def _hashes(report):
    return {path: sha for disc in report["discs"] for path, sha in disc["files_sha256"].items()}


def _saved_summary(relative, report):
    return {
        "folder": relative,
        "status": "completed",
        "saved": True,
        "checked_at": report["checked_at"],
        "result": _summary(report),
    }


def saved(relative):
    if not relative:
        raise ValueError("Open an album folder before viewing saved verification")
    root = _library_root()
    _folder(relative, root)
    report = _saved_report(root, relative)
    return _saved_summary(relative, report) if report else {}


def saved_albums():
    if not os.getenv("OSCAR_EXTERNAL_LIBRARY_ROOT", "").strip():
        return []
    root = _library_root()
    if not collection_catalog.database_path().is_file():
        return []
    with closing(_connect()) as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='external_verification_reports'"
        ).fetchone()
        if not exists:
            return []
        records = db.execute(
            """SELECT folder, checked_at, json_extract(report_json, '$.status')
               FROM external_verification_reports WHERE root=?
               ORDER BY checked_at DESC, folder""",
            (str(root),),
        )
        return [{"folder": folder, "checked_at": checked_at, "result": result}
                for folder, checked_at, result in records]


def save(job_id):
    root = _library_root()
    with _LOCK:
        if (_JOB.get("id") != job_id or _JOB.get("status") != "completed"
                or _JOB.get("_root") != root):
            raise ValueError("This verification is no longer available to save. Rerun the check.")
        relative, report = _JOB["folder"], _JOB["_report"]
    _folder(relative, root)
    with closing(_connect()) as db, db:
        db.execute(_REPORT_SCHEMA)
        db.execute(
            """
            INSERT INTO external_verification_reports(root, folder, checked_at, report_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(root, folder) DO UPDATE SET
                checked_at=excluded.checked_at, report_json=excluded.report_json
            WHERE excluded.checked_at >= external_verification_reports.checked_at
            """,
            (str(root), relative, report["checked_at"], json.dumps(report)),
        )
        return _saved_summary(relative, _read_report(db, root, relative))


def _run(root, relative):
    try:
        report = external_verification.verify(_folder(relative, root))
        outcome = {
            "status": "completed", "result": _summary(report), "_report": report,
            "checked_at": report["checked_at"],
        }
        try:
            previous = _saved_report(root, relative)
        except (sqlite3.Error, collection_catalog.CatalogError, OSError, ValueError):
            _LOG.warning("Could not read the saved external verification", exc_info=True)
        else:
            if previous:
                outcome["saved_hashes_changed"] = _hashes(previous) != _hashes(report)
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
    root = _library_root()
    _folder(relative, root)
    with _LOCK:
        if _JOB.get("status") == "running":
            raise ValueError("An external album verification is already running")
        job = {"id": uuid.uuid4().hex, "folder": relative, "status": "running"}
        _JOB.clear()
        _JOB.update(job, _root=root)
        try:
            threading.Thread(target=_run, args=(root, relative), name="oscar-external-verification",
                             daemon=True).start()
        except RuntimeError:
            _JOB.clear()
            raise ValueError("Could not start external verification") from None
        return job


def status():
    with _LOCK:
        return {key: value for key, value in _JOB.items() if not key.startswith("_")}
