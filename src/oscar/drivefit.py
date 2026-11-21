"""DriveFit v1: read-only optical drive performance evidence.

Only OSCAR's own immutable rip-state snapshots and existing verification reports
are read. A slow rip, missing AccurateRip or failed verification does NOT prove
a defective drive; media condition, disc length, firmware and bus matter.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import statistics
import time

from oscar import ripping
from oscar.settings import discover_settings, inspect_drives

_MAX_JOBS = 1000
_MAX_JSON = 3_000_000
_MAX_AGE_DAYS = 3650


def _json_file(path: Path):
    if path.is_symlink() or not path.is_file():
        return None
    size = path.stat().st_size
    if not 2 <= size <= _MAX_JSON:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _safe_timestamp(value):
    return value if isinstance(value, (float, int)) and math.isfinite(value) and value > 0 else None


def _median(values):
    return round(statistics.median(values), 1) if values else None


def report():
    """No probes, drive opens, destructive operations, or network requests."""
    settings = discover_settings()
    configured = {item.stable_id: item for item in settings.drives}
    detected = {str(item["stable_id"]): item for item in inspect_drives()}
    records = {key: [] for key in configured}

    root = ripping.staging_root()
    scanned = 0
    for job_dir in root.iterdir():
        if scanned >= _MAX_JOBS:
            break
        if job_dir.is_symlink() or not job_dir.is_dir():
            continue
        if not job_dir.name.startswith("oscar-") or len(job_dir.name) != 38:
            continue
        job_id = job_dir.name[6:]
        if any(ch not in "0123456789abcdef" for ch in job_id):
            continue
        scanned += 1
        state = _json_file(job_dir / "state.json")
        if not state or state.get("id") != job_id:
            continue
        stable_id = state.get("stable_id")
        if not isinstance(stable_id, str) or stable_id not in records:
            continue
        started, finished = (_safe_timestamp(state.get(key)) for key in ("started_at", "finished_at"))
        duration = (round(finished - started, 1)
                    if started and finished and 0 <= finished - started <= 10800 else None)
        plan = _json_file(job_dir / "plan.json")
        if plan and plan.get("stable_id") != stable_id:
            plan = None
        track_count = plan.get("track_count") if plan else None
        if not isinstance(track_count, int) or not 1 <= track_count <= 150:
            track_count = None
        check = _json_file(job_dir / "verification-report.json")
        verification_status = (
            check.get("status") if check and check.get("job_id") == job_id
            and check.get("status") in ("checks_passed", "review_required") else "not_available"
        )
        records[stable_id].append({
            "job_id": job_id,
            "disc_id": str(state.get("disc_id") or "")[:28],
            "status": str(state.get("status") or "unknown")[:40],
            "duration_seconds": duration,
            "tracks": track_count,
            "verification_status": verification_status,
            "ripping_errors": (
                check.get("ripping_errors") if check and check.get("job_id") == job_id
                and isinstance(check.get("ripping_errors"), int)
                and 0 <= check["ripping_errors"] <= 999999 else None
            ),
            "finished_at": finished,
        })

    results = []
    for key, drive in configured.items():
        jobs = sorted(records[key], key=lambda j: j["finished_at"] or 0, reverse=True)
        completed = [j for j in jobs if j["status"] == "needs_verification"]
        durations = [j["duration_seconds"] for j in completed if j["duration_seconds"] is not None]
        decoded = sum(j["verification_status"] == "checks_passed" for j in jobs)
        reviewed = sum(j["verification_status"] == "review_required" for j in jobs)
        errors = sum(j["ripping_errors"] > 0 for j in jobs if j["ripping_errors"] is not None)
        failures = sum(j["status"] in ("failed", "interrupted") for j in jobs)
        results.append({
            "stable_id": key, "label": drive.label, "enabled": drive.enabled,
            "present": key in detected,
            "firmware": detected.get(key, {}).get("firmware"),
            "identity_persistent": bool(detected.get(key, {}).get("identity_persistent")),
            "sample_count": len(jobs),
            "extractions_completed": len(completed),
            "failed_or_interrupted_jobs": failures,
            "verified_jobs": decoded, "review_required_jobs": reviewed,
            "ripping_error_reports": errors,
            "median_duration_seconds": _median(durations),
            "recent_jobs": jobs[:15],
            "assessment": (
                "insufficient_data" if len(completed) < 5 else
                "observations_available"
            ),
            "note": (
                "Observations only; no hardware-health percentage or replacement verdict. "
                "Rip duration depends on CD length, pressing, condition and drive strategy. "
                "A verification review is not proof of drive failure."
            ),
        })
    return {
        "version": 1, "mode": "read_only_retrospective",
        "drives": results, "jobs_scanned": scanned,
        "history_scope": "Existing staging folders only; removed jobs are not counted.",
        "limitations": [
            "No direct hardware wear sensor or dependable end-of-life estimate exists here.",
            "AccurateRip misses can reflect database coverage, not bad hardware.",
            "A slow rip or review-required CD does not prove a faulty drive.",
            "For a meaningful benchmark use the same known-good pressed CD in multiple drives.",
            "No new optical-drive I/O, drive speed changes, or automatic replacement advice.",
        ],
    }
