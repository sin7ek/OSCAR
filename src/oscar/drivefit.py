"""DriveFit v1: read-only optical drive performance evidence.

Only OSCAR's own immutable rip-state snapshots and existing verification reports
are read. A slow rip, missing AccurateRip or failed verification does NOT prove
a defective drive; media condition, disc length, firmware and bus matter.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import sqlite3
import statistics

from oscar import ripping, drivefit_history
from oscar.settings import discover_settings, inspect_drives

_MAX_JOBS = 1000
_MAX_JSON = 3_000_000
_JOB_DIR = re.compile(r"oscar-([a-f0-9]{32})\Z")
_FINISHED = {"needs_verification", "partial_diagnostic", "failed", "interrupted"}


def _json_file(path: Path):
    if path.is_symlink() or not path.is_file():
        return None
    try:
        if not 2 <= path.stat().st_size <= _MAX_JSON:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _safe_timestamp(value):
    return value if isinstance(value, (float, int)) and math.isfinite(value) and value > 0 else None


def _median(values):
    return round(statistics.median(values), 1) if values else None


def _verified_replacements(job_dir, job_id, check):
    """Credit only the diagnostic source of an independently matched replacement."""
    if (not check or check.get("job_id") != job_id or check.get("status") != "checks_passed"
            or check.get("verification_method") != "independent_trackverify_R_v1_v2"):
        return []
    provenance = _json_file(job_dir / "recovery-sources.json")
    if not provenance or provenance.get("format") != "OSCAR_TRACK_RECOVERY_V1":
        return []
    diagnostic = provenance.get("diagnostic_job_id")
    if (not isinstance(diagnostic, str) or not _JOB_DIR.fullmatch("oscar-" + diagnostic)
            or diagnostic == job_id or diagnostic == provenance.get("original_job_id")):
        return []
    parent = job_dir.parent / ("oscar-" + diagnostic)
    state = None if parent.is_symlink() else _json_file(parent / "state.json")
    if not state or state.get("id") != diagnostic or state.get("status") != "partial_diagnostic":
        return []
    selected = state.get("selected_tracks")
    if not isinstance(selected, list):
        return []
    report_tracks = check.get("tracks")
    source_tracks = provenance.get("tracks")
    if not isinstance(report_tracks, list) or not isinstance(source_tracks, list):
        return []
    verified = {
        row["number"] for row in report_tracks
        if isinstance(row, dict) and type(row.get("number")) is int and row.get("checks_passed")
        and row.get("source_job_id") == diagnostic
        and isinstance(versions := row.get("accuraterip"), dict)
        and all(isinstance(versions.get(version), dict)
                and versions[version].get("status") == "accurately_ripped" for version in ("v1", "v2"))
    }
    tracks = {
        row["track"] for row in source_tracks
        if isinstance(row, dict) and type(row.get("track")) is int and row.get("source_job_id") == diagnostic
        and row["track"] in verified and row["track"] in selected
    }
    drive = state.get("stable_id")
    return [{"drive": drive, "recovery_job_id": job_id, "source_job_id": diagnostic, "track": track} for track in sorted(tracks)]


def _rip_quality(job):
    return (job["verification_status"] == "checks_passed", job["verified_tracks"], -job["ripping_errors"])


def _difficult_disc_comparisons(records):
    """Compare complete, verified attempts at the same saved Disc ID."""
    discs = {}
    for drive, jobs in records.items():
        for job in jobs:
            disc = job.get("disc_id")
            if (not disc or job["status"] != "needs_verification" or job.get("diagnostic")
                    or job["verification_status"] == "not_available" or job["ripping_errors"] is None
                    or job["verified_tracks"] is None):
                continue
            discs.setdefault((disc, job["tracks"]), {}).setdefault(drive, []).append(job)
    comparisons = {drive: [] for drive in records}
    for (disc_id, count), drives in discs.items():
        if len(drives) < 2:
            continue
        best = {drive: max(attempts, key=_rip_quality) for drive, attempts in drives.items()}
        if all(_rip_quality(job) == (True, count, 0) for job in best.values()):
            continue
        scores = [_rip_quality(job) for job in best.values()]
        for drive, job in best.items():
            comparisons[drive].append({
                "disc_id": disc_id, "tracks": count, "verified_tracks": job["verified_tracks"],
                "ripping_errors": job["ripping_errors"], "verification_status": job["verification_status"],
                "job_id": job["job_id"], "compared_drives": len(best),
                "strictly_best": _rip_quality(job) == max(scores) and scores.count(_rip_quality(job)) == 1,
            })
    return comparisons


def _badges(jobs, recovered, comparisons):
    badges = []
    checked = [job for job in jobs if job["status"] == "needs_verification"
               and job["verification_status"] in ("checks_passed", "review_required")]
    passed = sum(job["verification_status"] == "checks_passed" for job in checked)
    if len(checked) >= 5 and 10 * passed >= 9 * len(checked):
        badges.append({"name": "Accurate", "evidence": f"{passed}/{len(checked)} full rips passed saved verification"})
    wins = sum(item["strictly_best"] for item in comparisons)
    if recovered or wins:
        badges.append({"name": "Recovery", "evidence":
                       f"{len(recovered)} independently confirmed replacements · "
                       f"best verified result on {wins}/{len(comparisons)} difficult CDs compared"})
    full = [job for job in jobs if not job.get("diagnostic") and job["status"] != "interrupted"]
    if len(full) >= 10 and all(job["status"] == "needs_verification" and job["ripping_errors"] == 0 for job in full):
        badges.append({"name": "Reliable", "evidence": f"{len(full)} full attempts with no extraction errors reported"})
    return badges


def _leaderboard(drives, value, sample_count, badge, unit, *, highest):
    ranked = sorted(
        (drive for drive in drives if drive[value] is not None),
        key=lambda drive: drive[value], reverse=highest,
    )
    eligible = [drive for drive in ranked if drive[sample_count] >= 5]
    leaders = [
        drive for drive in eligible if drive[value] == eligible[0][value]
    ] if len(eligible) >= 2 else []
    for drive in leaders:
        tied = " (tied)" if len(leaders) > 1 else ""
        drive["badges"].append({"name": badge, "evidence":
                               f"{drive[value]:g}{unit} across {drive[sample_count]} full rips{tied}"})
    leader_ids = {drive["stable_id"] for drive in leaders}
    return [
        {"label": drive["label"], "value": drive[value], "samples": drive[sample_count],
         "leader": drive["stable_id"] in leader_ids}
        for drive in ranked
    ]


def report():
    """No probes, drive opens, destructive operations, or network requests."""
    settings = discover_settings()
    configured = {item.stable_id: item for item in settings.drives}
    detected = {str(item["stable_id"]): item for item in inspect_drives()}
    records = {key: [] for key in configured}

    root = ripping.staging_root()
    scanned = 0
    recovered = []
    for job_dir in root.iterdir():
        if scanned >= _MAX_JOBS:
            break
        if job_dir.is_symlink() or not job_dir.is_dir():
            continue
        match = _JOB_DIR.fullmatch(job_dir.name)
        if not match:
            continue
        job_id = match[1]
        scanned += 1
        state = _json_file(job_dir / "state.json")
        if not state or state.get("id") != job_id:
            continue
        stable_id = state.get("stable_id")
        if stable_id == "recovery":
            recovered.extend(_verified_replacements(job_dir, job_id, _json_file(job_dir / "verification-report.json")))
            continue
        if not isinstance(stable_id, str) or stable_id not in records or state.get("status") not in _FINISHED:
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
        report_tracks = check.get("tracks") if verification_status != "not_available" else None
        verified_tracks = None
        if (isinstance(report_tracks, list) and track_count and len(report_tracks) == track_count
                and all(isinstance(track, dict) and type(track.get("number")) is int for track in report_tracks)
                and {track["number"] for track in report_tracks} == set(range(1, track_count + 1))):
            verified_tracks = sum(track.get("checks_passed") is True for track in report_tracks)
        records[stable_id].append({
            "job_id": job_id,
            "disc_id": str(state.get("disc_id") or "")[:28],
            "status": str(state.get("status") or "unknown")[:40],
            "duration_seconds": duration,
            "audio_seconds": drivefit_history.audio_seconds(plan or {}),
            "diagnostic": bool(state.get("selected_tracks") or (plan or {}).get("selected_tracks")
                               or state.get("status") == "partial_diagnostic"),
            "tracks": track_count,
            "verification_status": verification_status,
            "verified_tracks": verified_tracks,
            "ripping_errors": (
                check.get("ripping_errors") if check and check.get("job_id") == job_id
                and isinstance(check.get("ripping_errors"), int)
                and 0 <= check["ripping_errors"] <= 999999 else None
            ),
            "finished_at": finished,
        })

    comparisons = _difficult_disc_comparisons(records)

    # Historical measurements survive staging cleanup. Deduplicate by job ID.
    # A surviving staging report takes precedence over persisted summary data.
    history_available = True
    try:
        persisted = drivefit_history.read_history(set(configured))
    except (OSError, ValueError, sqlite3.Error):
        persisted = []
        history_available = False
    for item in persisted:
        key = item["stable_id"]
        if not any(entry["job_id"] == item["job_id"] for entry in records[key]):
            records[key].append(item)
    results = []
    for key, drive in configured.items():
        jobs = sorted(records[key], key=lambda j: j["finished_at"] or 0, reverse=True)
        completed = [j for j in jobs if j["status"] == "needs_verification"]
        durations = [j["duration_seconds"] for j in completed if j["duration_seconds"] is not None]
        speeds = [
            job["audio_seconds"] / job["duration_seconds"] for job in completed
            if job["verification_status"] == "checks_passed" and job["audio_seconds"]
            and job["duration_seconds"] and not job.get("diagnostic")
        ]
        contributions = list({
            (row["source_job_id"], row["track"]): row for row in recovered if row["drive"] == key
        }.values())
        decoded = sum(j["verification_status"] == "checks_passed" for j in jobs)
        reviewed = sum(j["verification_status"] == "review_required" for j in jobs)
        observed_errors = [j["ripping_errors"] for j in completed if j["ripping_errors"] is not None]
        errors = sum((j["ripping_errors"] or 0) > 0 for j in jobs)
        failures = sum(j["status"] == "failed" for j in jobs)
        interruptions = sum(j["status"] == "interrupted" for j in jobs)
        full_checked = [job for job in completed if job["verification_status"] in ("checks_passed", "review_required")]
        checked_rips = len(full_checked)
        full_passed = sum(job["verification_status"] == "checks_passed" for job in full_checked)
        results.append({
            "stable_id": key, "label": drive.label, "enabled": drive.enabled,
            "present": key in detected,
            "firmware": detected.get(key, {}).get("firmware"),
            "identity_persistent": bool(detected.get(key, {}).get("identity_persistent")),
            "sample_count": len(jobs),
            "extractions_completed": len(completed),
            "failed_or_interrupted_jobs": failures + interruptions,
            "failed_jobs": failures,
            "interrupted_jobs": interruptions,
            "verified_jobs": decoded, "review_required_jobs": reviewed,
            "ripping_error_reports": errors,
            "known_error_rips": len(observed_errors),
            "mean_errors_per_rip": round(statistics.mean(observed_errors), 3) if observed_errors else None,
            "checked_rips": checked_rips,
            "verification_pass_pct": round(100 * full_passed / checked_rips, 1) if checked_rips else None,
            "median_duration_seconds": _median(durations),
            "median_speed": _median(speeds),
            "timed_verified_rips": len(speeds),
            "diagnostic_jobs": sum(bool(job.get("diagnostic")) for job in jobs),
            "recovery_tracks": contributions,
            "difficult_disc_comparisons": comparisons[key],
            "badges": _badges(jobs, contributions, comparisons[key]),
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
        "version": 2, "mode": "read_only_retrospective",
        "drives": results, "jobs_scanned": scanned,
        "leaderboards": {
            "speed": _leaderboard(results, "median_speed", "timed_verified_rips", "Fast", "×", highest=True),
            "errors": _leaderboard(results, "mean_errors_per_rip", "known_error_rips", "Low errors",
                                  " errors/rip", highest=False),
            "accuracy": sorted((
                {"label": drive["label"], "value": drive["verification_pass_pct"], "samples": drive["checked_rips"]}
                for drive in results if drive["verification_pass_pct"] is not None
            ), key=lambda drive: drive["value"], reverse=True),
        },
        "history_scope": ("Existing staging and saved DriveFit history. Older attempts and recovery contributions require their staging records."
                          if history_available else "Saved DriveFit history unavailable. Showing existing staging only."),
        "limitations": [
            "No direct hardware wear sensor or dependable end-of-life estimate exists here.",
            "AccurateRip misses can reflect database coverage, not bad hardware.",
            "A slow rip or review-required CD does not prove a faulty drive.",
            "For a meaningful benchmark use the same known-good pressed CD in multiple drives.",
            "No new optical-drive I/O, drive speed changes, or automatic replacement advice.",
        ],
    }
