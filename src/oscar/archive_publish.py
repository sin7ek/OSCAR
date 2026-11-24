"""Opt-in, non-destructive archive publisher for reviewed, verified FLAC copies.

Only configured OSCAR_ARCHIVE_ROOT is writable. A new folder is assembled,
verified and renamed into place under an exclusive filesystem lock.
Neither original rips nor tagged staging copies are ever touched.
"""
from __future__ import annotations

import fcntl
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import threading
import time
import uuid

from mutagen.flac import FLAC, Picture

from oscar import archive_review, cover_art, ctdb_verification, edition_provenance, verification
from oscar.archive_naming import safe_component
from oscar.metadata_staging import _COPY_ID, _streaminfo_md5_hex
from oscar.pressing_evidence import observed_matrix

_LOCK = threading.RLock()
_JOBS = {}
_RUNNING = set()
_CONFIRM = "PUBLISH_REVIEWED_ARCHIVE"


class PublishError(RuntimeError):
    pass


def archive_root():
    configured = os.environ.get("OSCAR_ARCHIVE_ROOT", "").strip()
    if not configured:
        raise PublishError("Archive publishing is disabled: set OSCAR_ARCHIVE_ROOT to a dedicated writable mount")
    root = Path(configured)
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise PublishError("Configured archive root must be an existing, real, absolute directory")
    from oscar.ripping import staging_root
    stage = staging_root().resolve()
    resolved = root.resolve()
    if resolved == Path("/") or resolved == stage or resolved.is_relative_to(stage) or stage.is_relative_to(resolved):
        raise PublishError("Archive must be on a separate, dedicated mount outside staging")
    if root != resolved:
        raise PublishError("Archive root must not contain symbolic links in its path")
    return root


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _check_directory(path, root):
    if not path.is_relative_to(root):
        raise PublishError("Unsafe archive destination")
    current = root
    for component in path.relative_to(root).parts:
        current = current / component
        if current.is_symlink():
            raise PublishError("Symlink in archive path")
        if current.exists() and not current.is_dir():
            raise PublishError("Archive destination path is not a directory")


def _rename_noreplace(source, destination):
    """Linux renameat2(RENAME_NOREPLACE): never replace another publisher's path."""
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        method = libc.renameat2
    except AttributeError as exc:
        raise PublishError("Kernel/libc lacks safe no-replace directory rename") from exc
    method.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
    method.restype = ctypes.c_int
    at_fdcwd = -100
    status = method(at_fdcwd, os.fsencode(source), at_fdcwd,
                    os.fsencode(destination), 1)  # RENAME_NOREPLACE
    if status != 0:
        reason = ctypes.get_errno()
        if reason == errno.EEXIST:
            raise PublishError("Archive target already exists; refusing overwrite")
        # Unraid /mnt/user is backed by shfs (FUSE). Some mounts reject
        # renameat2(RENAME_NOREPLACE) with EINVAL/EOPNOTSUPP even when an
        # ordinary same-directory rename is supported. OSCAR's caller holds
        # the exclusive cross-process .oscar-publish.lock on this archive
        # root; the destination is also checked immediately before rename.
        # The fallback prevents overwrites by cooperating OSCAR publishers.
        # Use a dedicated archive mount not writable by other processes.
        if reason in {errno.EINVAL, errno.EOPNOTSUPP, errno.ENOTSUP, errno.ENOSYS}:
            if destination.exists() or destination.is_symlink():
                raise PublishError("Archive target already exists; refusing overwrite")
            try:
                os.rename(source, destination)
            except OSError as exc:
                raise PublishError("Filesystem could not promote verified archive: " + str(exc)) from exc
            return
        raise PublishError(f"Atomic publication failed: {os.strerror(reason)}")


def _names(review):
    album = review["album"]
    artist = safe_component(album.get("artist") or "Unknown Album Artist")
    title = safe_component(album.get("title"))
    catalog = (album.get("catalog_numbers") or [None])[0]
    year = str(album.get("date") or "")[:4]
    ident = review["release_id"].split("-")[0]
    label = (f"[{safe_component(catalog)}] " if catalog else "") + title
    if re.fullmatch(r"\d{4}", year):
        label += f" ({year})"
    label += f" [{ident}]"
    preview = review["cue"]
    tracks = review["tracks"]
    if preview.get("status") != "preview_requires_review":
        raise PublishError("CUE is not ready for review")
    names = preview.get("proposed_filenames") or []
    if len(names) != len(tracks) or len(set(x.casefold() for x in names)) != len(names):
        raise PublishError("Unsafe or colliding archive track filenames")
    for item in names:
        if item != Path(item).name or not item.lower().endswith(".flac") or '"' in item or "\n" in item:
            raise PublishError("Unsafe archive filename")
    # Preview metadata stores disc numbers on per-track tags; derive from the
    # original reviewed metadata, not an inferred track count.
    _, _, preview_data, _, _ = archive_review._load(
        review["job_id"], review["copy_id"], review["kind"])
    one = preview_data.get("tracks") or []
    if len(one) != len(tracks):
        raise PublishError("Unexpected stored track count")
    first_tags = (one[0].get("tags") or {})
    disc_number = int(first_tags.get("DISCNUMBER") or 1)
    disc_total = int(first_tags.get("DISCTOTAL") or 1)
    if not (1 <= disc_number <= disc_total <= 99):
        raise PublishError("Invalid reviewed disc position")
    if any(int((t.get("tags") or {}).get("DISCNUMBER") or 1) != disc_number for t in one):
        raise PublishError("Mixed disc numbers in a single source copy")
    # Avoid combining multiple discs in one leaf. Each disc is independently
    # published; the release folder can be reused but may not be overwritten.
    relative = Path(artist) / label
    if disc_total > 1:
        relative /= f"Disc {disc_number:02d}"
    return relative, names, disc_number, disc_total


def prepare(job_id, copy_id, kind="original_tags", profile="auto",
            *, include_cover=False):
    if not _COPY_ID.fullmatch(job_id) or not _COPY_ID.fullmatch(copy_id):
        raise PublishError("Invalid rip or copy ID")
    if kind not in {"original_tags", "classical_v2"}:
        raise PublishError("Invalid copy kind")
    if profile not in {"auto", "standard", "classical"}:
        raise PublishError("Invalid processing profile")
    root = verification._safe_job(job_id)
    verification_report = verification.report(job_id)
    if verification_report.get("status") != "checks_passed":
        raise PublishError("Source rip verification must pass before publishing")
    review = archive_review.review(job_id, copy_id, kind, profile=profile, artwork=False)
    relative, names, disc_number, disc_total = _names(review)
    _, tagged_folder, saved_preview, source_manifest, tracks = archive_review._load(
        job_id, copy_id, kind)
    files = source_manifest["files"]
    records = []
    for track, filename in zip(tracks, names):
        rel = track["file"]
        entry = files.get(rel)
        if not isinstance(entry, dict):
            raise PublishError("Missing tagged FLAC evidence")
        expected = entry.get("tagged_sha256")
        audio_md5 = entry.get("audio_streaminfo_md5")
        if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise PublishError("Missing tagged FLAC SHA-256")
        if not isinstance(audio_md5, str) or not re.fullmatch(r"[a-f0-9]{32}", audio_md5):
            raise PublishError("Missing source STREAMINFO audio MD5")
        source_path = tagged_folder / rel
        if source_path.is_symlink() or not source_path.is_file():
            raise PublishError("Unsafe tagged FLAC file")
        records.append({"number": track["number"], "source": rel,
                        "filename": filename, "expected_sha256": expected,
                        "audio_md5": audio_md5})
        source_sha = entry.get("source_sha256")
        if kind == "original_tags" and isinstance(source_sha, str) and re.fullmatch(r"[a-f0-9]{64}", source_sha):
            records[-1]["rip_sha256"] = source_sha
    ctdb_verification.automatic(job_id, root)
    ctdb = ctdb_verification.saved_evidence(job_id, root)
    evidence = _source_evidence(job_id, include_ctdb=bool(ctdb))
    recovery = _recovery_provenance(root, review["album"], records, verification_report)
    provenance = {
        "metadata_source": saved_preview.get("source") or "MusicBrainz",
        "verification_method": verification_report.get("verification_method") or
        ("cyanrip" if verification_report.get("tracks") else "not_recorded"),
        "accuraterip_coverage": verification_report.get("accuraterip_coverage"),
        "track_verification": {t["number"]: t.get("accuraterip", {})
                               for t in verification_report.get("tracks", [])},
        "recovery": recovery,
    }
    if genre_source_url := saved_preview.get("album", {}).get("genre_source_url"):
        provenance["genre_source_url"] = genre_source_url
    if ar_lookup := verification_report.get("accuraterip_lookup"):
        provenance["accuraterip_lookup"] = ar_lookup
    edition_search = edition_provenance.for_release(
        root, job_id, review["album"].get("musicbrainz_disc_id"), review["release_id"])
    if edition_search:
        provenance["edition_search"] = edition_search
    if ctdb:
        result, report_hash = ctdb
        if not any(item["source"] == ctdb_verification.REPORT and item["sha256"] == report_hash
                   for item in evidence):
            raise PublishError("CTDB report changed during archive preview; retry")
        provenance["ctdb"] = result
    if matrix := observed_matrix(review["album"].get("matrix_runout")):
        provenance["physical_matrix_runout"] = {"value": matrix, "source": "operator_transcription"}
    if include_cover:
        selected = cover_art.load(tagged_folder, review["release_id"])
        if not selected:
            raise PublishError("Load or upload a cover before previewing publication")
        provenance["artwork"] = selected[0]
    cue = review["cue"]["archive_cue_proposal"]
    if excluded := review["cue"].get("excluded_data_track"):
        provenance["excluded_data_track"] = excluded
    referenced = [match.group(1) for line in cue.splitlines()
                  if (match := archive_review._CUEFILE.match(line))]
    if referenced != names:
        raise PublishError("Archive CUE references do not match proposed FLAC names")
    if len(re.findall(r"(?m)^\s*INDEX 01\s+\d\d:\d\d:\d\d\s*$", cue)) != len(names):
        raise PublishError("Expected one sourced INDEX 01 per track; review the original CUE")
    # No network call or source audio hash on preview; the final publisher
    # rehashes and tests every byte before any rename.
    plan = {"job_id": job_id, "copy_id": copy_id, "kind": kind,
            "profile": review["music_profile"]["name"],
            "profile_request": profile,
            "release_id": review["release_id"], "album": review["album"],
            "relative_directory": relative.as_posix(),
            "disc_number": disc_number, "disc_total": disc_total,
            "tracks": records, "cue": cue, "source_evidence": evidence,
            "provenance": provenance,
            "include_cover": bool(include_cover),
            "metadata_observations": review["consistency"]["flags"],
            "original_preview_fingerprint": saved_preview.get("fingerprint"),
            "requires_explicit_review": True,
            "output_exists": (archive_root() / relative).exists(),
            "notes": [
                "Physical edition, CUE, cover and metadata exceptions require explicit operator review.",
                "This proposal does not rename, move or modify the original ripped or tagged staging files.",
                "The selected cover is embedded in the published FLAC copies and saved as folder.jpg.",
            ]}
    fingerprint_input = {k: v for k, v in plan.items()
                         if k not in {"output_exists", "notes"}}
    plan["fingerprint"] = hashlib.sha256(json.dumps(
        fingerprint_input, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    return plan


def _recovery_provenance(job, album, records, report):
    path = job / "recovery-sources.json"
    is_recovery = report.get("verification_method") == "independent_trackverify_R_v1_v2"
    if not is_recovery and not path.exists() and not report.get("recovery_sources"):
        return None
    if not is_recovery or not path.is_file() or path.is_symlink():
        raise PublishError("Missing or inconsistent track recovery evidence")
    try:
        recovery = json.loads(path.read_text(encoding="utf-8"))
        parent_ids = {key: recovery[key] for key in ("original_job_id", "diagnostic_job_id")}
        ids = set(parent_ids.values())
        tracks = recovery["tracks"]
        verification_tracks = report["tracks"]
        state = verification._load_job(job, report["job_id"])
        if (
            recovery["format"] != "OSCAR_TRACK_RECOVERY_V1"
            or parent_ids != report["recovery_sources"]
            or len(ids) != 2 or report["job_id"] in ids
            or not all(_COPY_ID.fullmatch(value) for value in ids)
            or recovery["disc_id"] != state["disc_id"]
            or (album.get("musicbrainz_disc_id") and recovery["disc_id"] != album["musicbrainz_disc_id"])
            or recovery["track_count"] != len(records)
            or len(tracks) != len(verification_tracks) or len(tracks) != len(records)
            or not any(track["source_job_id"] == parent_ids["diagnostic_job_id"] for track in tracks)
        ):
            raise ValueError
        for track, verified, record in zip(tracks, verification_tracks, records):
            source_path = track["source_path"]
            source_hash = track["source_sha256"]
            if (
                track["track"] != record["number"] or verified["number"] != record["number"]
                or track["source_job_id"] not in ids or track["source_job_id"] != verified["source_job_id"]
                or verified["file"] != record["source"] or not verified["checks_passed"]
                or not re.fullmatch(r"audio/[^/\r\n]+\.flac", source_path)
                or not re.fullmatch(r"[a-f0-9]{64}", source_hash)
                or source_hash != track["recovered_sha256"]
                or source_hash != state["files_sha256"][record["source"]]
                or source_hash != record.get("rip_sha256", source_hash)
                or verification.accuraterip_assessment(verified["accuraterip"])["status"] != "both_versions_matched"
            ):
                raise ValueError
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise PublishError("Inconsistent track recovery evidence") from exc
    return recovery


def _source_type(plan):
    return "HYBRID_REPAIRED_CD_RIP" if plan["provenance"]["recovery"] else "PHYSICAL_CD_RIP"


def render_sources(plan, release_match_status, *, published_files=None):
    """Render the same provenance text for Go review and archive publication."""
    provenance = plan["provenance"]
    recovery = provenance["recovery"]
    album = plan["album"]
    disc = plan["disc_number"]
    total = plan["disc_total"]
    disc_id = album.get("musicbrainz_disc_id") or (recovery or {}).get("disc_id") or "Not recorded"
    method = {
        "independent_trackverify_R_v1_v2": "Independent trackverify -R (AccurateRip v1 and v2, offset 0)",
        "cyanrip": "AccurateRip results reported by cyanrip during extraction",
        "cyanrip_cd_extra_accuraterip_lookup": "Independent AccurateRip full-CD-Extra TOC lookup; CRCs calculated by cyanrip during extraction",
    }.get(provenance["verification_method"], "Verification method not recorded")
    lines = [
        "OSCAR archive sources",
        f"SOURCE_TYPE: {_source_type(plan)}",
        f"Album: {album['artist']} — {album['title']}",
        f"Medium: Disc {disc:02d} of {total:02d}",
        f"Disc ID: {disc_id}",
        "",
        "[Metadata]",
        f"Source: {provenance['metadata_source']}",
        f"MusicBrainz release: https://musicbrainz.org/release/{plan['release_id']}",
        f"Physical edition status: {release_match_status}",
        f"Processing profile: {plan['profile']}",
        f"Tagged staging copy: {plan['copy_id']} ({plan['kind']})",
    ]
    if album.get("catalog_numbers"):
        lines.append("Catalog numbers from metadata: " + "; ".join(album["catalog_numbers"]))
    if matrix := provenance.get("physical_matrix_runout"):
        lines.append("Physical matrix/runout (operator transcription): " + matrix["value"])
    if album.get("genre_source"):
        lines.append(f"Genre metadata source: {album['genre_source']}")
        if genre_source_url := provenance.get("genre_source_url"):
            lines.append(f"Genre source release: {genre_source_url}")
    if cover := provenance.get("artwork"):
        lines.append("Front cover: " + (cover["source"] or "User upload") +
                     " · folder.jpg and FLAC PICTURE blocks")
        lines.append("Front cover SHA-256: " + cover["sha256"])
    if searches := provenance.get("edition_search"):
        lines.extend(edition_provenance.render(searches))
    lines.extend(["", "[Audio extraction]", f"Staging rip job: {plan['job_id']}"])
    if data_track := provenance.get("excluded_data_track"):
        lines.append(f"CD-Extra data track {data_track}: outside the audio archive; full original CUE retained in ExtractionEvidence")
    if recovery:
        lines.extend([
            f"Original full-disc rip job: {recovery['original_job_id']}",
            f"Replacement diagnostic rip job: {recovery['diagnostic_job_id']}",
            "The recovery job assembled the disc from both staging sources.",
        ])
    lines.extend(["", "[Verification]", method])
    if lookup := provenance.get("accuraterip_lookup"):
        lines.append("AccurateRip full-disc lookup: " + lookup["status"])
        lines.append("AccurateRip URL: " + lookup["url"])
        lines.append("AccurateRip physical TOC (LSN): " + lookup["disc_toc"])
    ctdb = provenance.get("ctdb")
    if ctdb:
        detail = f" ({ctdb['confidence']}/{ctdb['total']} confidence)" if "confidence" in ctdb else ""
        trigger = f" ({ctdb['trigger']})" if ctdb.get("trigger") else ""
        message = f" — {ctdb['message']}" if ctdb.get("message") else ""
        lines.append(f"CTDB: {ctdb['status']}{detail} via {ctdb['method']}{trigger}{message}")
        if ctdb.get("cue_layout") == "cyanrip_split_pregaps":
            lines.append("CTDB input: compatible copy of cyanrip CUE; original indexes preserved")
        elif ctdb.get("cue_layout") == "cd_extra_audio_session":
            lines.append("CTDB input: CD-Extra audio session; data track outside verification scope")
        elif ctdb.get("cue_layout") == "cd_extra_full_toc":
            lines.append("CTDB input: full physical CD-Extra TOC; audio checksums only")
            lines.append("CTDB physical TOC (LSN): " + ctdb["disc_toc"])
    else:
        lines.append("CTDB: not checked by OSCAR")
    if provenance["accuraterip_coverage"]:
        lines.append(f"AccurateRip coverage: {provenance['accuraterip_coverage']}")
    lines.extend(["Archive checks: FLAC decode, file SHA-256, STREAMINFO audio MD5 and CUE references.",
                  "", "[Track sources]"])
    final_hashes = {item["track"]: item["sha256"] for item in published_files or ()}
    for item in plan["tracks"]:
        number = item["number"]
        lines.append(f"Disc {disc:02d} / Track {number:02d} — {item['filename']}")
        if recovery:
            source = recovery["tracks"][number - 1]
            job_id = source["source_job_id"]
            origin = "diagnostic replacement" if job_id == recovery["diagnostic_job_id"] else "original full-disc rip"
            lines.extend([
                f"  Audio source: {origin}",
                f"  Source job: {job_id}",
                f"  Source file: {source['source_path']}",
                f"  Source and recovered-copy SHA-256: {source['source_sha256']}",
            ])
        else:
            lines.append(f"  Audio source: {plan['job_id']}/{item['source']}")
            if item.get("rip_sha256"):
                lines.append(f"  Source FLAC SHA-256: {item['rip_sha256']}")
        versions = provenance["track_verification"].get(number, {})
        for version in ("v1", "v2"):
            match = versions.get(version)
            if not match:
                lines.append(f"  AccurateRip {version}: not reported")
                continue
            confidence = match.get("confidence")
            suffix = f" (confidence {confidence})" if confidence is not None else ""
            lines.append(f"  AccurateRip {version}: {match['status'].replace('_', ' ')}{suffix}")
        if plan["include_cover"] and number not in final_hashes:
            lines.append(f"  Tagged staging FLAC SHA-256: {item['expected_sha256']}")
        else:
            lines.append(f"  Published FLAC SHA-256: {final_hashes.get(number, item['expected_sha256'])}")
    lines.extend(["", "[Archived evidence]", "album.cue — CUE with published file names",
                  "manifest.json — archive file hashes and provenance"])
    for item in plan["source_evidence"]:
        lines.append(f"ExtractionEvidence/{item['source']} — SHA-256: {item['sha256']}")
    return "\n".join(lines) + "\n"


def _source_evidence(job_id, *, include_ctdb=False):
    """Read-only inventory of the source CUE, logs and verification records."""
    job = verification._safe_job(job_id)
    audio = job / "audio"
    if audio.is_symlink() or not audio.is_dir():
        raise PublishError("Unsafe original audio folder")
    cues = list(audio.glob("*.cue"))
    if len(cues) != 1 or cues[0].is_symlink() or not cues[0].is_file():
        raise PublishError("Exactly one safe original CUE required")
    paths = [cues[0]]
    for folder in (job, audio):
        for path in sorted(folder.glob("*.log")):
            if path.is_symlink() or not path.is_file():
                raise PublishError("Unsafe original extraction log")
            paths.append(path)
    names = ["verification-report.json", "recovery-sources.json"]
    if include_ctdb:
        names.append(ctdb_verification.REPORT)
    for name in names:
        path = job / name
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise PublishError("Unsafe verification or recovery evidence")
        if path.is_file():
            paths.append(path)
    return [{"source": path.relative_to(job).as_posix(),
             "sha256": _hash(path), "size": path.stat().st_size}
            for path in paths]


def _copy_source_evidence(job_id, entries, temp):
    """Preserve CUE/log bytes and their hashes without altering staging."""
    job = verification._safe_job(job_id)
    folder = temp / "ExtractionEvidence"
    folder.mkdir(mode=0o700)
    output = []
    for entry in entries:
        relative = Path(entry["source"])
        if relative.is_absolute() or ".." in relative.parts or len(relative.parts) not in (1, 2):
            raise PublishError("Unsafe source evidence path")
        source = job / relative
        if source.is_symlink() or not source.is_file() or source.parent not in (job, job / "audio"):
            raise PublishError("Source evidence missing or unsafe")
        if _hash(source) != entry["sha256"] or source.stat().st_size != entry["size"]:
            raise PublishError("Source evidence changed since review")
        target = folder / relative
        target.parent.mkdir(exist_ok=True)
        with source.open("rb") as inp, target.open("xb") as out:
            shutil.copyfileobj(inp, out, 1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        if _hash(target) != entry["sha256"] or target.stat().st_size != entry["size"]:
            raise PublishError("Published evidence does not match original")
        output.append({"filename": target.relative_to(temp).as_posix(),
                       "original_staging_path": entry["source"],
                       "sha256": entry["sha256"], "size": entry["size"]})
    return output


def _embed_front(target, selected, raw):
    flac = FLAC(target)
    retained = [picture for picture in flac.pictures if picture.type != 3]
    flac.clear_pictures()
    for picture in retained:
        flac.add_picture(picture)
    front = Picture()
    front.type = 3
    front.mime = "image/jpeg"
    front.width, front.height = selected["width"], selected["height"]
    front.depth = 24
    front.data = raw
    flac.add_picture(front)
    flac.save()
    with target.open("rb") as output:
        os.fsync(output.fileno())


def _do_publish(plan, publish_id, *, allow_metadata_observations):
    job_id, copy_id, kind = plan["job_id"], plan["copy_id"], plan["kind"]
    new_plan = prepare(job_id, copy_id, kind, plan["profile_request"],
                       include_cover=plan["include_cover"])
    if new_plan["fingerprint"] != plan["fingerprint"]:
        raise PublishError("Archive preview changed; review and confirm a new preview")
    if new_plan["metadata_observations"] and not allow_metadata_observations:
        raise PublishError("Metadata review observations require explicit acknowledgement")
    root = archive_root()
    destination = root / new_plan["relative_directory"]
    parent = destination.parent
    if not parent.is_relative_to(root):
        raise PublishError("Unsafe destination")
    _check_directory(parent, root)
    lockfile = root / ".oscar-publish.lock"
    if lockfile.is_symlink():
        raise PublishError("Unsafe archive lock")
    # lock directory-level transitions across multiple OSCAR processes
    with lockfile.open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            if destination.exists() or destination.is_symlink():
                raise PublishError("Archive target already exists; refusing to overwrite")
            parent.mkdir(parents=True, exist_ok=True)
            if parent.is_symlink():
                raise PublishError("Unsafe archive parent")
            temp = parent / (".oscar-unpublished-" + publish_id)
            temp.mkdir(mode=0o700, exist_ok=False)
            source_job = verification._safe_job(job_id)
            prefix = "metadata-copy-" if kind == "original_tags" else "metadata-v2-"
            source_folder = source_job / (prefix + copy_id)
            artwork = new_plan["provenance"].get("artwork")
            cover = None
            if artwork:
                selected = cover_art.load(source_folder, new_plan["release_id"])
                if not selected or selected[0] != artwork:
                    raise PublishError("Cover selection changed; review the archive preview again")
                _, cover = selected
                with (temp / "folder.jpg").open("xb") as output:
                    output.write(cover)
                    output.flush()
                    os.fsync(output.fileno())
                artwork = {**artwork, "embedded_in_flacs": True}
            published = []
            for entry in new_plan["tracks"]:
                source = source_folder / entry["source"]
                if source.is_symlink() or not source.is_file():
                    raise PublishError("Tagged FLAC missing or unsafe during publish")
                if _hash(source) != entry["expected_sha256"]:
                    raise PublishError("Tagged source hash changed since verification")
                original = FLAC(str(source))
                if _streaminfo_md5_hex(original.info.md5_signature) != entry["audio_md5"]:
                    raise PublishError("Tagged source audio MD5 changed")
                target = temp / entry["filename"]
                with source.open("rb") as src, target.open("xb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                    dst.flush()
                    os.fsync(dst.fileno())
                if _hash(target) != entry["expected_sha256"]:
                    raise PublishError("Archive FLAC differs from tagged staging copy")
                if cover is not None:
                    _embed_front(target, artwork, cover)
                result = subprocess.run(["flac", "-t", "--silent", str(target)],
                                        capture_output=True, timeout=180, check=False)
                if result.returncode:
                    raise PublishError(f"FLAC decode failed for track {entry['number']}")
                archived = FLAC(str(target))
                if _streaminfo_md5_hex(archived.info.md5_signature) != entry["audio_md5"]:
                    raise PublishError("Archive FLAC audio MD5 differs")
                if cover is not None:
                    if archived.tags != original.tags:
                        raise PublishError("FLAC tags changed while embedding the front cover")
                    if [p.data for p in archived.pictures if p.type == 3] != [cover]:
                        raise PublishError("Embedded front cover differs from reviewed folder.jpg")
                published.append({"track": entry["number"], "filename": entry["filename"],
                                  "sha256": _hash(target) if cover is not None else entry["expected_sha256"],
                                  "streaminfo_audio_md5": entry["audio_md5"]})
            cue_path = temp / "album.cue"
            with cue_path.open("x", encoding="utf-8") as out:
                out.write(new_plan["cue"])
                out.flush()
                os.fsync(out.fileno())
            with cue_path.open(encoding="utf-8") as inp:
                cue_names = [m.group(1) for line in inp
                             if (m := archive_review._CUEFILE.match(line))]
            if cue_names != [x["filename"] for x in published]:
                raise PublishError("Published CUE filename order differs from actual files")
            if not all((temp / name).is_file() for name in cue_names):
                raise PublishError("Published CUE references missing FLAC files")
            evidence_copies = _copy_source_evidence(job_id, new_plan["source_evidence"], temp)
            release_match_status = plan.get("_release_match_status") or "EDITION_NOT_VERIFIED"
            with (temp / "SOURCES.txt").open("x", encoding="utf-8") as out:
                out.write(render_sources(new_plan, release_match_status, published_files=published))
                out.flush()
                os.fsync(out.fileno())
            manifest = {
                "status": "published_verified", "publish_id": publish_id,
                "job_id": job_id, "copy_id": copy_id,
                "release_id": new_plan["release_id"], "profile": new_plan["profile"],
                "release_match_status": release_match_status,
                "source_type": _source_type(new_plan),
                "provenance": new_plan["provenance"],
                "label_info": new_plan["album"].get("labels") or [],
                "disc_number": new_plan["disc_number"],
                "disc_total": new_plan["disc_total"],
                "source_preview_fingerprint": new_plan["original_preview_fingerprint"],
                "archive_plan_fingerprint": new_plan["fingerprint"],
                "metadata_observations": new_plan["metadata_observations"],
                "observations_acknowledged": bool(allow_metadata_observations),
                "files": published,
                "source_evidence": evidence_copies,
                "cue": {"filename": "album.cue", "sha256": _hash(cue_path),
                        "original_indexes_preserved_as_reported": True},
                "artwork": artwork,
                "note": "Archive files were copied without changing the original rip/tagged staging copies.",
            }
            with (temp / "manifest.json").open("x", encoding="utf-8") as out:
                json.dump(manifest, out, indent=2, ensure_ascii=False)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            # Refuse even an unexpectedly appearing target. Rename on the
            # same filesystem (under lock) only after full verification.
            if destination.exists() or destination.is_symlink():
                raise PublishError("Archive target appeared during staging; refusing overwrite")
            _rename_noreplace(temp, destination)
            # Directory is already visible now. Certain FUSE/shfs mounts
            # do not support fsync of a directory. Never misreport an
            # already-promoted archive as unpublished due solely to that
            # durability limitation. The individual copied files and
            # manifest have been fsynced before promotion.
            directory_sync = "ok"
            try:
                dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError as exc:
                directory_sync = "unavailable: " + str(exc)
            return {"status": "published_verified", "publish_id": publish_id,
                    "directory_sync": directory_sync,
                    "job_id": job_id, "copy_id": copy_id,
                    "relative_directory": new_plan["relative_directory"],
                    "file_count": len(published), "manifest_sha256": _hash(destination / "manifest.json"),
                    "artwork": artwork, "source_preserved": True}
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def start(job_id, copy_id, kind, profile, fingerprint, confirmation,
          *, acknowledge_observations=False, include_cover=False,
          approve_cover=False, release_match_status=None,
          reserved_publish_id=None):
    if confirmation != _CONFIRM:
        raise PublishError("Explicit archive publishing confirmation is required")
    if release_match_status not in {None, "INFERRED_OPERATOR_ACCEPTED",
                                    "INFERRED_NOT_PHYSICALLY_VERIFIED"}:
        raise PublishError("Unsupported edition provenance for archive publishing")
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise PublishError("A reviewed plan fingerprint is required")
    if include_cover and not approve_cover:
        raise PublishError("You must confirm the cover matches your physical edition")
    # Preflight before creating any output or background thread.
    plan = prepare(job_id, copy_id, kind, profile, include_cover=include_cover)
    if plan["fingerprint"] != fingerprint:
        raise PublishError("Archive preview changed; review again")
    if plan["output_exists"]:
        raise PublishError("Archive target already exists; refusing to overwrite")
    if plan["metadata_observations"] and not acknowledge_observations:
        raise PublishError("Review observations require acknowledgement")
    # Provenance is server-supplied; not an operator-editable MusicBrainz match.
    plan["_release_match_status"] = release_match_status
    if reserved_publish_id is not None and not _COPY_ID.fullmatch(reserved_publish_id):
        raise PublishError("Invalid reserved archive publication ID")
    publish_id = reserved_publish_id or uuid.uuid4().hex
    with _LOCK:
        if publish_id in _JOBS:
            raise PublishError("Publication ID already used by this process")
        if (job_id, copy_id) in _RUNNING:
            raise PublishError("This tagged copy is already being published")
        _RUNNING.add((job_id, copy_id))
        _JOBS[publish_id] = {"job_id": job_id, "copy_id": copy_id,
                             "publish_id": publish_id, "status": "running"}
    def work():
        try:
            result = _do_publish(plan, publish_id,
                                 allow_metadata_observations=acknowledge_observations)
            if result.get("status") == "published_verified":
                # Archive verification is independent of catalog SQLite success.
                # Index only the newly promoted directory, never the entire tree.
                try:
                    from oscar.collection_catalog import import_published
                    dest = archive_root() / result["relative_directory"]
                    imported = import_published(only_path=dest)
                    result["catalog"] = {
                        **imported,
                        "status": "indexed" if imported["indexed"] else "index_required",
                    }
                except Exception as catalog_exc:
                    result["catalog"] = {"status": "index_required",
                                         "error": f"{type(catalog_exc).__name__}: {catalog_exc}"[:350]}
        except Exception as exc:
            result = {"job_id": job_id, "copy_id": copy_id,
                      "publish_id": publish_id, "status": "failed",
                      "error": f"{type(exc).__name__}: {exc}"[:450],
                      "note": "Original sources are untouched. If a partial .oscar-unpublished-* folder exists, preserve it for inspection."}
        with _LOCK:
            _JOBS[publish_id] = result
            _RUNNING.discard((job_id, copy_id))
    threading.Thread(target=work, daemon=True,
                     name="oscar-publish-" + publish_id[:8]).start()
    return {"job_id": job_id, "copy_id": copy_id,
            "publish_id": publish_id, "status": "running"}


def status(job_id, publish_id):
    if not _COPY_ID.fullmatch(job_id) or not _COPY_ID.fullmatch(publish_id):
        raise PublishError("Invalid job or publication ID")
    with _LOCK:
        data = _JOBS.get(publish_id)
    if data and data["job_id"] == job_id:
        return data
    raise PublishError("Publication status unavailable; inspect archive manifest after restart")
