"""Operator-controlled metadata refresh for an existing verified Go! CD.

Never modify the original rip, historical tagged copy, workflow ledger, or
published archive. The new copy is *staging only* and has no publish action.
"""
import json
from pathlib import Path

from oscar import metadata_staging, workflow_ledger


class ReprocessError(ValueError):
    pass


def _accepted_workflow(job_id):
    workflow = workflow_ledger.refresh(job_id)
    if (workflow.get("identification_mode") != "semi_automatic"
            or workflow.get("release_match_status") != "INFERRED_OPERATOR_ACCEPTED"
            or not workflow.get("accepted_release_id")
            or not workflow.get("metadata_copy_id")
            or workflow.get("metadata_release_id") != workflow.get("accepted_release_id")
            or workflow.get("phase") not in {
                "METADATA_READY", "ARCHIVE_PUBLISHED", "ARCHIVE_REVIEW_REQUIRED",
            }):
        raise ReprocessError("An existing accepted, verified Semi Automatic tagged copy is required")
    return workflow


def _old_copy_preview(job_id, workflow):
    from oscar import verification
    folder = verification._safe_job(job_id) / ("metadata-copy-" + workflow["metadata_copy_id"])
    if folder.is_symlink() or not folder.is_dir():
        raise ReprocessError("Original tagged staging copy is unavailable or unsafe")
    saved = folder / "metadata-preview.json"
    manifest = folder / "metadata-manifest.json"
    for file in (saved, manifest):
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 3_000_000:
            raise ReprocessError("Original metadata evidence is unavailable or unsafe")
    old = json.loads(saved.read_text(encoding="utf-8"))
    original_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    if (old.get("job_id") != job_id
            or old.get("release_id") != workflow["accepted_release_id"]
            or old.get("fingerprint") != original_manifest.get("preview_fingerprint")
            or original_manifest.get("status") != "tagged_copy_ready_for_review"
            or original_manifest.get("job_id") != job_id
            or original_manifest.get("copy_id") != workflow["metadata_copy_id"]):
        raise ReprocessError("Saved tagged-copy evidence differs from accepted job")
    old_tracks = old.get("tracks")
    if not isinstance(old_tracks, list) or not old_tracks or len(old_tracks) > 150:
        raise ReprocessError("Original metadata preview has invalid tracks")
    inspected = metadata_staging.inspect_copy(job_id, workflow["metadata_copy_id"])
    if inspected.get("status") != "tags_match_preview":
        raise ReprocessError("Original tagged copy does not pass read-back integrity checks")
    return old


def _changes(previous, current):
    changes = []
    for field in ("title", "artist", "date", "barcode", "catalog_numbers", "labels"):
        old = (previous.get("album") or {}).get(field)
        new = (current.get("album") or {}).get(field)
        if old != new:
            changes.append({"scope": "album", "field": field, "before": old, "after": new})
    old_tracks = previous.get("tracks") or []
    new_tracks = current.get("tracks") or []
    if len(old_tracks) != len(new_tracks):
        raise ReprocessError("Track count changed; manual release review required")
    for older, newer in zip(old_tracks, new_tracks):
        if (older.get("number") != newer.get("number")
                or older.get("original_file") != newer.get("original_file")):
            raise ReprocessError("Physical track ordering or source files changed")
        old_tags, new_tags = older.get("tags") or {}, newer.get("tags") or {}
        for key in sorted(set(old_tags) | set(new_tags)):
            if old_tags.get(key) != new_tags.get(key):
                changes.append({
                    "scope": "track", "track": newer["number"], "field": key,
                    "before": old_tags.get(key), "after": new_tags.get(key),
                })
    return changes


def refresh_preview(job_id, *, lookup=None):
    """Read back the old copy and fetch current MusicBrainz metadata, no writes."""
    workflow = _accepted_workflow(job_id)
    old = _old_copy_preview(job_id, workflow)
    opts = {"operator_accepted": True}
    if lookup is not None:
        opts["lookup"] = lookup
    fresh = metadata_staging.preview(job_id, workflow["accepted_release_id"], **opts)
    if fresh.get("job_id") != job_id or fresh.get("release_id") != workflow["accepted_release_id"]:
        raise ReprocessError("MusicBrainz preview release differs from accepted workflow")
    changes = _changes(old, fresh)
    return {
        "job_id": job_id,
        "release_id": workflow["accepted_release_id"],
        "previous_copy_id": workflow["metadata_copy_id"],
        "historical_status": workflow["release_match_status"],
        "old_catalog_numbers": (old.get("album") or {}).get("catalog_numbers") or [],
        "new_catalog_numbers": (fresh.get("album") or {}).get("catalog_numbers") or [],
        "track_count": len(fresh.get("tracks") or []),
        "fingerprint": fresh["fingerprint"],
        "changes": changes,
        "change_count": len(changes),
        "new_copy_allowed": bool(changes),
        "status": "changes_found" if changes else "unchanged",
        "warning": ("Read-only comparison. A new staging copy requires explicit approval "
                    "and never replaces the published archive or the durable Go history. "
                    "MusicBrainz does not prove the physical pressing; verify the CD."),
    }


def create_new_staging_copy(job_id, fingerprint, confirmation):
    if confirmation != "REPROCESS_TO_NEW_STAGING_COPY":
        raise ReprocessError("Explicit reprocessing confirmation required")
    current = refresh_preview(job_id)
    if not current["new_copy_allowed"]:
        raise ReprocessError("No new MusicBrainz metadata changes to stage")
    if current["fingerprint"] != fingerprint:
        raise ReprocessError("MusicBrainz changed since preview; compare again")
    started = metadata_staging.start_copy(
        job_id, current["release_id"], fingerprint, "COPY_TAGGED_TO_STAGING",
        identification_status="INFERRED_OPERATOR_ACCEPTED")
    return {
        **started, "previous_copy_id": current["previous_copy_id"],
        "release_id": current["release_id"],
        "note": ("Independent tagged staging copy only; original rip, old copy, "
                 "archive, Collection catalog and workflow remain unchanged. "
                 "Inspect this copy; no archive replacement is implemented."),
    }
