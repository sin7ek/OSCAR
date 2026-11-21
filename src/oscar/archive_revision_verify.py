"""Independent, read-only verification of an OSCAR archive revision.

Verify is safe to repeat. It checks the current publication, retained original,
every approved FLAC tag, audio decoding, original CUE/evidence, and Collection.
It does NOT delete or move anything; cleanup needs a separate safety review.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

from mutagen.flac import FLAC

from oscar import archive_revision as revision, archive_metadata_scan as scan
from oscar import collection_catalog as catalog
from oscar.metadata_staging import _streaminfo_md5_hex


class ArchiveVerifyError(ValueError):
    pass


def _non_flac_digest_map(album):
    result = {}
    for folder, directories, files in os.walk(album, followlinks=False):
        for name in directories + files:
            if (Path(folder) / name).is_symlink():
                raise ArchiveVerifyError("Symlink in archived evidence")
        for name in files:
            path = Path(folder) / name
            relative = path.relative_to(album).as_posix()
            if relative == "manifest.json" or relative.lower().endswith(".flac"):
                continue
            result[relative] = scan._digest(path)
    return result


def _verify_locked(operation_id):
    if not isinstance(operation_id, str) or not re.fullmatch(r"[a-f0-9]{32}", operation_id):
        raise ArchiveVerifyError("Invalid operation ID")
    with revision._db() as db:
        row = db.execute("SELECT * FROM archive_revision_operations WHERE operation_id=?",
                         (operation_id,)).fetchone()
        if row is None or row["status"] != "completed":
            raise ArchiveVerifyError("Only completed archive revisions can be verified")
        proposals = []
        for fingerprint in json.loads(row["proposal_fingerprints"]):
            proposal = db.execute(
                "SELECT status,scope,track,field,after_json FROM metadata_proposals "
                "WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if proposal is None or proposal["status"] != "applied":
                raise ArchiveVerifyError("A reviewed metadata decision was not marked applied")
            proposals.append(proposal)
        chain = [row]
        seen = {row["operation_id"]}
        while True:
            previous = chain[-1]
            successors = db.execute(
                "SELECT * FROM archive_revision_operations "
                "WHERE source_publish_id=? AND source_path=?",
                (previous["new_publish_id"], previous["dest_path"]),
            ).fetchall()
            if not successors:
                break
            if len(successors) != 1 or successors[0]["status"] != "completed":
                raise ArchiveVerifyError("Ambiguous or unfinished archive revision successor")
            successor = successors[0]
            if successor["operation_id"] in seen:
                raise ArchiveVerifyError("Cycle in archive revision journal")
            seen.add(successor["operation_id"])
            chain.append(successor)
            if len(chain) > 100:
                raise ArchiveVerifyError("Unreasonably long archive revision chain")
        latest = chain[-1]
        linked = db.execute(
            "SELECT archive_path,catalog_number,label,label_provenance FROM archive_items "
            "WHERE archive_path=?", (latest["dest_path"],)
        ).fetchall()
    if len(linked) != 1:
        raise ArchiveVerifyError("Collection is not uniquely linked to latest publication")
    if linked[0]["catalog_number"] != latest["target_catalog"]:
        raise ArchiveVerifyError("Collection catalog number differs from latest revision")
    if (latest["target_label"] and linked[0]["label"] != latest["target_label"]
            and linked[0]["label_provenance"] not in ("manual", "operator_curated")):
        raise ArchiveVerifyError(
            "Collection Label is stale; synchronize applied labels before verifying"
        )
    root = catalog.archive_root()
    old = Path(row["backup_path"])
    new = Path(row["dest_path"])
    expected = root / ".oscar-archive-versions" / row["source_publish_id"] / operation_id
    if (old != expected or not old.is_relative_to(root)
            or not new.is_relative_to(root) or new == root):
        raise ArchiveVerifyError("Unsafe retained archive history path")
    for album in (old, new):
        if not album.is_dir() or album.is_symlink() or album.resolve(strict=True) != album:
            raise ArchiveVerifyError("Archived original or revised directory missing or unsafe")
    if old.parent.is_symlink() or old.parent.parent.is_symlink():
        raise ArchiveVerifyError("Symlink in archive history parent")
    if scan._digest(old / "manifest.json") != row["source_manifest_sha256"]:
        raise ArchiveVerifyError("Retained original publication manifest hash changed")
    original = json.loads((old / "manifest.json").read_text(encoding="utf-8"))
    current = json.loads((new / "manifest.json").read_text(encoding="utf-8"))
    lineage = current.get("revision") or {}
    if (original.get("publish_id") != row["source_publish_id"]
            or current.get("publish_id") != row["new_publish_id"]
            or lineage.get("parent_publish_id") != row["source_publish_id"]
            or lineage.get("parent_manifest_sha256") != row["source_manifest_sha256"]):
        raise ArchiveVerifyError("Archive publication ancestry differs from journal")
    # Historical versions are intentionally hidden under a 4-level archive
    # history path, not the regular /artist/album layout understood by the
    # live archive scanner. Verify their original hashes directly instead.
    new_snapshot = scan._archive_snapshot(str(new))
    if original.get("release_id") != new_snapshot["release_id"]:
        raise ArchiveVerifyError("Original/new MusicBrainz release identity differs")
    old_files = original.get("files") or []
    new_files = current.get("files") or []
    if (not old_files or len(old_files) != len(new_files)
            or [item["filename"] for item in old_files] !=
            [item["filename"] for item in new_files]):
        raise ArchiveVerifyError("Original and revised track manifest mismatch")
    # Refuse unlisted audio files in either generation: they would otherwise
    # become duplicate media library tracks without manifest integrity proof.
    for directory, entries in ((old, old_files), (new, new_files)):
        declared = {item["filename"] for item in entries}
        actual = {path.name for path in directory.iterdir() if path.suffix.lower() == ".flac"}
        if declared != actual:
            raise ArchiveVerifyError("Unlisted or missing FLAC in archived publication")
    revision._verify_preserved_evidence(old, original)
    revision._verify_preserved_evidence(new, current)
    if _non_flac_digest_map(old) != _non_flac_digest_map(new):
        raise ArchiveVerifyError("Non-audio evidence or cover art differs from original")
    checked = 0
    for index, (before, after) in enumerate(zip(old_files, new_files), 1):
        original_file = old / before["filename"]
        if (original_file.is_symlink() or not original_file.is_file()
                or scan._digest(original_file) != before["sha256"]):
            raise ArchiveVerifyError("Retained original FLAC SHA-256 mismatch")
        source = FLAC(str(original_file))
        target = FLAC(str(new / after["filename"]))
        if ((source.get("MUSICBRAINZ_ALBUMID") or []) != [new_snapshot["release_id"]]
                or (source.get("MUSICBRAINZ_DISCID") or []) != [new_snapshot["disc_id"]]):
            raise ArchiveVerifyError("Original/new MusicBrainz CD identity differs")
        if (_streaminfo_md5_hex(source.info.md5_signature)
                != _streaminfo_md5_hex(target.info.md5_signature)):
            raise ArchiveVerifyError("FLAC audio STREAMINFO MD5 was changed")
        for proposal in proposals:
            if proposal["scope"] == "track" and proposal["track"] != index:
                continue
            if scan._canonical((target.get(proposal["field"]) or [])) != scan._canonical(
                    json.loads(proposal["after_json"])):
                raise ArchiveVerifyError("Archived FLAC differs from reviewed metadata")
        for path in (old / before["filename"], new / after["filename"]):
            try:
                response = subprocess.run(
                    ["flac", "-t", "--silent", str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=180, check=False,
                )
            except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
                raise ArchiveVerifyError("FLAC decoder unavailable or timed out") from exc
            if response.returncode:
                raise ArchiveVerifyError("Original or revised FLAC failed decoding")
        checked += 1
    # This content-bound receipt can be submitted for an explicitly opted-in
    # cleanup. Cleanup MUST run this entire verification again under the lock.
    fingerprint = hashlib.sha256(json.dumps({
        "operation_id": operation_id,
        "old_manifest": row["source_manifest_sha256"],
        "new_manifest": scan._digest(new / "manifest.json"),
        "old_flacs": [entry["sha256"] for entry in old_files],
        "new_flacs": [entry["sha256"] for entry in new_files],
        "approved": row["proposal_fingerprints"],
        "collection": [linked[0]["catalog_number"], linked[0]["label"],
                       linked[0]["label_provenance"]],
    }, sort_keys=True).encode()).hexdigest()
    return {
        "verification_fingerprint": fingerprint,
        "operation_id": operation_id, "status": "verified",
        "original_flacs_verified": checked,
        "revised_flacs_verified": checked,
        "approved_fields_verified": len(proposals),
        "manifest_and_evidence_verified": True,
        "collection_verified": True,
        "original_retained": True,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "note": "Read-only; neither the revised archive nor retained originals were modified.",
    }


def verify(operation_id):
    root = catalog.archive_root()
    lock_path = root / ".oscar-publish.lock"
    if lock_path.is_symlink():
        raise ArchiveVerifyError("Unsafe archive publish lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return _verify_locked(operation_id)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
