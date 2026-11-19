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
_SAFE_FLAC = re.compile(r"audio/(\d{2,3}) - [^/\\]+\.flac\Z")
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
    return {"number": position, "original_file": f"audio/{position:02d} - Unknown track.flac",
            "tags": tag, "composers": composers, "performers": performers,
            "works": works, "provenance": "musicbrainz_explicit_release_and_relationships"}


def build_preview(info, job_id, disc_id, track_count):
    if info.get("status") != "exact_disc_id_and_track_count" or len(info.get("matched_media") or []) != 1:
        raise MetadataError("Release does not have one exact Disc ID + track-count medium")
    medium = info["matched_media"][0]
    if not medium.get("disc_id_attached") or medium.get("track_count") != track_count:
        raise MetadataError("Exact medium match is required")
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
        "source": "MusicBrainz (exact matching Disc ID; edition selection requires human review)",
        "requires_review": True, "approved": False,
        "album": album, "disc_number": medium["position"],
        "disc_total": info["total_media"], "track_count": track_count,
        "tracks": [
            _track_data(t, i, track_count, medium["position"], info["total_media"], album)
            for i, t in enumerate(tracks, 1)
        ],
        "warnings": [
            "MusicBrainz Disc ID matches a medium but does not prove a physical edition; review catalog number and packaging.",
            "Classical composers, works and performers are tagged only where explicitly linked in MusicBrainz.",
            "Original names are preserved. English aliases and artwork are not automatically added in this first version.",
            "No source FLAC, CUE, original rip log, verification report, or archive is changed."
        ],
    }
    core = json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    output["fingerprint"] = hashlib.sha256(core).hexdigest()
    return output


def preview(job_id, release_id, *, lookup=lookup_release_medium):
    directory, state, report = _source(job_id)
    if not RELEASE_ID.fullmatch(release_id):
        raise MetadataError("Valid MusicBrainz release UUID required")
    disc_id = state.get("disc_id") or json.loads((directory / "plan.json").read_text())["disc_id"]
    count = report["expected_tracks"]
    info = lookup(release_id, disc_id, count)
    result = build_preview(info, job_id, disc_id, count)
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
                 flac_factory=None, runner=subprocess.run):
    if flac_factory is None:
        from mutagen.flac import FLAC
        flac_factory = FLAC
    source, state, _ = _source(job_id)
    plan = preview(job_id, release_id, lookup=lookup)
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
        source_audio_md5 = obj.info.md5_signature
        obj.clear()
        for key, value in track["tags"].items():
            if value:
                obj[key] = value if isinstance(value, list) else [str(value)]
        obj.save()
        tagged = flac_factory(str(target))
        if tagged.info.md5_signature != source_audio_md5:
            raise MetadataError("Audio STREAMINFO MD5 changed after tagging")
        check = runner(["flac", "-t", "--silent", str(target)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                       timeout=180, check=False)
        if check.returncode:
            raise MetadataError("Tagged FLAC failed audio integrity test: " + rel)
        manifest[str(target.relative_to(root))] = {
            "source_sha256": original_hashes[rel],
            "tagged_sha256": verification._digest(target),
            "audio_streaminfo_md5": source_audio_md5.hex(),
        }
    output = {
        "job_id": job_id, "copy_id": copy_id, "release_id": release_id,
        "preview_fingerprint": fingerprint, "status": "tagged_copy_ready_for_review",
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


def start_copy(job_id, release_id, fingerprint, confirmation):
    if confirmation != "COPY_TAGGED_TO_STAGING":
        raise MetadataError("Explicit tagged-copy confirmation required")
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        raise MetadataError("Invalid preview fingerprint")
    _source(job_id)
    if not RELEASE_ID.fullmatch(release_id):
        raise MetadataError("Invalid release ID")
    copy_id = uuid.uuid4().hex
    with _LOCK:
        if job_id in _RUNNING:
            raise MetadataError("A tagged-copy job for this rip is already running")
        _RUNNING.add(job_id)
        _JOBS[copy_id] = {"job_id": job_id, "copy_id": copy_id, "status": "running"}
    def work():
        try:
            result = _tagged_copy(job_id, release_id, fingerprint, copy_id)
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
