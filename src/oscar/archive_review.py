"""Read-only final archive review: metadata consistency, cover candidate and CUE.

Not a publisher. MusicBrainz recording and work are distinct identities. The
original ripped CUE, audio, and all tagged copies are never changed here.
"""
from collections import defaultdict
from pathlib import Path
import json
import re
import urllib.error
import urllib.request

from mutagen.flac import FLAC

from oscar import verification
from oscar.metadata_staging import _COPY_ID, _SAFE_FLAC
from oscar.boxsets import RELEASE_ID

_CUEFILE = re.compile(r'^\s*FILE\s+"([^"\r\n]+)"\s+WAVE\s*$', re.I)
_TRACK = re.compile(r'^\s*TRACK\s+(\d{2,3})\s+AUDIO\s*$', re.I)
_MAX = 150


class ReviewError(RuntimeError):
    pass


def _json_file(folder, name):
    path = folder / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 3_000_000:
        raise ReviewError("Missing or unsafe review evidence: " + name)
    return json.loads(path.read_text(encoding="utf-8"))


def _load(job_id, copy_id, kind):
    if not _COPY_ID.fullmatch(job_id) or not _COPY_ID.fullmatch(copy_id):
        raise ReviewError("Invalid job/copy ID")
    if kind not in {"original_tags", "classical_v2"}:
        raise ReviewError("Unsupported tagged copy type")
    root = verification._safe_job(job_id)
    prefix = "metadata-copy-" if kind == "original_tags" else "metadata-v2-"
    folder = root / (prefix + copy_id)
    if folder.is_symlink() or not folder.is_dir():
        raise ReviewError("Tagged staging copy not found")
    preview_name = "metadata-preview.json" if kind == "original_tags" else "classical-v2-preview.json"
    manifest_name = "metadata-manifest.json" if kind == "original_tags" else "classical-v2-manifest.json"
    preview = _json_file(folder, preview_name)
    manifest = _json_file(folder, manifest_name)
    done = "tagged_copy_ready_for_review" if kind == "original_tags" else "classical_v2_ready_for_review"
    if (manifest.get("status") != done or manifest.get("copy_id") != copy_id
            or manifest.get("job_id") != job_id or preview.get("job_id") != job_id
            or manifest.get("preview_fingerprint") != preview.get("fingerprint")):
        raise ReviewError("Staging copy has incomplete or mismatched evidence")
    files = manifest.get("files") or {}
    tracks = preview.get("tracks") or []
    if not 1 <= len(tracks) == len(files) <= _MAX:
        raise ReviewError("Staging manifest track count mismatch")
    if not isinstance(files, dict):
        raise ReviewError("Bad staging manifest")
    info = []
    seen = set()
    for t in tracks:
        relative = t.get("original_file")
        if not isinstance(relative, str) or not _SAFE_FLAC.fullmatch(relative):
            raise ReviewError("Unexpected tagged FLAC path")
        if relative in seen or relative not in files:
            raise ReviewError("Duplicate or missing tagged source")
        seen.add(relative)
        tagged_path = folder / relative
        if tagged_path.is_symlink() or not tagged_path.is_file():
            raise ReviewError("Tagged FLAC missing")
        flac = FLAC(str(tagged_path))
        tags = {key.upper(): list(values) for key, values in flac.items()}
        info.append({
            "number": t["number"],
            "file": relative,
            "title": (tags.get("TITLE") or [""])[0],
            "artist": (tags.get("ARTIST") or [""])[0],
            "composer": tags.get("COMPOSER", []),
            "conductor": tags.get("CONDUCTOR", []),
            "documented_performers": tags.get("PERFORMER", []),
            "recording_id": (tags.get("MUSICBRAINZ_TRACKID") or [""])[0],
            "work_ids": tags.get("MUSICBRAINZ_WORKID", []),
            "work_names": tags.get("WORK", []),
            "release_section": (tags.get("RELEASE_SECTION") or [""])[0],
            "length_seconds": round(flac.info.length, 3),
            "musicbrainz_length_ms": t.get("length_ms"),  # only newer previews
        })
    if seen != set(files):
        raise ReviewError("Extra manifest entries")
    if [t["number"] for t in info] != list(range(1, len(info) + 1)):
        raise ReviewError("Track order mismatch")
    return root, folder, preview, manifest, info



def resolve_music_profile(tracks, kind, requested="auto"):
    """Select a conservative CUE/review policy; never guess specific genres.

    Classical v2 is explicit evidence. For older generic tagged copies,
    widespread documented conductor credits indicate a classical-performance
    presentation. Otherwise use the ordinary credited-artist policy. The
    result is a *processing profile*, not a factual MusicBrainz genre tag.
    """
    if requested not in {"auto", "standard", "classical"}:
        raise ReviewError("Unknown music processing profile")
    if requested != "auto":
        return {"name": requested, "source": "operator_review_override",
                "requires_review": True}
    if kind == "classical_v2":
        return {"name": "classical", "source": "existing_classical_v2_copy",
                "requires_review": False}
    conductor_count = sum(bool(t.get("conductor")) for t in tracks)
    if tracks and conductor_count > len(tracks) / 2:
        return {"name": "classical", "source": "majority_documented_conductors",
                "requires_review": True}
    return {"name": "standard", "source": "generic_tagged_copy_no_classical_evidence",
            "requires_review": True}


def _variant_title(title):
    """Only recognize an explicit reprise suffix, not unrelated work variants."""
    return re.sub(r"\s*\(reprise\)\s*$", "", str(title or "").casefold()).strip()


def _normal_reprise_pair(titles):
    if len(titles) != 2:
        return False
    original, reprise = sorted(titles, key=lambda t: "(reprise)" in t.casefold())
    return ("(reprise)" in reprise.casefold()
            and _variant_title(original) == _variant_title(reprise))

def consistency(tracks, profile="classical"):
    """Flag ambiguity for review; never declare two recordings identical by work."""
    flags = []
    by_work = defaultdict(list)
    by_recording = defaultdict(list)
    if profile not in {"standard", "classical"}:
        raise ReviewError("Unknown music processing profile")
    classical_with_work_links = profile == "classical" and any(t.get("work_ids") for t in tracks)
    for t in tracks:
        n = t["number"]
        if not t["title"]:
            flags.append({"severity": "review", "code": "missing_title",
                          "tracks": [n], "message": "Track title is missing"})
        if not t["recording_id"]:
            flags.append({"severity": "review", "code": "missing_recording_id",
                          "tracks": [n], "message": "MusicBrainz Recording ID is missing"})
        if not t["artist"]:
            flags.append({"severity": "review", "code": "missing_artist",
                          "tracks": [n], "message": "Track artist credit is missing"})
        if classical_with_work_links and not t["work_ids"]:
            flags.append({"severity": "review", "code": "missing_classical_work_link",
                          "tracks": [n], "message": "No MusicBrainz Work relationship is documented on this track while other tracks on the release have linked works. This may be legitimate; do not infer a work from the title."})
        for work in set(t["work_ids"]):
            by_work[work].append(t)
        if t["recording_id"]:
            by_recording[t["recording_id"]].append(t)
        mb_ms = t.get("musicbrainz_length_ms")
        if isinstance(mb_ms, int) and mb_ms > 0:
            delta = abs(t["length_seconds"] - mb_ms / 1000)
            if delta > 10:
                flags.append({"severity": "review", "code": "duration_mismatch",
                              "tracks": [n], "message": f"MusicBrainz vs actual FLAC: {delta:.1f}s difference"})
    for work, members in by_work.items():
        if len(members) < 2:
            continue
        titles = {m["title"].casefold().strip() for m in members}
        recordings = {m["recording_id"] for m in members if m["recording_id"]}
        if len(titles) > 1 and not (profile == "standard"
                                     and _normal_reprise_pair([m["title"] for m in members])):
            flags.append({
                "severity": "review", "code": "same_work_different_titles",
                "tracks": [x["number"] for x in members], "work_id": work,
                "message": "Multiple distinct track titles link to one work; may be legitimate repeats, sections or arrangements. Check edition/recordings; do not infer wrong work.",
                "recording_ids_differ": len(recordings) > 1,
            })
    for recording, members in by_recording.items():
        if len(members) > 1:
            lengths = [m["length_seconds"] for m in members]
            if max(lengths) - min(lengths) > 10:
                flags.append({
                    "severity": "review", "code": "same_recording_different_durations",
                    "tracks": [x["number"] for x in members], "recording_id": recording,
                    "message": "Same MusicBrainz recording appears with notably different durations; review for cuts or mixed tracks.",
                })
    return {
        "status": "review_recommended" if flags else "no_detected_conflicts",
        "review_count": len(flags), "flags": flags,
        "notes": [
            "Same Work ID does not mean two FLACs contain the same recording.",
            "A MusicBrainz Recording ID represents a recording, while a Work ID represents a composition.",
            "Duration differences only flagged where an MB track length is present; no AcoustID or audio fingerprint run.",
            "Absence of flags is not proof of correct musicological relationships; reviewer still approves the physical edition.",
        ],
    }


def _escape_cue(value):
    return str(value or "").replace("\r", " ").replace("\n", " ").replace('"', "'")[:500]



def _documented_cue_performer(track, profile="classical"):
    """Select documented performing artists, never a composer just by ARTIST.

    FLAC PERFORMER values are OSCAR's explicitly sourced MusicBrainz recording
    relationships and include role suffixes for provenance. In a CUE sheet,
    use the names as a display credit; the full tagged roles remain available.
    """
    if profile == "standard":
        # ARTIST represents the release's primary track artist credit,
        # while PERFORMER carries detailed MusicBrainz session credits.
        return (track.get("artist") or "").strip() or None
    names = []
    for value in track.get("documented_performers") or []:
        if not isinstance(value, str):
            continue
        name = re.sub(r"\s+\((?:conductor|performer|instrument|vocal|orchestra|performing orchestra|choir|chorus master|concertmaster|solo|voice actor)\)$",
                      "", value.strip(), flags=re.I).strip()
        if name and name not in names:
            names.append(name)
    if names:
        return "; ".join(names)
    # In pop/dance, ARTIST can legitimately name the credited performing artist.
    # But do not put the composer's name into PERFORMER on a classical track.
    composer = track.get("composer") or []
    artist = (track.get("artist") or "").strip()
    if composer or track.get("work_ids"):
        return None
    return artist or None


def _album_cue_performer(tracks, album_artist, profile="classical"):
    """Prefer a documented common conductor where one is credited."""
    if profile == "standard":
        return album_artist or None
    conductors = [
        {str(name) for name in t.get("conductor") or [] if name}
        for t in tracks
    ]
    if conductors and all(conductors):
        common = set.intersection(*conductors)
        if common:
            return "; ".join(sorted(common))
    # Release artist credit is not always performing artist credit (classical).
    # Avoid using composer-heavy artist credit as an invented performer.
    if any(t.get("composer") or t.get("documented_performers") for t in tracks):
        return None
    return album_artist or None

def cue_preview(root, tracks, album_title, album_artist, *, profile="classical"):
    raw_audio = root / "audio"
    if not raw_audio.is_dir() or raw_audio.is_symlink():
        raise ReviewError("Original rip audio directory missing")
    cues = [p for p in raw_audio.glob("*.cue") if p.is_file() and not p.is_symlink()]
    if len(cues) != 1:
        return {"status": "needs_review", "reason": "Exactly one original CUE required; no synthetic INDEX or PREGAP generated"}
    original = cues[0].read_text(encoding="utf-8-sig", errors="replace")
    lines = original.splitlines()
    referenced = [_CUEFILE.match(line.strip()) for line in lines]
    names = [m.group(1) for m in referenced if m]
    expected = [Path(t["file"]).name for t in tracks]
    if names != expected:
        return {"status": "needs_review", "reason": "Original CUE FILE order differs from tagged FLACs"}
    markers = [int(m.group(1)) for line in lines if (m := _TRACK.match(line))]
    if markers != list(range(1, len(tracks) + 1)):
        return {"status": "needs_review", "reason": "Original CUE TRACK numbering mismatched"}
    # Keep original time indexes / pregaps exactly as captured; edit display text only.
    album_cue_performer = _album_cue_performer(tracks, album_artist, profile)
    out = []
    inside = None
    global_title = global_performer = False
    emitted = set()
    for line in lines:
        marker = _TRACK.match(line)
        if marker:
            inside = int(marker.group(1))
            out.append(line)
            out.append(f'    TITLE "{_escape_cue(tracks[inside - 1]["title"])}"')
            performer = _documented_cue_performer(tracks[inside - 1], profile)
            if performer:
                out.append(f'    PERFORMER "{_escape_cue(performer)}"')
            emitted.add(inside)
            continue
        label = line.strip().upper()
        if inside is None:
            if label.startswith("TITLE "):
                if not global_title:
                    out.append(f'TITLE "{_escape_cue(album_title)}"')
                    global_title = True
                continue
            if label.startswith("PERFORMER "):
                if not global_performer and album_cue_performer:
                    out.append(f'PERFORMER "{_escape_cue(album_cue_performer)}"')
                    global_performer = True
                continue
        else:
            if label.startswith(("TITLE ", "PERFORMER ")):
                continue
        out.append(line)
    prefix = []
    if not global_title:
        prefix.append(f'TITLE "{_escape_cue(album_title)}"')
    if not global_performer and album_cue_performer:
        prefix.append(f'PERFORMER "{_escape_cue(album_cue_performer)}"')
    if set(emitted) != set(range(1, len(tracks) + 1)):
        raise ReviewError("Unable to preserve CUE TRACK structure")
    # A second proposal describes target filenames for a future publisher.
    # These files do not exist yet. It is NOT a playable/archive CUE until the
    # reviewed publisher actually creates exactly these target names.
    from oscar.archive_naming import safe_component
    proposed = [f'{t["number"]:02d} - {safe_component(t["title"])}.flac' for t in tracks]
    renamed = []
    index = 0
    for line in prefix + out:
        if _CUEFILE.match(line.strip()):
            renamed.append('FILE "' + _escape_cue(proposed[index]) + '" WAVE')
            index += 1
        else:
            renamed.append(line)
    if index != len(proposed) or len(set(proposed)) != len(proposed):
        raise ReviewError("Unable to build distinct archive CUE filename proposal")
    return {
        "status": "preview_requires_review",
        "text": "\n".join(prefix + out) + "\n",
        "archive_cue_proposal": "\n".join(renamed) + "\n",
        "proposed_filenames": proposed,
        "archive_cue_requires_renaming": True,
        "original_cue": cues[0].name,
        "track_count": len(tracks),
        "preserves_original_indices": True,
        "performer_provenance": ("Primary MusicBrainz track-artist credit; detailed session performers retained in FLAC tags." if profile == "standard" else
                                 "Explicit recorded performer/conductor relationships where available; otherwise non-composer track credit. Uncertain credits omitted."),
        "music_profile": profile,
        "note": "Both CUE proposals preserve the original INDEX/PREGAP lines without independent validation. The first points to current staged files; the second names proposed future archive files that do not exist yet. Review before publication.",
    }


def cover_preview(release_id, *, opener=None):
    if not RELEASE_ID.fullmatch(release_id):
        raise ReviewError("Invalid MusicBrainz release ID")
    url = "https://coverartarchive.org/release/" + release_id
    request = urllib.request.Request(url, headers={"User-Agent": "OSCAR/0.1 (local archive preview)",
                                                  "Accept": "application/json"})
    handler = opener or urllib.request.urlopen
    try:
        with handler(request, timeout=8) as response:
            raw = response.read(300_001)
            if len(raw) > 300_000:
                raise ReviewError("Cover Art Archive metadata too large")
        data = json.loads(raw)
        fronts = [x for x in data.get("images", []) if x.get("front") is True]
        return {
            "status": "candidate_found" if fronts else "no_front",
            "thumbnail_url": f"https://coverartarchive.org/release/{release_id}/front-250" if fronts else None,
            "large_url": f"https://coverartarchive.org/release/{release_id}/front-500" if fronts else None,
            "source": url,
            "needs_physical_cover_review": True,
            "note": "Candidate front cover only; compare against actual CD before embedding or archiving.",
        }
    except urllib.error.HTTPError as exc:
        return {"status": "not_found" if exc.code == 404 else "unavailable",
                "note": f"Cover Art Archive returned HTTP {exc.code}; no cover inferred."}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return {"status": "unavailable", "note": "Cover Art Archive could not be reached; no cover inferred."}


def review(job_id, copy_id, kind="classical_v2", *, profile="auto", artwork=True, cover_lookup=cover_preview):
    root, folder, preview, manifest, tracks = _load(job_id, copy_id, kind)
    original = _json_file(root / ("metadata-copy-" +
                          (copy_id if kind == "original_tags" else preview["source_copy_id"])),
                          "metadata-preview.json")
    album = original.get("album") or {}
    release_id = original.get("release_id")
    if not RELEASE_ID.fullmatch(str(release_id or "")):
        raise ReviewError("Missing reviewed physical MusicBrainz release")
    known_lengths = {t.get("number"): t.get("length_ms") for t in original.get("tracks") or []}
    for track in tracks:
        if track.get("musicbrainz_length_ms") is None:
            track["musicbrainz_length_ms"] = known_lengths.get(track["number"])
    processing = resolve_music_profile(tracks, kind, requested=profile)
    metadata_review = consistency(tracks, profile=processing["name"])
    cue = cue_preview(root, tracks, album.get("title"), album.get("artist"),
                      profile=processing["name"])
    cover = cover_lookup(release_id) if artwork else {"status": "not_checked"}
    return {
        "job_id": job_id, "copy_id": copy_id, "kind": kind,
        "release_id": release_id, "album": album,
        "music_profile": processing,
        "tracks": tracks, "consistency": metadata_review,
        "cover_art": cover, "cue": cue,
        "publication_ready": False,
        "notes": [
            "Read-only evaluation. Archive publication and deletion are disabled.",
            "Work/recording metadata discrepancies do not automatically mean the audio is inaccurate.",
            "CUE is a preview only; no original or new CUE has been written.",
        ],
    }
