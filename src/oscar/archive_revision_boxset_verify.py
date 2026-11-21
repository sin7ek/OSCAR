"""Independent read-only verification of completed coordinated boxset revisions.

Audits original and revised FLAC Vorbis comments field-by-field. Only the
operator-approved LABEL and its existing RECORDLABEL alias may differ.
Never edits archives, Collection, or prior operation journal records.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from mutagen.flac import FLAC
from oscar import archive_revision_boxset_apply as group
from oscar import collection_catalog as catalog

_ID = re.compile(r"[0-9a-f]{32}\Z")
_ALLOWED = {"LABEL", "RECORDLABEL"}


def _tags(path):
    return {str(key).upper(): sorted(str(v) for v in values)
            for key, values in FLAC(str(path)).tags.items()}


def compare_tags(original, revised, approved):
    """Return exact unexpected tag changes; case-insensitive Vorbis names."""
    before, after = _tags(original), _tags(revised)
    unexpected = {}
    for field in sorted(set(before) | set(after)):
        if before.get(field, []) == after.get(field, []):
            continue
        if field in _ALLOWED:
            if after.get(field, []) != sorted(str(v) for v in approved):
                unexpected[field] = {"before": before.get(field, []),
                                     "after": after.get(field, [])}
            if field == "RECORDLABEL" and not before.get(field):
                unexpected[field] = {"before": [], "after": after.get(field, [])}
            continue
        unexpected[field] = {"before": before.get(field, []),
                             "after": after.get(field, [])}
    # No unexpected new RECORDLABEL alias on an otherwise unlabeled source.
    return unexpected


def verify(operation_id):
    if not isinstance(operation_id, str) or not _ID.fullmatch(operation_id):
        raise group.BoxsetApplyError("Invalid group operation ID")
    with group._db() as db:
        row = db.execute(
            "SELECT release_id,status,entries_json FROM boxset_revision_operations "
            "WHERE operation_id=?", (operation_id,)
        ).fetchone()
    if row is None:
        raise group.BoxsetApplyError("Unknown group operation")
    if row["status"] != "completed":
        raise group.BoxsetApplyError("Only completed group operations can be independently verified")
    entries = json.loads(row["entries_json"])
    if not isinstance(entries, list) or not entries or len(entries) > 99:
        raise group.BoxsetApplyError("Invalid group journal entries")

    results = []
    for entry in entries:
        disc = entry["disc"]
        original, revised = Path(entry["backup"]), Path(entry["source"])
        errors = []
        track_count = None
        try:
            group._validate_leaf(original, entry, new=False)
            group._validate_leaf(revised, entry, new=True)
            group._verify_audio_pair(entry)
            group._verify_non_audio_pair(entry)
            old_manifest = json.loads((original / "manifest.json").read_text(encoding="utf-8"))
            new_manifest = json.loads((revised / "manifest.json").read_text(encoding="utf-8"))
            old_files = {x["filename"]: x for x in old_manifest["files"]}
            track_count = len(old_files)
            new_files = {x["filename"]: x for x in new_manifest["files"]}
            if old_manifest.get("release_id") != row["release_id"]:
                errors.append("Journal release differs from retained original")
            if old_manifest.get("disc_number") != disc:
                errors.append("Journal disc position differs from original")
            for key in sorted(set(old_files) & set(new_files)):
                differences = compare_tags(original / key, revised / key, entry["after"])
                if differences:
                    errors.append(f"Track {key}: unexpected metadata differences in " +
                                  ", ".join(sorted(differences)))
                # Old generation was already SHA verified, but test decoder independently.
                completed = subprocess.run(
                    ["flac", "-t", "--silent", str(original / key)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=180, check=False,
                )
                if completed.returncode != 0:
                    errors.append(f"Retained original cannot be decoded: {key}")
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
            errors.append(f"{type(exc).__name__}: {exc}"[:300])
        with group._db() as db:
            item = db.execute(
                "SELECT label,label_provenance,musicbrainz_release_id,disc_number "
                "FROM archive_items WHERE archive_path=?", (str(revised),)
            ).fetchone()
            decisions = db.execute(
                "SELECT status FROM metadata_proposals WHERE fingerprint=?",
                (entry["fingerprint"],)
            ).fetchall()
        if (item is None or item["musicbrainz_release_id"] != row["release_id"]
                or item["disc_number"] != disc or
                item["label"] != "; ".join(entry["after"]) or
                item["label_provenance"] != "archive_revision_approved_labels"):
            errors.append("Collection row does not match approved revised disc")
        if len(decisions) != 1 or decisions[0]["status"] != "applied":
            errors.append("Approved metadata decision is not marked applied")
        results.append({
            "disc": disc, "tracks": track_count,
            "status": "pass" if not errors else "failed",
            "observations": errors,
        })
    return {
        "operation_id": operation_id, "release_id": row["release_id"],
        "status": "pass" if all(r["status"] == "pass" for r in results) else "failed",
        "verified_discs": results,
        "note": (
            "Read-only check of both generations, decoded audio, manifest hashes, "
            "evidence, metadata-diff allowlist, and Collection decisions. "
            "Does not independently authenticate MusicBrainz physical editions or CTDB."
        ),
    }
