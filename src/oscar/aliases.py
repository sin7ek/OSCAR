"""Fetch trustworthy English entity aliases, preserving MusicBrainz native names.

English alias != machine translation. Never infer a translation from sort-name
or alter an entity's original name, IDs, or relationship provenance.
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from oscar import musicbrainz as mb

_ID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
_TYPES = {"artist", "work"}
_MAX_BYTES = 250_000


def choose_english_alias(aliases: list, original: str) -> dict:
    """Deterministic: current primary en alias, then current en alias."""
    candidates = []
    for alias in aliases or []:
        if not isinstance(alias, dict):
            continue
        if not str(alias.get("locale") or "").lower().startswith("en"):
            continue
        name = alias.get("name")
        if not isinstance(name, str) or not name.strip() or name.strip() == original:
            continue
        # Ended aliases are historic labels rather than current search names.
        if alias.get("ended") is True:
            continue
        candidates.append(alias)
    candidates.sort(key=lambda a: (
        0 if a.get("primary") is True else 1,
        0 if str(a.get("locale")).lower() == "en" else 1,
        a.get("name", "").casefold(),
    ))
    if not candidates:
        return {"english": None, "source": "unavailable", "locale": None}
    result = candidates[0]
    return {"english": result["name"], "source": "musicbrainz_alias",
            "locale": result.get("locale")}


def lookup_aliases(entity_type: str, entity_id: str, opener=None) -> dict:
    if entity_type not in _TYPES:
        raise mb.MusicBrainzError("Only artist and work aliases are supported")
    if not _ID.fullmatch(entity_id):
        raise mb.MusicBrainzError("Invalid MusicBrainz entity ID")
    url = "https://musicbrainz.org/ws/2/" + entity_type + "/" + urllib.parse.quote(entity_id, safe="") + "?inc=aliases&fmt=json"
    req = urllib.request.Request(url, headers={
        "User-Agent": mb._UA, "Accept": "application/json",
    })
    from oscar.mb_client import fetch_json
    data = fetch_json(req, opener=opener, timeout=12, max_bytes=_MAX_BYTES)
    if data.get("id", "").lower() != entity_id.lower():
        raise mb.MusicBrainzError("Unexpected entity ID in alias response")
    original = data.get("name") or data.get("title") or ""
    alias = choose_english_alias(data.get("aliases") or [], original)
    return {
        "entity_type": entity_type,
        "id": entity_id.lower(),
        "original": original,
        "english": alias["english"],
        "english_source": alias["source"],
        "english_locale": alias["locale"],
        "sort_name": data.get("sort-name") if entity_type == "artist" else None,
        "aliases": [
            {"name": a.get("name"), "locale": a.get("locale"), "primary": bool(a.get("primary"))}
            for a in data.get("aliases") or [] if isinstance(a, dict) and isinstance(a.get("name"), str)
        ],
        "requires_review": True,
    }
