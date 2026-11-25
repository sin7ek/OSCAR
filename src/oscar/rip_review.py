"""Read-only routing for tracked rips, based on saved extraction evidence."""

import json

from oscar import ripping, verification


def _saved(directory, name, job_id):
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) and value.get("job_id") == job_id else {}


def next_step(job_id, phase, *, has_candidate=False):
    if phase == "ARCHIVE_PUBLISHED":
        return {"group": "done", "action": "published", "reason": "Archive published"}
    if phase in {"METADATA_COPY_RUNNING", "ARCHIVE_PUBLISH_RUNNING"}:
        return {"group": "active", "action": "progress", "reason": "Processing in Go!"}

    state = {}
    report = {}
    ctdb = {}
    try:
        from oscar.workflow_ledger import _state

        directory = verification._safe_job(job_id)
        state = _state(job_id)
        if state.get("status") == "needs_verification":
            report = _saved(directory, "verification-report.json", job_id)
            ctdb = _saved(directory, "ctdb-report.json", job_id)
            if ctdb.get("files_sha256") != state.get("files_sha256"):
                ctdb = {}
    except (OSError, ValueError, KeyError, RuntimeError):
        pass

    result = {"source_drive": state.get("stable_id"), "disc_id": state.get("disc_id"),
              "verification": report.get("status"), "ctdb": ctdb.get("status")}
    data = state.get("cd_extra_data")
    if state.get("cd_extra_data_error"):
        result["layout"] = "CD-Extra data capture failed"
    elif isinstance(data, dict) and data.get("verification") == "two_matching_raw_reads":
        result["layout"] = "CD-Extra data captured and verified at extraction"
    elif str(ctdb.get("cue_layout", "")).startswith("cd_extra_"):
        result["layout"] = "CD-Extra audio checked; verified data capture unavailable"

    def route(group, action, reason):
        return {**result, "group": group, "action": action, "reason": reason}

    status = state.get("status")
    if (phase in {"RIP_FAILED", "RIP_INTERRUPTED"} or status in {"failed", "interrupted"}
            or (phase == "RIP_IN_PROGRESS" and status in {"queued", "running"}
                and job_id not in ripping._JOBS)):
        return route("reread", "retry", state.get("error") or
                     "Extraction stopped. Inspect the saved attempt and use another drive if available.")
    if phase in {"RIP_IN_PROGRESS", "VERIFICATION_PENDING"}:
        if job_id in verification._RUNNING:
            return route("active", "progress", "Verifying staged audio")
        if phase == "RIP_IN_PROGRESS" and status != "needs_verification":
            return route("active", "progress", "Extraction in progress or awaiting status")
        if not report:
            return route("active", "verify", "Awaiting an audio verification result")

    if report.get("status") == "review_required":
        tracks = [track for track in (report.get("tracks") or []) if isinstance(track, dict)]
        affected = sorted({
            track["number"] for track in tracks
            if type(track.get("number")) is int and 1 <= track["number"] <= 99
            and (not track.get("sha256_matches") or not track.get("flac_decodes")
                 or (track.get("accuraterip_assessment") or {}).get("status") == "review_required")
        })
        if affected:
            if len(affected) < (report.get("expected_tracks") or len(tracks)):
                result["tracks"] = affected
            return route("reread", "retry", "Read, integrity or AccurateRip issue on the listed tracks")
        if ctdb.get("status") == "no_audio_match":
            return route("reread", "retry", "CTDB reference found; the staged audio did not match")
        if (tracks and report.get("ripping_errors") == 0
                and len(tracks) == report.get("expected_tracks") == report.get("flac_count")
                and (report.get("cue") or {}).get("references_match")):
            return route("audio_review", "verify", "Local checks passed; AccurateRip confirmation is incomplete")
        return route("audio_review", "verify", "Inspect the saved audio verification report")

    if ctdb.get("status") == "no_audio_match":
        return route("reread", "retry", "CTDB reference found; the staged audio did not match")
    if result.get("layout") in {"CD-Extra data capture failed",
                               "CD-Extra audio checked; verified data capture unavailable"}:
        return route("audio_review", "layout", "Inspect audio and data capture before publishing")
    if phase in {"RELEASE_REVIEW_PENDING", "DEFERRED_REVIEW"} or (
            report.get("status") == "checks_passed" and phase in {"RIP_IN_PROGRESS", "VERIFICATION_PENDING"}):
        reason = "Compare the physical edition" if has_candidate else "Find the physical edition"
        return route("edition", "edition", reason)
    if phase in {"METADATA_READY", "ARCHIVE_REVIEW_REQUIRED"}:
        return route("ready", "archive", "Archive review is available")
    if phase == "RELEASE_ACCEPTED":
        return route("edition", "metadata", "Continue with accepted release metadata")
    if phase == "METADATA_REVIEW_REQUIRED":
        return route("edition", "metadata", "Inspect the metadata handoff")
    return route("audio_review", "verify", "Inspect the saved rip")
