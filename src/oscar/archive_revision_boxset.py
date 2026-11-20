"""Read-only coordinated label review for archived multidisc MusicBrainz releases.

This is a planning and provenance check only. It deliberately cannot apply a
partial boxset: multiple disc folders need one journaled all-or-none revision.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from oscar import archive_metadata_scan as scanner
from oscar import archive_revision as revision, collection_catalog as catalog

_UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")


class BoxsetReviewError(ValueError):
    pass


def preview(release_id, *, lookup=None):
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
    target_labels = None
    result = []
    provider = lookup or scanner.lookup_release_medium
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
        candidates = scanner._fresh_values(snapshot, provider)
        match = [item for item in candidates if item[:3] == ("release", 0, "LABEL")]
        if len(match) != 1:
            raise BoxsetReviewError("Could not obtain one exact physical release label")
        _, _, _, existing, incoming = match[0]
        if not incoming:
            raise BoxsetReviewError("MusicBrainz release has no verified label for these physical discs")
        normalized = scanner._canonical(incoming)
        if target_labels is None:
            target_labels = normalized
        if target_labels != normalized:
            raise BoxsetReviewError("MusicBrainz label differs across discs of one physical release")
        with revision._db() as db:
            approvals = db.execute(
                "SELECT fingerprint,before_json,after_json,archive_revision,publish_id "
                "FROM metadata_proposals "
                "WHERE archive_path=? AND release_id=? AND status='accepted' "
                "AND field='LABEL' AND scope='release' AND track=0",
                (str(leaf), release_id)
            ).fetchall()
        already_correct = scanner._canonical(existing) == normalized
        accepted = (len(approvals) == 1
                    and approvals[0]["archive_revision"] == snapshot["manifest_sha256"]
                    and approvals[0]["publish_id"] == snapshot["publish_id"]
                    and json.loads(approvals[0]["before_json"]) == scanner._canonical(existing)
                    and json.loads(approvals[0]["after_json"]) == normalized)
        if len(approvals) > 1:
            raise BoxsetReviewError("Multiple competing accepted label approvals for one disc")
        status = "already_correct" if already_correct else (
            "approved_for_review" if accepted else "needs_operator_approval"
        )
        result.append({
            "disc": row["disc_number"],
            "archive_path": str(leaf),
            "publication_id": snapshot["publish_id"],
            "manifest_sha256": snapshot["manifest_sha256"],
            "track_count": len(snapshot["tracks"]),
            "existing_flac_labels": scanner._canonical(existing),
            "reviewed_labels": normalized,
            "label_status": status,
            "accepted_fingerprint": approvals[0]["fingerprint"] if accepted else None,
        })
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
    ready = all(d["label_status"] != "needs_operator_approval" for d in result)
    fingerprint = hashlib.sha256(json.dumps({
        "release_id": release_id, "discs": result, "missing": missing,
    }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {
        "release_id": release_id,
        "album_directory": str(parent),
        "disc_total": total,
        "present_disc_numbers": present,
        "missing_disc_numbers": missing,
        "partial_boxset": bool(missing),
        "reviewed_labels": target_labels,
        "disc_reviews": result,
        "all_present_discs_reviewed": ready,
        "fingerprint": fingerprint,
        "apply_supported": False,
        "note": (
            "Read-only group preview; no FLAC, manifest or Collection changes. "
            "Coordinated all-or-none multidisc apply is NOT implemented. "
            "Absent physical CDs will not be invented or silently updated. "
            "Do not use the single-disc archive revision Apply button for this release."
        ),
    }
