"""MusicBrainz Disc ID release candidate lookup (read-only, no auto-match).

Requests limited to the public MusicBrainz API with a descriptive User-Agent.
Network lookup is opt-in; release candidates always require human review.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
_UA = "OSCAR/0.1.0-alpha (https://github.com/sin7ek/OSCAR)"


class MusicBrainzError(RuntimeError):
    pass


def lookup_releases(disc_id: str, toc: str, opener=None) -> dict:
    """Return unranked release candidates; a Disc ID may match many editions."""
    import re
    if not re.fullmatch(r"[A-Za-z0-9._-]{28}", disc_id):
        raise MusicBrainzError("Invalid MusicBrainz Disc ID")
    if not re.fullmatch(r"[0-9]+(?: [0-9]+){3,102}", toc):
        raise MusicBrainzError("Invalid MusicBrainz TOC")
    url = ("https://musicbrainz.org/ws/2/discid/" +
           urllib.parse.quote(disc_id, safe="") + "?" +
           urllib.parse.urlencode({
               "toc": toc,
               "inc": "artist-credits+labels+release-groups",
               "cdstubs": "no",
               "fmt": "json",
           }))
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json",
    })
    from oscar.mb_client import fetch_json
    payload = fetch_json(req, opener=opener, timeout=12,
                         max_bytes=1_000_000, allow_404=True)
    if payload is None:
        return {"disc_id": disc_id, "releases": [], "status": "no_match"}
    releases = []
    for release in payload.get("releases", []):
        if not isinstance(release, dict) or not release.get("id"):
            continue
        artist = "".join(
            part.get("name", "") + part.get("joinphrase", "")
            for part in release.get("artist-credit", []) if isinstance(part, dict)
        )
        labels = []
        for item in release.get("label-info", []):
            if not isinstance(item, dict):
                continue
            label = item.get("label") or {}
            labels.append({
                "name": label.get("name"),
                "catalog_number": item.get("catalog-number"),
            })
        releases.append({
            "id": release["id"],
            "title": release.get("title"),
            "artist": artist,
            "date": release.get("date"),
            "country": release.get("country"),
            "barcode": release.get("barcode"),
            "labels": labels,
        })
    return {
        "disc_id": disc_id,
        "releases": releases,
        "status": "candidates" if releases else "no_match",
        "requires_review": True,
    }


def lookup_enabled() -> bool:
    return os.environ.get("OSCAR_ENABLE_MUSICBRAINZ") == "1"
