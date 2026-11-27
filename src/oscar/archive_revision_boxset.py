"""Coordinated preview for archived multidisc MusicBrainz releases.

Preview is read-only. A separate opt-in, journaled group engine handles Apply.
"""
from __future__ import annotations

import hashlib
import os
import json
from pathlib import Path
import re

from oscar import archive_metadata_scan as scanner
from oscar.boxsets import cached_release_lookup
from oscar import archive_revision as revision, collection_catalog as catalog

FIELDS = ("LABEL", "GENRE", "RELEASECOUNTRY")
MODES = (*FIELDS, "METADATA")

_UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")


class BoxsetReviewError(ValueError):
    pass


def preview(release_id, *, lookup=None, field="LABEL"):
    if field not in MODES:
        raise BoxsetReviewError("Unsupported coordinated migration field")
    fields = FIELDS if field == "METADATA" else (field,)
    if not isinstance(release_id, str) or not _UUID.fullmatch(release_id):
        raise BoxsetReviewError("A full MusicBrainz release UUID is required")
    root = catalog.archive_root()
    with revision._db() as db:
        albums = db.execute(
            "SELECT archive_path,disc_number,disc_total FROM archive_items "
            "WHERE musicbrainz_release_id=? ORDER BY disc_number", (release_id,)
        ).fetchall()
    if not albums:
        raise BoxsetReviewError("No indexed OSCAR archive leaves for this MusicBrainz release")
    if len(albums) > 99:
        raise BoxsetReviewError("Too many indexed discs for one boxset")
    total = albums[0]["disc_total"]
    if type(total) is not int or total <= 1:
        raise BoxsetReviewError("Selected release is not an indexed multidisc boxset")
    if any(row["disc_total"] != total for row in albums):
        raise BoxsetReviewError("Inconsistent disc-total information in Collection")
    present = [row["disc_number"] for row in albums]
    if len(set(present)) != len(present) or any(
        not isinstance(n, int) or not 1 <= n <= total for n in present
    ):
        raise BoxsetReviewError("Invalid or duplicated physical medium positions")
    parent = None
    targets = {}
    result = []
    provider = lookup or cached_release_lookup()
    for row in albums:
        leaf = Path(row["archive_path"])
        relative = leaf.relative_to(root)
        if len(relative.parts) != 3 or not re.fullmatch(r"Disc \d{2}", leaf.name):
            raise BoxsetReviewError("Boxset discs must have a shared artist/album/Disc NN layout")
        if parent is None:
            parent = leaf.parent
        if leaf.parent != parent:
            raise BoxsetReviewError("Different album folders were indexed as one physical boxset")
        snapshot = scanner._archive_snapshot(str(leaf))
        if snapshot["release_id"] != release_id or snapshot["disc_number"] != row["disc_number"]:
            raise BoxsetReviewError("Published manifest does not match indexed physical CD medium")
        source = json.loads((leaf / "manifest.json").read_text(encoding="utf-8"))
        if source.get("disc_total") != total:
            raise BoxsetReviewError("Published disc-total metadata differs from Collection")
        candidates, genre_source = scanner._fresh_values(snapshot, provider)
        with revision._db() as db:
            approvals = db.execute(
                "SELECT * FROM metadata_proposals "
                "WHERE archive_path=? AND release_id=? AND status='accepted'",
                (str(leaf), release_id),
            ).fetchall()
        reviewed = {}
        for name in fields:
            match = next((item for item in candidates if item[:3] == ("release", 0, name)), None)
            before = scanner._canonical(match[3]) if match else []
            after = scanner._canonical(match[4]) if match else []
            if name in targets and targets[name] != after:
                raise BoxsetReviewError("MusicBrainz " + name + " differs across discs of one release")
            targets[name] = after
            accepted = [row for row in approvals if row["field"] == name
                        and row["scope"] == "release" and row["track"] == 0]
            if len(accepted) > 1:
                raise BoxsetReviewError("Multiple competing accepted " + name + " approvals for one disc")
            approval = accepted[0] if accepted and before != after else None
            if approval and (not match or not after
                             or approval["archive_revision"] != snapshot["manifest_sha256"]
                             or approval["publish_id"] != snapshot["publish_id"]
                             or not scanner._matches_proposal(match, approval, genre_source)):
                raise BoxsetReviewError("Stale " + name + " approval on disc " + str(row["disc_number"]))
            status = ("approved_for_review" if approval else "unavailable" if not after else
                      "already_correct" if before == after else "needs_operator_approval")
            reviewed[name] = {"before": before, "after": after, "status": status,
                              "fingerprint": approval["fingerprint"] if approval else None}
            if approval and approval["source_url"]:
                reviewed[name]["source_url"] = approval["source_url"]
        disc = {
            "disc": row["disc_number"],
            "archive_path": str(leaf),
            "publication_id": snapshot["publish_id"],
            "manifest_sha256": snapshot["manifest_sha256"],
            "track_count": len(snapshot["tracks"]),
            "metadata": reviewed,
        }
        if field in ("LABEL", "GENRE"):
            for name, key in (("LABEL", "label"), ("GENRE", "genre")):
                values = reviewed.get(name, {})
                disc[f"existing_flac_{key}s"] = values.get("before", [])
                disc[f"reviewed_{key}s"] = values.get("after", [])
                disc[f"{key}_status"] = values.get("status", "")
            disc["accepted_fingerprint"] = reviewed[field]["fingerprint"]
        result.append(disc)
    # Never silently omit a newly published disc that has not yet been
    # imported into Collection. A future coordinated Apply must include every
    # published leaf of the release, not just the currently indexed subset.
    indexed_paths = {Path(row["archive_path"]) for row in albums}
    for sibling in parent.iterdir():
        if not re.fullmatch(r"Disc \d{2}", sibling.name):
            continue
        if sibling.is_symlink():
            raise BoxsetReviewError("Unsafe linked physical disc directory in boxset")
        if sibling.is_dir() and (sibling / "manifest.json").exists():
            if sibling not in indexed_paths:
                raise BoxsetReviewError(
                    "Unindexed published disc detected; refresh Collection before reviewing this boxset"
                )
    missing = sorted(set(range(1, total + 1)) - set(present))
    active = [name for name in fields if any(d["metadata"][name]["fingerprint"] for d in result)]
    required = active if field == "METADATA" else fields
    ready = all(d["metadata"][name]["status"] in ("already_correct", "approved_for_review")
                for d in result for name in required)
    actionable = ready and bool(active)
    enabled = os.environ.get("OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS") == "1"
    fingerprint = hashlib.sha256(json.dumps({
        "release_id": release_id, "discs": result, "missing": missing,
        **({"field": field} if field != "LABEL" else {}),
    }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {
        "release_id": release_id,
        "album_directory": str(parent),
        "disc_total": total,
        "present_disc_numbers": present,
        "missing_disc_numbers": missing,
        "partial_boxset": bool(missing),
        "field": field,
        "reviewed_labels": targets.get("LABEL", []),
        "reviewed_genres": targets.get("GENRE", []),
        "active_fields": active,
        "disc_reviews": result,
        "all_present_discs_reviewed": ready,
        "fingerprint": fingerprint,
        "apply_supported": bool(actionable and enabled),
        "note": (
            "Read-only group preview; no FLAC, manifest or Collection changes. "
            "A separate opt-in group engine can migrate only explicitly approved present discs; "
            "missing physical CDs will never be fabricated. "
            "The group promotion is recoverable but not multi-directory filesystem atomic. "
            "Never use the single-disc archive revision Apply button for this boxset."
        ),
    }
