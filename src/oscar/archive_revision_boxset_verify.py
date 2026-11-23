"""Independent read-only verification of completed coordinated boxset revisions.

Audits original and revised FLAC Vorbis comments field-by-field. Only the
operator-approved fields (plus a pre-existing RECORDLABEL alias) may differ.
Never edits archives, Collection, or prior operation journal records.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from mutagen.flac import FLAC
from oscar import archive_revision_boxset_apply as group
from oscar.archive_revision_boxset import FIELDS
from oscar import collection_catalog as catalog

_ID = re.compile(r"[0-9a-f]{32}\Z")


def _tags(path):
    return {str(key).upper(): sorted(str(v) for v in values)
            for key, values in FLAC(str(path)).tags.items()}


def compare_tags(original, revised, approved, *, field="LABEL"):
    return _compare_changes(original, revised, {field: approved})


def _compare_changes(original, revised, approved):
    """Return exact unexpected tag changes; case-insensitive Vorbis names."""
    if not set(approved) <= set(FIELDS):
        raise ValueError("Unsupported verified metadata field")
    before, after = _tags(original), _tags(revised)
    expected = {**before, **{field: sorted(str(v) for v in values)
                            for field, values in approved.items()}}
    if "LABEL" in approved and before.get("RECORDLABEL"):
        expected["RECORDLABEL"] = expected["LABEL"]
    return {field: {"before": before.get(field, []), "after": after.get(field, [])}
            for field in set(expected) | set(after)
            if expected.get(field, []) != after.get(field, [])}


def _successor_backup(entry, operations):
    matches = [(row, successor) for row in operations
               for successor in json.loads(row["entries_json"])
               if successor["source"] == entry["source"]
               and successor["old_publish_id"] == entry["new_publish_id"]]
    if not matches:
        return None
    if len(matches) != 1 or matches[0][0]["status"] != "completed":
        raise group.BoxsetApplyError("Ambiguous or unfinished successor revision")
    row, successor = matches[0]
    backup = Path(successor["backup"])
    expected = catalog.archive_root() / ".oscar-archive-versions" / entry["new_publish_id"] / (
        row["operation_id"] + "-disc-" + str(entry["disc"]).zfill(2)
    )
    if backup != expected or backup.resolve() != backup:
        raise group.BoxsetApplyError("Unsafe successor retained-generation path")
    group._validate_leaf(backup, successor, new=False)
    return backup


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
        operations = db.execute(
            "SELECT operation_id,status,entries_json FROM boxset_revision_operations "
            "WHERE release_id=? AND status IN ('completed','prepared') AND operation_id<>?",
            (row["release_id"], operation_id),
        ).fetchall()
    entries = json.loads(row["entries_json"])
    if not isinstance(entries, list) or not entries or len(entries) > 99:
        raise group.BoxsetApplyError("Invalid group journal entries")

    results = []
    for entry in entries:
        disc = entry["disc"]
        original, live = Path(entry["backup"]), Path(entry["source"])
        changes = group.journal_changes(entry)
        approved = {change["field"]: change["after"] for change in changes}
        errors = []
        track_count = None
        new_manifest = {}
        historical = False
        try:
            retained = _successor_backup(entry, operations)
            historical = retained is not None
            revised = retained or live
            pair = {**entry, "source": str(revised)}
            group._validate_leaf(original, entry, new=False)
            group._validate_leaf(revised, entry, new=True)
            group._verify_audio_pair(pair)
            group._verify_non_audio_pair(pair)
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
                differences = _compare_changes(original / key, revised / key, approved)
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
                "SELECT label,label_provenance,genres,library_section,musicbrainz_release_id,disc_number "
                "FROM archive_items WHERE archive_path=?", (str(live),)
            ).fetchone()
            decisions = [db.execute(
                "SELECT status,archive_path FROM metadata_proposals WHERE fingerprint=?",
                (change["fingerprint"],),
            ).fetchone() for change in changes]
        if (item is None or item["musicbrainz_release_id"] != row["release_id"]
                or item["disc_number"] != disc):
            errors.append("Collection row does not match physical disc identity")
        elif not historical:
            if "LABEL" in approved and (item["label"] != "; ".join(approved["LABEL"]) or
                    item["label_provenance"] != "archive_revision_approved_labels"):
                errors.append("Collection label does not match approved revision")
            if "GENRE" in approved:
                from oscar.archive_genres import classify
                expected = classify(approved["GENRE"], profile=new_manifest.get("profile"))
                if (item["genres"] != expected["genres"] or
                        item["library_section"] != expected["library_section"]):
                    errors.append("Collection genre does not match approved revision")
        if any(decision is None or decision["status"] != "applied" or
               decision["archive_path"] != str(live) for decision in decisions):
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
