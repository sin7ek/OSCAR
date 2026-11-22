"""MusicBrainz Disc ID release candidate lookup (read-only, no auto-match).

Requests limited to the public MusicBrainz API with a descriptive User-Agent.
Network lookup is opt-in; release candidates always require human review.
"""
import json
import os
import re
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


def _quoted_search_value(value):
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _search(entity, expression, opener):
    url = f"https://musicbrainz.org/ws/2/{entity}/?" + urllib.parse.urlencode({
        "query": expression, "limit": "25", "fmt": "json",
    })
    request = urllib.request.Request(url, headers={
        "User-Agent": _UA,
        "Accept": "application/json",
    })
    from oscar.mb_client import fetch_json
    return fetch_json(request, opener=opener, timeout=12, max_bytes=1_000_000)


def search_release_candidates(*, catalog_number=None, title=None, barcode=None,
                              matrix_runout=None, opener=None):
    """Find physical-release *candidates* without a Disc ID lookup.

    Catalog, barcode, title and matrix searches are separate evidence sources. Query
    tokens are quoted as Lucene string literals, not raw search syntax.
    No search result implies a Disc ID attachment or physical-edition match.
    """
    from oscar.pressing_evidence import observed_matrix

    fields = {"catno": catalog_number, "release": title, "barcode": barcode,
              "matrix_runout": matrix_runout}
    supplied = [(field, value) for field, value in fields.items() if value is not None]
    if len(supplied) != 1:
        raise MusicBrainzError("Enter one catalog number, barcode, release title or matrix/runout")
    field, value = supplied[0]
    try:
        query_value = observed_matrix(value)
    except ValueError as exc:
        raise MusicBrainzError(str(exc)) from exc
    if not query_value or (field != "matrix_runout" and len(value.strip()) > 100):
        raise MusicBrainzError("Invalid search value")
    if field == "barcode" and not re.fullmatch(r"[0-9]{8,14}", query_value):
        raise MusicBrainzError("Enter the barcode as 8 to 14 digits")

    if field == "matrix_runout":
        return _search_matrix_annotations(query_value, opener)

    payload = _search("release", f"{field}:{_quoted_search_value(query_value)}", opener)
    releases = []
    for item in payload.get("releases") or []:
        if not isinstance(item, dict) or not re.fullmatch(
            r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}",
            str(item.get("id") or ""),
        ):
            continue
        labels = [{"name": (x.get("label") or {}).get("name"),
                   "catalog_number": x.get("catalog-number")}
                  for x in item.get("label-info") or [] if isinstance(x, dict)]
        artist = "".join(
            x.get("name", "") + x.get("joinphrase", "")
            if isinstance(x, dict) else str(x)
            for x in item.get("artist-credit") or []
        )
        releases.append({
            "id": item["id"], "title": item.get("title"), "artist": artist,
            "date": item.get("date"), "country": item.get("country"),
            "barcode": item.get("barcode"), "labels": labels,
            "search_score": item.get("score"),
            "provenance": f"musicbrainz_search_{field}",
        })
    return {
        "status": "candidates" if releases else "no_match",
        "query_kind": field, "query_value": query_value,
        "releases": releases, "requires_review": True,
        "disc_id_compared": False, "physical_edition_approved": False,
        "note": "Search candidates are not Disc ID or track-count matches. Inspect the exact release medium and physical evidence separately before tagging.",
    }


def _search_matrix_annotations(matrix, opener):
    """Find release annotations containing the entered text as a phrase."""
    payload = _search("annotation", f"type:release AND text:{_quoted_search_value(matrix)}", opener)
    releases = {}
    for item in payload.get("annotations") or []:
        if not isinstance(item, dict) or item.get("type") != "release":
            continue
        release_id = item.get("entity")
        if not isinstance(release_id, str) or not re.fullmatch(
                r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", release_id):
            continue
        releases.setdefault(release_id, {
            "id": release_id, "title": item.get("name"), "labels": [],
            "provenance": "musicbrainz_release_annotation",
            "annotation": str(item.get("text") or "")[:1500],
        })
    return {
        "status": "candidates" if releases else "no_match",
        "query_kind": "matrix_runout", "query_value": matrix,
        "releases": list(releases.values()), "requires_review": True,
        "disc_id_compared": False, "physical_edition_approved": False,
        "note": ("Only searchable MusicBrainz release annotations are covered. "
                 "Try a distinctive part of the matrix such as a mastering code. "
                 "An annotation match is a candidate for manual physical review."),
    }


def assess_disc_candidates(result: dict, catalog_number: str | None = None) -> dict:
    """Read-only, risk-based physical edition guidance; never auto-approve.

    A unique Disc ID candidate permits automatic candidate inspection, but it
    does not prove the catalog/pressing: an unlinked edition can still exist.
    """
    import copy
    import re

    output = copy.deepcopy(result)
    candidates = output.get("releases") or []
    if not isinstance(candidates, list):
        raise MusicBrainzError("Invalid release candidates")
    if not isinstance(catalog_number, (str, type(None))):
        raise MusicBrainzError("Invalid catalog number")
    raw = (catalog_number or "").strip()
    if len(raw) > 100 or any(ord(ch) < 32 for ch in raw):
        raise MusicBrainzError("Invalid catalog number")
    def norm(value):
        return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())
    needle = norm(raw)
    if raw and not needle:
        raise MusicBrainzError("Invalid catalog number")
    matches = 0
    for item in candidates:
        labels = item.get("labels") or []
        match = bool(needle and any(
            norm(label.get("catalog_number")) == needle
            for label in labels if isinstance(label, dict)
        ))
        item["printed_catalog_matches"] = match if raw else None
        if match:
            matches += 1
    if not candidates:
        level = "no_disc_candidates"
        guidance = "No releases are linked to this Disc ID. Search independently by the printed catalog number or title."
    elif raw and matches == 0:
        level = "catalog_conflict"
        guidance = "No Disc ID candidate matches the printed catalog number. Search independently by catalog number; do not select a different edition."
    elif raw and matches > 1:
        level = "ambiguous_catalog"
        guidance = "Several releases share the catalog number. Check barcode, artwork and other physical evidence."
    elif raw:
        level = "catalog_candidate"
        guidance = "Catalog matches one candidate. Continue with medium/tracklist comparison, then physical-edition review."
    elif len(candidates) > 1:
        level = "ambiguous_disc_id"
        guidance = "Several releases share this Disc ID. Enter the printed catalog number to narrow the candidates."
    else:
        level = "single_candidate"
        guidance = "One Disc ID candidate: inspect its medium automatically. Confirm physical edition evidence before final tagging or publication."
    output["edition_gate"] = {
        "status": level, "candidate_count": len(candidates),
        "printed_catalog": raw or None, "catalog_match_count": matches,
        "catalog_prompt_recommended": level in {"ambiguous_disc_id", "ambiguous_catalog", "catalog_conflict", "no_disc_candidates"},
        "can_inspect_automatically": level in {"single_candidate", "catalog_candidate"},
        "requires_review": True, "physical_edition_approved": False,
        "message": guidance,
    }
    return output
