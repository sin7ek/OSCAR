"""Reviewed MusicBrainz metadata preview and non-destructive tagged staging copies.

No archive writes and no automatic edition selection. Every physical release
must match the saved Disc ID and all tracks. The original FLAC/CUE/logs stay
untouched. Changes to metadata require a fresh preview fingerprint.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from oscar import ripping, verification
from oscar.boxsets import RELEASE_ID, lookup_release_medium
from oscar.musicbrainz import MusicBrainzError

_LOCK = threading.Lock()
_JOBS = {}
_RUNNING = set()
_SAFE_FLAC = re.compile(r"audio/((?:[1-9]\d{0,2}|0[1-9]\d?|00[1-9])) - [^/\\]+\.flac\Z")
_COPY_ID = re.compile(r"[a-f0-9]{32}\Z")


class MetadataError(RuntimeError):
    pass


def _source(job_id):
    directory = verification._safe_job(job_id)
    state = verification._load_job(directory, job_id)
    report = verification.report(job_id)
    if report.get("status") != "checks_passed" or report.get("job_id") != job_id:
        raise MetadataError("All staged audio checks must pass before preparing tagged copies")
    manifest = state.get("files_sha256") or {}
    if len(manifest) != report.get("expected_tracks") or not manifest:
        raise MetadataError("Staged track manifest does not match verification report")
    if len(report.get("tracks") or []) != len(manifest) or not all(
            t.get("checks_passed") for t in report["tracks"]):
        raise MetadataError("Per-track verification is incomplete")
    return directory, state, report


def _streaminfo_md5_hex(value):
    """Normalize Mutagen's 128-bit integer STREAMINFO MD5 to 32 hex digits."""
    if isinstance(value, int):
        if not 0 <= value < (1 << 128):
            raise MetadataError("Invalid FLAC STREAMINFO MD5 integer")
        return format(value, "032x")
    if isinstance(value, (bytes, bytearray)) and len(value) == 16:
        return bytes(value).hex()
    raise MetadataError("Unexpected FLAC STREAMINFO MD5 representation")


def _one_string(value):
    return str(value or "").strip()[:500]


def _track_data(track, position, total, disc_number, disc_total, album):
    composers = track.get("composers") or []
    performers = track.get("performers") or []
    works = track.get("work_details") or []
    tag = {
        "ALBUM": album["title"],
        "ALBUMARTIST": album["artist"],
        "ARTIST": _one_string(track.get("artist_credit")) or album["artist"],
        "TITLE": _one_string(track.get("title")),
        "TRACKNUMBER": str(position),
        "TRACKTOTAL": str(total),
        "DISCNUMBER": str(disc_number),
        "DISCTOTAL": str(disc_total),
        "RIPPED_WITH": "Ripped with OSCAR - Preserve Every Note.",
        "RIPPER_URL": "https://github.com/sin7ek/OSCAR",
        "MUSICBRAINZ_ALBUMID": album["musicbrainz_release_id"],
        "MUSICBRAINZ_DISCID": album["musicbrainz_disc_id"],
    }
    if album.get("date"):
        tag["DATE"] = album["date"]
    if album.get("barcode"):
        tag["BARCODE"] = album["barcode"]
    if album.get("catalog_numbers"):
        tag["CATALOGNUMBER"] = album["catalog_numbers"]
    if track.get("recording_id"):
        tag["MUSICBRAINZ_TRACKID"] = track["recording_id"]
    if track.get("release_track_id"):
        tag["MUSICBRAINZ_RELEASETRACKID"] = track["release_track_id"]
    if composers:
        tag["COMPOSER"] = list(dict.fromkeys(c["name"] for c in composers if c.get("name")))
        ids = [c["artist_id"] for c in composers if c.get("artist_id")]
        if ids:
            tag["MUSICBRAINZ_COMPOSERARTISTID"] = list(dict.fromkeys(ids))
    roles = [
        ("conductor", "CONDUCTOR"),
        ("orchestra", "ORCHESTRA"),
        ("performing orchestra", "ORCHESTRA"),
    ]
    for role, field in roles:
        names = [p["name"] for p in performers if p.get("role") == role and p.get("name")]
        if names:
            tag[field] = list(dict.fromkeys((tag.get(field) or []) + names))
    if performers:
        tag["PERFORMER"] = list(dict.fromkeys(
            p["name"] + (" (" + p["role"] + ")" if p.get("role") else "")
            for p in performers if p.get("name")))
    if works:
        tag["MUSICBRAINZ_WORKID"] = list(dict.fromkeys(w["id"] for w in works if w.get("id")))
        tag["WORK"] = list(dict.fromkeys(w["title"] for w in works if w.get("title")))
        parent = [p["title"] for w in works for p in (w.get("parents") or []) if p.get("title")]
        if parent:
            tag["GROUPING"] = list(dict.fromkeys(parent))
    return {"number": position, "length_ms": track.get("length_ms"), "original_file": f"audio/{position:02d} - Unknown track.flac",
            "tags": tag, "composers": composers, "performers": performers,
            "works": works, "provenance": "musicbrainz_explicit_release_and_relationships"}


def build_preview(info, job_id, disc_id, track_count, *, operator_accepted=False):
    exact = (info.get("status") == "exact_disc_id_and_track_count"
             and len(info.get("matched_media") or []) == 1)
    if exact:
        medium = info["matched_media"][0]
        if not medium.get("disc_id_attached") or medium.get("track_count") != track_count:
            raise MetadataError("Exact medium match is required")
    elif (operator_accepted and info.get("status") == "no_exact_medium_match"
          and info.get("total_media") == 1):
        # Only a saved Semi Automatic operator acceptance may use this path.
        # A multi-disc boxset is NEVER identified using track count alone.
        media = info.get("all_media") or []
        matches = [m for m in media if m.get("track_count") == track_count
                   and m.get("format") == "CD"
                   and m.get("position") == 1 and not m.get("disc_id_attached")]
        if len(media) != 1 or len(matches) != 1:
            raise MetadataError("Operator-accepted release has no unique compatible CD medium")
        medium = matches[0]
    else:
        raise MetadataError("Release does not have one exact Disc ID + track-count medium")
    tracks = medium.get("tracks") or []
    if len(tracks) != track_count:
        raise MetadataError("MusicBrainz release has an incomplete or missing tracklist")
    positions = [t.get("position") for t in tracks]
    if positions != list(range(1, track_count + 1)):
        raise MetadataError("MusicBrainz track positions are incomplete or out of order")
    title = _one_string(info.get("release_title"))
    artist = _one_string(info.get("album_artist"))
    if not title or not artist or not all(_one_string(t.get("title")) for t in tracks):
        raise MetadataError("Album, album artist or track title missing; review MusicBrainz release")
    date = _one_string(info.get("date"))
    labels = [x for x in info.get("label_info") or [] if x.get("name") or x.get("catalog_number")]
    catalog = list(dict.fromkeys(x["catalog_number"] for x in labels if x.get("catalog_number")))
    album = {"title": title, "artist": artist, "date": date, "country": info.get("country"),
             "barcode": info.get("barcode"), "labels": labels, "catalog_numbers": catalog,
             "musicbrainz_release_id": info["release_id"],
             "musicbrainz_disc_id": disc_id}
    if not isinstance(medium.get("position"), int) or not 1 <= medium["position"] <= info["total_media"]:
        raise MetadataError("Missing physical disc position")
    output = {
        "job_id": job_id, "release_id": info["release_id"],
        "source": ("MusicBrainz (exact Disc ID + track count; physical edition requires review)"
                   if exact else
                   "MusicBrainz (operator-accepted release; NO attached matching Disc ID)"),
        "medium_match_method": ("exact_disc_id_and_track_count" if exact
                                else "single_cd_operator_accepted_track_count_only"),
        "requires_review": True, "approved": False,
        "album": album, "disc_number": medium["position"],
        "disc_total": info["total_media"], "track_count": track_count,
        "tracks": [
            _track_data(t, i, track_count, medium["position"], info["total_media"], album)
            for i, t in enumerate(tracks, 1)
        ],
        "warnings": [
            ("MusicBrainz Disc ID matches a medium but does not prove a physical edition; review catalog number and packaging."
             if exact else
             "CAUTION: No matching Disc ID is attached to this MusicBrainz medium. This is an operator-accepted INFERRED edition, not Disc ID or physical-edition verification; confirm the physical catalog, track titles, ordering and durations before publishing."),
            "Classical composers, works and performers are tagged only where explicitly linked in MusicBrainz.",
            "Original names are preserved. English aliases and artwork are not automatically added in this first version.",
            "No source FLAC, CUE, original rip log, verification report, or archive is changed."
        ],
    }
    core = json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    output["fingerprint"] = hashlib.sha256(core).hexdigest()
    return output


def preview(job_id, release_id, *, lookup=lookup_release_medium, operator_accepted=False):
    directory, state, report = _source(job_id)
    if not RELEASE_ID.fullmatch(release_id):
        raise MetadataError("Valid MusicBrainz release UUID required")
    disc_id = state.get("disc_id") or json.loads((directory / "plan.json").read_text())["disc_id"]
    count = report["expected_tracks"]
    info = lookup(release_id, disc_id, count)
    result = build_preview(info, job_id, disc_id, count,
                           operator_accepted=operator_accepted)
    # Actual original files may have non-unknown names in future cyanrip versions:
    # map track numbers to the manifest instead of assuming names.
    manifest = state.get("files_sha256") or {}
    indexed = {}
    for name in manifest:
        match = _SAFE_FLAC.fullmatch(name)
        if not match:
            raise MetadataError("Unexpected source FLAC name")
        number = int(match.group(1))
        if number in indexed:
            raise MetadataError("Duplicate numbered source FLAC")
        indexed[number] = name
    if set(indexed) != set(range(1, count + 1)):
        raise MetadataError("Incomplete source FLAC manifest")
    for track in result["tracks"]:
        track["original_file"] = indexed[track["number"]]
    # fingerprint also covers the actual source filenames
    result.pop("fingerprint")
    core = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    result["fingerprint"] = hashlib.sha256(core).hexdigest()
    return result


def _tagged_copy(job_id, release_id, fingerprint, copy_id, *, lookup=lookup_release_medium,
                 flac_factory=None, runner=subprocess.run, identification_status=None):
    if flac_factory is None:
        from mutagen.flac import FLAC
        flac_factory = FLAC
    source, state, _ = _source(job_id)
    plan = preview(job_id, release_id, lookup=lookup,
                   operator_accepted=(identification_status == "INFERRED_OPERATOR_ACCEPTED"))
    if plan["fingerprint"] != fingerprint:
        raise MetadataError("Metadata preview changed; review the current MusicBrainz data again")
    root = source / ("metadata-copy-" + copy_id)
    if root.exists() or root.is_symlink():
        raise MetadataError("Tagged staging copy already exists; refusing to overwrite")
    root.mkdir(mode=0o700)
    audio = root / "audio"
    audio.mkdir(mode=0o700)
    manifest = {}
    original_hashes = state["files_sha256"]
    for track in plan["tracks"]:
        rel = track["original_file"]
        src = verification._file_readonly(source, rel)
        if verification._digest(src) != original_hashes[rel]:
            raise MetadataError("Source SHA-256 changed since rip: " + rel)
        target = audio / Path(rel).name
        # 'xb' prevents clobbering even in races, no symlink/hardlink to originals.
        with src.open("rb") as inp, target.open("xb") as out:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
        obj = flac_factory(str(target))
        source_audio_md5 = _streaminfo_md5_hex(obj.info.md5_signature)
        obj.clear()
        for key, value in track["tags"].items():
            if value:
                obj[key] = value if isinstance(value, list) else [str(value)]
        obj.save()
        tagged = flac_factory(str(target))
        if _streaminfo_md5_hex(tagged.info.md5_signature) != source_audio_md5:
            raise MetadataError("Audio STREAMINFO MD5 changed after tagging")
        check = runner(["flac", "-t", "--silent", str(target)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       timeout=180, check=False)
        if check.returncode:
            raise MetadataError("Tagged FLAC failed audio integrity test: " + rel)
        manifest[str(target.relative_to(root))] = {
            "source_sha256": original_hashes[rel],
            "tagged_sha256": verification._digest(target),
            "audio_streaminfo_md5": source_audio_md5,
        }
    output = {
        "job_id": job_id, "copy_id": copy_id, "release_id": release_id,
        "preview_fingerprint": fingerprint, "status": "tagged_copy_ready_for_review",
        "identification_status": identification_status or "UNSPECIFIED_REVIEW_REQUIRED",
        "files": manifest, "count": len(manifest),
        "note": "Staging copies only. No archive publication or cleanup; original files remain untouched.",
    }
    with (root / "metadata-manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with (root / "metadata-preview.json").open("x", encoding="utf-8") as handle:
        json.dump(plan, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return output


def start_copy(job_id, release_id, fingerprint, confirmation, *,
               reserved_copy_id=None, identification_status=None):
    if confirmation != "COPY_TAGGED_TO_STAGING":
        raise MetadataError("Explicit tagged-copy confirmation required")
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise MetadataError("Invalid preview fingerprint")
    _source(job_id)
    if not RELEASE_ID.fullmatch(release_id):
        raise MetadataError("Invalid release ID")
    if reserved_copy_id is not None and not _COPY_ID.fullmatch(reserved_copy_id):
        raise MetadataError("Invalid reserved metadata copy ID")
    if identification_status not in {None, "INFERRED_NOT_PHYSICALLY_VERIFIED",
                                     "INFERRED_OPERATOR_ACCEPTED"}:
        raise MetadataError("Invalid inference provenance")
    copy_id = reserved_copy_id or uuid.uuid4().hex
    with _LOCK:
        if job_id in _RUNNING or copy_id in _JOBS:
            raise MetadataError("A tagged-copy job for this rip is already running")
        # A reserved ID must never overwrite an earlier copy or partial write.
        candidate = verification._safe_job(job_id) / ("metadata-copy-" + copy_id)
        if candidate.exists() or candidate.is_symlink():
            raise MetadataError("Reserved tagged-copy path already exists")
        _RUNNING.add(job_id)
        _JOBS[copy_id] = {"job_id": job_id, "copy_id": copy_id, "status": "running"}
    def work():
        try:
            result = _tagged_copy(job_id, release_id, fingerprint, copy_id,
                                  identification_status=identification_status)
        except Exception as exc:
            result = {"job_id": job_id, "copy_id": copy_id, "status": "failed",
                      "error": f"{type(exc).__name__}: {exc}"[:350],
                      "note": "No originals were modified. Do not use partial metadata-copy folder."}
        finally:
            with _LOCK:
                _JOBS[copy_id] = result
                _RUNNING.discard(job_id)
    threading.Thread(target=work, name="oscar-metadata-copy-" + copy_id[:8],
                     daemon=True).start()
    return {"job_id": job_id, "copy_id": copy_id, "status": "running"}


def copy_status(job_id, copy_id):
    if not _COPY_ID.fullmatch(copy_id):
        raise MetadataError("Invalid metadata copy ID")
    with _LOCK:
        result = _JOBS.get(copy_id)
    if result and result.get("job_id") == job_id:
        return result
    source = verification._safe_job(job_id)
    path = source / ("metadata-copy-" + copy_id) / "metadata-manifest.json"
    if path.is_file() and not path.is_symlink():
        return json.loads(path.read_text(encoding="utf-8"))
    raise MetadataError("Tagged copy not found or unfinished")


def inspect_copy(job_id, copy_id):
    """Read back actual Vorbis comments from a completed, new tagged staging copy.

    No MusicBrainz/network call, and no source modifications. The saved
    metadata-preview.json is the source of *expected* fields.
    """
    from mutagen.flac import FLAC
    if not _COPY_ID.fullmatch(copy_id):
        raise MetadataError("Invalid metadata copy ID")
    source = verification._safe_job(job_id)
    folder = source / ("metadata-copy-" + copy_id)
    if folder.is_symlink() or not folder.is_dir():
        raise MetadataError("Tagged copy not found")
    def json_file(name):
        target = folder / name
        if target.is_symlink() or not target.is_file():
            raise MetadataError("Missing or unsafe copy metadata file")
        return json.loads(target.read_text(encoding="utf-8"))
    manifest = json_file("metadata-manifest.json")
    expected = json_file("metadata-preview.json")
    if (manifest.get("job_id") != job_id or manifest.get("copy_id") != copy_id
            or manifest.get("status") != "tagged_copy_ready_for_review"):
        raise MetadataError("Only a completed tagged copy can be inspected")
    if (expected.get("job_id") != job_id
            or expected.get("fingerprint") != manifest.get("preview_fingerprint")
            or expected.get("release_id") != manifest.get("release_id")):
        raise MetadataError("Stored preview does not match copy manifest")
    tracks = expected.get("tracks") or []
    recorded = manifest.get("files") or {}
    if not isinstance(recorded, dict) or not (1 <= len(tracks) == len(recorded) <= 150):
        raise MetadataError("Copy track manifest is incomplete")
    audio_folder = folder / "audio"
    if audio_folder.is_symlink() or not audio_folder.is_dir():
        raise MetadataError("Unsafe copy audio directory")
    results = []
    used = set()
    for entry in tracks:
        original = entry.get("original_file")
        if not isinstance(original, str) or not _SAFE_FLAC.fullmatch(original):
            raise MetadataError("Unexpected original FLAC name in saved preview")
        relative = original
        if relative in used:
            raise MetadataError("Duplicate track in saved preview")
        used.add(relative)
        info = recorded.get(relative)
        if not isinstance(info, dict):
            raise MetadataError("Copy manifest lacks a reviewed track")
        path = audio_folder / Path(relative).name
        if path.is_symlink() or not path.is_file() or path.parent.resolve() != audio_folder.resolve():
            raise MetadataError("Missing or unsafe tagged FLAC")
        actual = FLAC(str(path))
        actual_tags = {k.upper(): list(v) for k, v in actual.items()}
        planned = entry.get("tags") or {}
        expected_tags = {str(k).upper(): (v if isinstance(v, list) else [str(v)])
                         for k, v in planned.items() if v}
        differences = {}
        for key, values in expected_tags.items():
            if actual_tags.get(key) != values:
                differences[key] = {"expected": values, "actual": actual_tags.get(key, [])}
        # Preserve and display additional tags rather than silently marking
        # a successful match when surprising/unreviewed tags are present.
        for key, values in actual_tags.items():
            if key not in expected_tags:
                differences[key] = {"expected": [], "actual": values}
        current_hash = verification._digest(path)
        hash_matches = current_hash == info.get("tagged_sha256")
        audio_md5 = _streaminfo_md5_hex(actual.info.md5_signature)
        audio_matches = audio_md5 == info.get("audio_streaminfo_md5")
        results.append({
            "track": entry["number"], "file": relative,
            "tags": actual_tags, "expected_tags": expected_tags,
            "differences": differences, "tags_match": not differences,
            "sha256_matches": hash_matches, "audio_streaminfo_md5_matches": audio_matches,
            "status": "matches_preview" if not differences and hash_matches and audio_matches else "review_required"
        })
    if set(recorded) != used:
        raise MetadataError("Copy manifest contains extra or missing tracks")
    return {
        "job_id": job_id, "copy_id": copy_id,
        "release_id": manifest["release_id"],
        "album": expected.get("album", {}),
        "track_count": len(results),
        "status": "tags_match_preview" if all(t["status"] == "matches_preview" for t in results)
                  else "review_required",
        "tracks": results,
        "notes": [
            "Tags were read directly from the completed tagged FLAC copies using Mutagen.",
            "SHA-256 was recalculated against the tagged-copy manifest, and STREAMINFO MD5 was compared.",
            "Matching the saved preview does not certify MusicBrainz editorial correctness, cover art, or independent AccurateRip/CTDB.",
            "Original FLACs, CUE, rip logs and archive were not modified."
        ]
    }
