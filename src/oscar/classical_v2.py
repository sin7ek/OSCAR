"""Classical Metadata v2: explicitly reviewed disc sections and work identity.

Existing tagged copies are never modified. Review selections are applied only
to NEW isolated FLAC copies, with audio integrity verification.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from oscar import metadata_staging as staging, verification
from oscar.alias_cache import cache_path

_LOCK = threading.Lock()
_JOBS = {}
_RUNNING = set()
_UUID = re.compile(r"[a-f0-9]{32}\Z")
_MAX_SECTION = 120


class ClassicalError(RuntimeError):
    pass


def _alias(entity_type, entity_id):
    """Cached English alias only: no unbounded MusicBrainz calls in preview."""
    from oscar.aliases import _ID
    if not isinstance(entity_id, str) or not _ID.fullmatch(entity_id):
        return None
    path = cache_path()
    if not path.is_file() or path.is_symlink():
        return None
    import sqlite3
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2) as db:
            row = db.execute(
                "SELECT response_json FROM aliases WHERE entity_type=? AND entity_id=?",
                (entity_type, entity_id.lower())).fetchone()
        if row:
            payload = json.loads(row[0])
            return payload.get("english") or None
    except (sqlite3.Error, ValueError, OSError):
        return None
    return None


def _validated_source(job_id, copy_id):
    if not _UUID.fullmatch(job_id) or not _UUID.fullmatch(copy_id):
        raise ClassicalError("Invalid staging or tagged copy ID")
    inspection = staging.inspect_copy(job_id, copy_id)
    if inspection.get("status") != "tags_match_preview":
        raise ClassicalError("Source tagged copy must pass its metadata inspection")
    folder = verification._safe_job(job_id) / ("metadata-copy-" + copy_id)
    for name in ("metadata-preview.json", "metadata-manifest.json"):
        if (folder / name).is_symlink():
            raise ClassicalError("Unsafe source metadata")
    plan = json.loads((folder / "metadata-preview.json").read_text(encoding="utf-8"))
    if len(plan.get("tracks") or []) != inspection["track_count"]:
        raise ClassicalError("Invalid source track manifest")
    return folder, plan, inspection


def validate_sections(sections, total):
    """A named section must have an explicit, nonoverlapping track range."""
    if not isinstance(sections, list) or not 1 <= len(sections) <= 30:
        raise ClassicalError("Supply one to thirty reviewed CD sections")
    ranges = {}
    normalized = []
    for item in sections:
        if not isinstance(item, dict):
            raise ClassicalError("Invalid reviewed section")
        start, end, name = item.get("start"), item.get("end"), item.get("name")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            raise ClassicalError("Section track boundaries must be integers")
        if not (1 <= start <= end <= total):
            raise ClassicalError("Section range outside the CD")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > _MAX_SECTION:
            raise ClassicalError("Section name is empty or too long")
        for i in range(start, end + 1):
            if i in ranges:
                raise ClassicalError("Overlapping CD sections")
            ranges[i] = name.strip()
        normalized.append({"start": start, "end": end, "name": name.strip(),
                           "source": "operator_review_of_physical_release"})
    if set(ranges) != set(range(1, total + 1)):
        raise ClassicalError("Reviewed CD sections must cover every track")
    return normalized, ranges


def _aliases_for_track(entry):
    result = {}
    composers = entry.get("composers") or []
    for composer in composers:
        label = _alias("artist", composer.get("artist_id"))
        if label:
            result.setdefault("COMPOSER_EN", []).append(label)
    performers = entry.get("performers") or []
    for artist in performers:
        label = _alias("artist", artist.get("artist_id"))
        if not label:
            continue
        if artist.get("role") == "conductor":
            result.setdefault("CONDUCTOR_EN", []).append(label)
        elif artist.get("role") in {"orchestra", "performing orchestra"}:
            result.setdefault("ORCHESTRA_EN", []).append(label)
    works = entry.get("works") or []
    for work in works:
        label = _alias("work", work.get("id"))
        if label:
            result.setdefault("WORK_EN", []).append(label)
        for parent in work.get("parents") or []:
            label = _alias("work", parent.get("id"))
            if label:
                result.setdefault("WORK_PARENT_EN", []).append(label)
    return {key: list(dict.fromkeys(values)) for key, values in result.items()}


def create_preview(job_id, copy_id, sections, movements=None):
    folder, source, inspection = _validated_source(job_id, copy_id)
    total = inspection["track_count"]
    checked_sections, by_track = validate_sections(sections, total)
    if movements is None:
        movements = {}
    if not isinstance(movements, dict) or len(movements) > total:
        raise ClassicalError("Invalid movement overrides")
    explicit_movements = {}
    for key, value in movements.items():
        try:
            n = int(key)
        except (TypeError, ValueError):
            raise ClassicalError("Invalid movement track number")
        if not str(key).isdigit() or not 1 <= n <= total or not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ClassicalError("Movement requires a reviewed nonempty title and track number")
        explicit_movements[n] = value.strip()
    tracks = []
    for entry in source["tracks"]:
        n = entry["number"]
        tags = dict(entry["tags"])
        tags.pop("GROUPING", None)
        tags["RELEASE_SECTION"] = by_track[n]
        # Distinguish the linked work from its parent, regardless of the
        # division of the physical CD into suites/sections.
        parents = [p for w in entry.get("works") or []
                   for p in w.get("parents") or [] if p.get("title")]
        if parents:
            tags["WORK_PARENT"] = list(dict.fromkeys(p["title"] for p in parents))
            ids = [p["id"] for p in parents if p.get("id")]
            if ids:
                tags["MUSICBRAINZ_WORKPARENTID"] = list(dict.fromkeys(ids))
        else:
            tags.pop("WORK_PARENT", None)
            tags.pop("MUSICBRAINZ_WORKPARENTID", None)
        tags.pop("MOVEMENT", None)
        if n in explicit_movements:
            tags["MOVEMENT"] = explicit_movements[n]
        # Supplemental aliases never replace the source-language fields.
        tags.update(_aliases_for_track(entry))
        tracks.append({
            "number": n, "original_file": entry["original_file"],
            "title": tags.get("TITLE"),
            "release_section": by_track[n],
            "work": tags.get("WORK", []),
            "work_parent": tags.get("WORK_PARENT", []),
            "movement": explicit_movements.get(n),
            "aliases": {k: v for k, v in tags.items() if k.endswith("_EN")},
            "tags": tags,
        })
    result = {
        "schema": "oscar.classical_metadata_v2",
        "job_id": job_id, "source_copy_id": copy_id,
        "release_id": source["release_id"],
        "source_preview_fingerprint": source.get("fingerprint"),
        "sections": checked_sections, "tracks": tracks, "track_count": total,
        "status": "requires_review",
        "warnings": [
            "RELEASE_SECTION is a reviewed physical-CD section; WORK_PARENT is MusicBrainz composition hierarchy.",
            "MOVEMENT is written only when explicitly supplied by the reviewer, never inferred from punctuation or numbering.",
            "English aliases come from the local MusicBrainz alias cache and supplement original names; absent aliases remain absent.",
            "WORK retains all explicitly linked work titles and IDs; source tags and original FLACs remain untouched.",
        ],
    }
    canonical = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    result["fingerprint"] = hashlib.sha256(canonical).hexdigest()
    return result


def _do_copy(preview, copy_id):
    from mutagen.flac import FLAC
    job_id = preview["job_id"]
    source_id = preview["source_copy_id"]
    source_folder, _, inspection = _validated_source(job_id, source_id)
    root = verification._safe_job(job_id)
    output_folder = root / ("metadata-v2-" + copy_id)
    if output_folder.exists() or output_folder.is_symlink():
        raise ClassicalError("Metadata v2 copy already exists")
    output_folder.mkdir(mode=0o700)
    audio = output_folder / "audio"
    audio.mkdir(mode=0o700)
    copied = {}
    source_manifest_file = source_folder / "metadata-manifest.json"
    if source_manifest_file.is_symlink():
        raise ClassicalError("Unsafe source manifest")
    source_manifest = json.loads(source_manifest_file.read_text(encoding="utf-8"))["files"]
    for entry in preview["tracks"]:
        relative = entry["original_file"]
        if not staging._SAFE_FLAC.fullmatch(relative):
            raise ClassicalError("Invalid source file reference")
        src = source_folder / relative
        if src.is_symlink() or not src.is_file():
            raise ClassicalError("Missing or unsafe tagged source file")
        expected_hash = source_manifest[relative]["tagged_sha256"]
        if verification._digest(src) != expected_hash:
            raise ClassicalError("Source tagged FLAC changed before copying")
        dest = audio / src.name
        with src.open("rb") as fin, dest.open("xb") as fout:
            shutil.copyfileobj(fin, fout, length=1024 * 1024)
        if verification._digest(dest) != expected_hash:
            raise ClassicalError("Copy does not match the verified tagged source")
        tags = FLAC(str(dest))
        audio_md5 = staging._streaminfo_md5_hex(tags.info.md5_signature)
        if audio_md5 != source_manifest[relative]["audio_streaminfo_md5"]:
            raise ClassicalError("Source FLAC audio MD5 changed since tagging")
        tags.clear()
        for k, v in entry["tags"].items():
            if v:
                tags[k] = v if isinstance(v, list) else [str(v)]
        tags.save()
        again = FLAC(str(dest))
        if staging._streaminfo_md5_hex(again.info.md5_signature) != audio_md5:
            raise ClassicalError("Tagged v2 copy changed audio STREAMINFO MD5")
        decoded = subprocess.run(["flac", "-t", "--silent", str(dest)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                 timeout=180, check=False)
        if decoded.returncode:
            raise ClassicalError("Tagged v2 FLAC failed decoding")
        copied["audio/" + dest.name] = {
            "tagged_sha256": verification._digest(dest),
            "source_sha256": verification._digest(src),
            "audio_streaminfo_md5": audio_md5,
        }
    result = {
        "schema": "oscar.classical_metadata_v2",
        "job_id": job_id, "copy_id": copy_id, "source_copy_id": source_id,
        "status": "classical_v2_ready_for_review",
        "count": len(copied), "files": copied,
        "preview_fingerprint": preview["fingerprint"],
        "note": "New staging copies only. Original rip and previous tagged copies unchanged. Not archived.",
    }
    for name, data in (("classical-v2-preview.json", preview),
                       ("classical-v2-manifest.json", result)):
        with (output_folder / name).open("x", encoding="utf-8") as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
            out.write("\n")
    return result


def start_copy(preview, confirmation):
    if confirmation != "COPY_CLASSICAL_V2_TO_STAGING":
        raise ClassicalError("Explicit Classical v2 staging confirmation required")
    if preview.get("schema") != "oscar.classical_metadata_v2":
        raise ClassicalError("Invalid classical metadata preview")
    canonical = {k: v for k, v in preview.items() if k != "fingerprint"}
    actual = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()
    if actual != preview.get("fingerprint"):
        raise ClassicalError("Tampered metadata preview")
    job_id, source_id = preview["job_id"], preview["source_copy_id"]
    # Always rebuild and compare the review fingerprint against current source
    # and cache; do not trust submitted tags from a browser.
    movements = {str(t["number"]): t["movement"] for t in preview["tracks"] if t.get("movement")}
    rebuilt = create_preview(job_id, source_id, preview["sections"], movements)
    if rebuilt["fingerprint"] != preview["fingerprint"]:
        raise ClassicalError("Classical preview changed; review it again")
    copy_id = uuid.uuid4().hex
    with _LOCK:
        if job_id in _RUNNING:
            raise ClassicalError("A metadata copy is already running for this job")
        _RUNNING.add(job_id)
        _JOBS[copy_id] = {"job_id": job_id, "copy_id": copy_id, "status": "running"}
    def worker():
        try:
            report = _do_copy(rebuilt, copy_id)
        except Exception as exc:
            report = {"job_id": job_id, "copy_id": copy_id, "status": "failed",
                      "error": f"{type(exc).__name__}: {exc}"[:350],
                      "note": "Partial v2 staging directory, if any, must not be treated as complete."}
        finally:
            with _LOCK:
                _JOBS[copy_id] = report
                _RUNNING.discard(job_id)
    threading.Thread(target=worker, name="oscar-classical-v2-" + copy_id[:8], daemon=True).start()
    return {"job_id": job_id, "copy_id": copy_id, "status": "running"}


def copy_status(job_id, copy_id):
    if not _UUID.fullmatch(job_id) or not _UUID.fullmatch(copy_id):
        raise ClassicalError("Invalid job or copy ID")
    with _LOCK:
        record = _JOBS.get(copy_id)
    if record and record.get("job_id") == job_id:
        return record
    path = verification._safe_job(job_id) / ("metadata-v2-" + copy_id) / "classical-v2-manifest.json"
    if path.is_file() and not path.is_symlink():
        return json.loads(path.read_text(encoding="utf-8"))
    raise ClassicalError("Classical v2 copy not found or unfinished")
