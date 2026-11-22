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


def adopt_new_staging_copy_for_go(job_id, copy_id, fingerprint, confirmation):
    """Review and bind a completed refreshed copy to an unpublished Go job.

    No new tagged copies, rip/FLAC mutations, archive writes, automatic
    publication, or change to the originally accepted MusicBrainz release.
    """
    import re
    from oscar import verification
    if confirmation != "USE_REVIEWED_COPY_FOR_FIRST_PUBLICATION":
        raise ReprocessError("Explicit refreshed-copy approval is required")
    if not isinstance(copy_id, str) or not re.fullmatch(r"[a-f0-9]{32}", copy_id):
        raise ReprocessError("Invalid refreshed copy ID")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise ReprocessError("Invalid reviewed copy fingerprint")
    workflow = _accepted_workflow(job_id)
    if workflow["phase"] != "METADATA_READY" or workflow.get("archive_publish_id"):
        raise ReprocessError("Only unpublished METADATA_READY jobs may select a new copy")
    previous = workflow["metadata_copy_id"]
    if previous == copy_id:
        raise ReprocessError("The refreshed copy is already the active Go copy")
    old = _old_copy_preview(job_id, workflow)
    root = verification._safe_job(job_id)
    folder = root / ("metadata-copy-" + copy_id)
    if folder.is_symlink() or not folder.is_dir():
        raise ReprocessError("Refreshed copy is unavailable or unsafe")
    paths = [folder / "metadata-manifest.json", folder / "metadata-preview.json"]
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
            raise ReprocessError("Refreshed copy evidence is missing or unsafe")
    manifest, proposal = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if (manifest.get("status") != "tagged_copy_ready_for_review"
            or manifest.get("job_id") != job_id
            or manifest.get("copy_id") != copy_id
            or manifest.get("release_id") != workflow["accepted_release_id"]
            or manifest.get("preview_fingerprint") != fingerprint
            or manifest.get("identification_status") != "INFERRED_OPERATOR_ACCEPTED"
            or proposal.get("job_id") != job_id
            or proposal.get("release_id") != workflow["accepted_release_id"]
            or proposal.get("fingerprint") != fingerprint):
        raise ReprocessError("Refreshed copy differs from the approved release or reviewed fingerprint")
    old_tracks = old.get("tracks") or []
    new_tracks = proposal.get("tracks") or []
    if (len(old_tracks) != len(new_tracks) or not new_tracks
            or [(x.get("number"), x.get("original_file"))
                for x in old_tracks] !=
               [(x.get("number"), x.get("original_file"))
                for x in new_tracks]):
        raise ReprocessError("Refreshed copy has changed rip track order/source paths")
    old_album, new_album = old.get("album") or {}, proposal.get("album") or {}
    for key in ("musicbrainz_release_id", "musicbrainz_disc_id"):
        if old_album.get(key) != new_album.get(key):
            raise ReprocessError("Refreshed physical release/Disc ID changed")
    for before, after in zip(old_tracks, new_tracks):
        for key in ("MUSICBRAINZ_ALBUMID", "MUSICBRAINZ_DISCID",
                    "DISCNUMBER", "DISCTOTAL", "TRACKNUMBER", "TRACKTOTAL"):
            if (before.get("tags") or {}).get(key) != (after.get("tags") or {}).get(key):
                raise ReprocessError("Refreshed copy differs in physical disc/track identity")
    inspected = metadata_staging.inspect_copy(job_id, copy_id)
    if (inspected.get("status") != "tags_match_preview"
            or inspected.get("release_id") != workflow["accepted_release_id"]
            or inspected.get("track_count") != len(new_tracks)
            or any(not t.get("sha256_matches") or not t.get("audio_streaminfo_md5_matches")
                   or not t.get("tags_match") for t in inspected.get("tracks", []))):
        raise ReprocessError("Refreshed staging FLAC tags, hashes or audio MD5 failed inspection")
    # Protect against a stale-source race: the original rip and all its file
    # hashes are re-verified by the same source validation used for staging.
    _, source_state, _ = metadata_staging._source(job_id)
    originals = source_state.get("files_sha256") or {}
    entries = manifest.get("files") or {}
    if (set(entries) != {x["original_file"] for x in new_tracks}
            or any(entries[x["original_file"]].get("source_sha256")
                   != originals.get(x["original_file"]) for x in new_tracks)):
        raise ReprocessError("Refreshed copy no longer matches verified original rip hashes")
    revised = workflow_ledger.adopt_refreshed_metadata_copy(
        job_id, previous, copy_id, workflow["accepted_release_id"],
        fingerprint, confirmation)
    return {
        "status": "refreshed_copy_selected_for_first_publication",
        "job_id": job_id, "previous_copy_id": previous,
        "active_copy_id": copy_id, "release_id": workflow["accepted_release_id"],
        "workflow_phase": revised["phase"],
        "new_archive_publication": False,
        "note": ("Go now uses the independently verified refreshed staging copy. "
                 "No archive was published and the original rip and previous copy "
                 "remain unchanged. Review a NEW archive preview before approval. "
                 "Physical edition inference status remains unchanged."),
    }
