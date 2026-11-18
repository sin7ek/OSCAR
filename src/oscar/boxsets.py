"""Read-only release medium/tracklist identification.

Never infer the disc number from number of tracks alone: a matching Disc ID
must be explicitly attached to a medium on the selected MusicBrainz release.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from oscar import musicbrainz as mb
from oscar.classical import recording_roles
from oscar.work_hierarchy import group_tracks, work_details

RELEASE_ID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\Z")
DISC_ID = re.compile(r"[A-Za-z0-9._-]{28}\Z")


def _artist_credit(parts):
    if not isinstance(parts, list):
        return ""
    return "".join(
        part.get("name", "") + part.get("joinphrase", "")
        if isinstance(part, dict) else str(part)
        for part in parts
    )


def parse_release_media(payload: dict, disc_id: str, track_count: int) -> dict:
    """Extract exact medium matches while retaining mismatches for review."""
    media = payload.get("media") or []
    results = []
    for medium in media:
        discs = medium.get("discs") or []
        linked = any(isinstance(d, dict) and d.get("id") == disc_id for d in discs)
        tracks = medium.get("tracks") or []
        reported_count = medium.get("track-count", len(tracks))
        if not isinstance(reported_count, int):
            reported_count = len(tracks)
        results.append({
            "position": medium.get("position"),
            "title": medium.get("title"),
            "format": medium.get("format"),
            "medium_id": medium.get("id"),
            "disc_id_attached": linked,
            "track_count": reported_count,
            "track_count_matches": reported_count == track_count,
            "tracks": [
                {
                    "position": t.get("position"),
                    "number": t.get("number"),
                    "title": t.get("title") or (t.get("recording") or {}).get("title"),
                    "artist_credit": _artist_credit(t.get("artist-credit") or (t.get("recording") or {}).get("artist-credit", [])),
                    **recording_roles(t.get("recording") or {}),
                    "work_details": work_details(t.get("recording") or {}),
                    "recording_id": (t.get("recording") or {}).get("id"),
                    "length_ms": t.get("length"),
                }
                for t in tracks if isinstance(t, dict)
            ],
        })
        results[-1]["work_groups"] = group_tracks(results[-1]["tracks"])
    matched = [m for m in results if m["disc_id_attached"]]
    fully_matching = [m for m in matched if m["track_count_matches"]]
    if len(fully_matching) == 1:
        status = "exact_disc_id_and_track_count"
    elif matched:
        status = "review_disc_id_or_count_ambiguity"
    else:
        status = "no_exact_medium_match"
    return {
        "release_id": payload.get("id"),
        "release_title": payload.get("title"),
        "disc_id": disc_id,
        "total_media": len(media),
        "status": status,
        "requires_review": True,
        "matched_media": matched,
        "all_media_summary": [
            {
                "position": m["position"], "title": m["title"],
                "track_count": m["track_count"], "disc_id_attached": m["disc_id_attached"],
            }
            for m in results
        ],
    }


def lookup_release_medium(release_id: str, disc_id: str, track_count: int, opener=None) -> dict:
    if not RELEASE_ID.fullmatch(release_id):
        raise mb.MusicBrainzError("Invalid release MBID")
    if not DISC_ID.fullmatch(disc_id):
        raise mb.MusicBrainzError("Invalid Disc ID")
    if not isinstance(track_count, int) or not 1 <= track_count <= 99:
        raise mb.MusicBrainzError("Invalid track count")
    url = ("https://musicbrainz.org/ws/2/release/" +
           urllib.parse.quote(release_id, safe="") + "?" +
           urllib.parse.urlencode({"inc": "recordings+artist-credits+discids+recording-level-rels+work-rels+work-level-rels+artist-rels", "fmt": "json"}))
    request = urllib.request.Request(url, headers={
        "User-Agent": mb._UA, "Accept": "application/json",
    })
    from oscar.mb_client import fetch_json
    payload = fetch_json(request, opener=opener, timeout=18, max_bytes=8_000_000)
    if payload.get("id", "").lower() != release_id.lower():
        raise mb.MusicBrainzError("Unexpected release ID in response")
    return parse_release_media(payload, disc_id, track_count)
