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
import urllib.request
import uuid

from mutagen.flac import FLAC

from oscar import archive_review, verification
from oscar.archive_naming import safe_component
from oscar.metadata_staging import _COPY_ID, _streaminfo_md5_hex

_LOCK = threading.RLock()
_JOBS = {}
_RUNNING = set()
_MAX_COVER = 8 * 1024 * 1024
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
    if verification.report(job_id).get("status") != "checks_passed":
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
    cue = review["cue"]["archive_cue_proposal"]
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
            "tracks": records, "cue": cue, "include_cover": bool(include_cover),
            "metadata_observations": review["consistency"]["flags"],
            "original_preview_fingerprint": saved_preview.get("fingerprint"),
            "requires_explicit_review": True,
            "output_exists": (archive_root() / relative).exists(),
            "notes": [
                "Physical edition, CUE, cover and metadata exceptions require explicit operator review.",
                "This proposal does not rename, move or modify the original ripped or tagged staging files.",
                "Artwork is downloaded only if separately approved, and is never automatically embedded in FLACs.",
            ]}
    fingerprint_input = {k: v for k, v in plan.items()
                         if k not in {"output_exists", "notes"}}
    plan["fingerprint"] = hashlib.sha256(json.dumps(
        fingerprint_input, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")).hexdigest()
    return plan


def _cover(release_id, target, *, opener=None):
    """Fetch only front art for the exactly selected release, after approval."""
    url = f"https://coverartarchive.org/release/{release_id}/front"
    req = urllib.request.Request(url, headers={"User-Agent": "OSCAR/0.1 (reviewed archive artwork)"})
    with (opener or urllib.request.urlopen)(req, timeout=15) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > _MAX_COVER:
            raise PublishError("Cover art exceeds size limit")
        raw = response.read(_MAX_COVER + 1)
        if len(raw) > _MAX_COVER:
            raise PublishError("Cover art exceeds size limit")
    if raw.startswith(b"\xff\xd8\xff"):
        extension = "jpg"
    elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = "png"
    else:
        raise PublishError("Cover Art Archive did not return a supported JPEG/PNG")
    dest = target / f"cover.{extension}"
    with dest.open("xb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    return {"filename": dest.name, "sha256": _hash(dest), "source": url,
            "reviewed_physical_front": True}


def _do_publish(plan, publish_id, *, allow_metadata_observations, cover_download=None):
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
                result = subprocess.run(["flac", "-t", "--silent", str(target)],
                                        capture_output=True, timeout=180, check=False)
                if result.returncode:
                    raise PublishError(f"FLAC decode failed for track {entry['number']}")
                if _hash(target) != entry["expected_sha256"]:
                    raise PublishError("Archive FLAC differs from tagged staging copy")
                if _streaminfo_md5_hex(FLAC(str(target)).info.md5_signature) != entry["audio_md5"]:
                    raise PublishError("Archive FLAC audio MD5 differs")
                published.append({"track": entry["number"], "filename": entry["filename"],
                                  "sha256": entry["expected_sha256"],
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
            artwork = (cover_download or _cover)(new_plan["release_id"], temp) if new_plan["include_cover"] else None
            sources = (
                "OSCAR archived copy — original ripping evidence remains in staging\n"
                f"Staging rip job: {job_id}\nTagged staging copy: {copy_id}\n"
                f"MusicBrainz physical release: https://musicbrainz.org/release/{new_plan['release_id']}\n"
                f"Processing profile: {new_plan['profile']}\n"
                "AccurateRip confidence is from cyanrip's saved verification report, not a new independent lookup.\n"
                "The originally ripped CUE, logs and FLACs remain in their original staging folder.\n"
                "This folder contains reviewed copies, not new recordings or rewritten audio.\n"
            )
            (temp / "SOURCES.txt").write_text(sources, encoding="utf-8")
            manifest = {
                "status": "published_verified", "publish_id": publish_id,
                "job_id": job_id, "copy_id": copy_id,
                "release_id": new_plan["release_id"], "profile": new_plan["profile"],
                "disc_number": new_plan["disc_number"],
                "disc_total": new_plan["disc_total"],
                "source_preview_fingerprint": new_plan["original_preview_fingerprint"],
                "archive_plan_fingerprint": new_plan["fingerprint"],
                "metadata_observations": new_plan["metadata_observations"],
                "observations_acknowledged": bool(allow_metadata_observations),
                "files": published,
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
            dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            return {"status": "published_verified", "publish_id": publish_id,
                    "job_id": job_id, "copy_id": copy_id,
                    "relative_directory": new_plan["relative_directory"],
                    "file_count": len(published), "manifest_sha256": _hash(destination / "manifest.json"),
                    "artwork": artwork, "source_preserved": True}
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def start(job_id, copy_id, kind, profile, fingerprint, confirmation,
          *, acknowledge_observations=False, include_cover=False,
          approve_cover=False):
    if confirmation != _CONFIRM:
        raise PublishError("Explicit archive publishing confirmation is required")
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
    publish_id = uuid.uuid4().hex
    with _LOCK:
        if (job_id, copy_id) in _RUNNING:
            raise PublishError("This tagged copy is already being published")
        _RUNNING.add((job_id, copy_id))
        _JOBS[publish_id] = {"job_id": job_id, "copy_id": copy_id,
                             "publish_id": publish_id, "status": "running"}
    def work():
        try:
            result = _do_publish(plan, publish_id,
                                 allow_metadata_observations=acknowledge_observations)
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
