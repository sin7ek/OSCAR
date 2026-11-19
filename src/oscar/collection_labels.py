"""Exact MusicBrainz release label backfill for older published OSCAR archives.

Only fills missing labels when BOTH the stored MusicBrainz release UUID and
printed catalog agree with the live release's label-info. Never changes
archive files, FLAC tags or any manually entered label.
"""
import re
import urllib.parse
import urllib.request

from oscar import collection_catalog as catalog
from oscar import musicbrainz as mb
from oscar.mb_client import fetch_json

_UUID = re.compile(r"[a-fA-F0-9]{8}-(?:[a-fA-F0-9]{4}-){3}[a-fA-F0-9]{12}\Z")


class LabelEnrichmentError(RuntimeError):
    pass


def _norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def exact_release_labels(release_id, printed_catalog, *, opener=None):
    if not _UUID.fullmatch(release_id) or not _norm(printed_catalog):
        raise LabelEnrichmentError("Exact MusicBrainz release ID and physical catalog number required")
    url = ("https://musicbrainz.org/ws/2/release/" +
           urllib.parse.quote(release_id, safe="") + "?" +
           urllib.parse.urlencode({"inc":"labels", "fmt":"json"}))
    request = urllib.request.Request(url, headers={"User-Agent":mb._UA, "Accept":"application/json"})
    response = fetch_json(request, opener=opener, timeout=12, max_bytes=1500000)
    if response.get("id", "").lower() != release_id.lower():
        raise LabelEnrichmentError("MusicBrainz release UUID mismatch")
    names = set()
    for item in response.get("label-info") or []:
        if not isinstance(item, dict) or _norm(item.get("catalog-number")) != _norm(printed_catalog):
            continue
        label = (item.get("label") or {}).get("name")
        if isinstance(label, str) and label.strip():
            names.add(label.strip()[:250])
    return "; ".join(sorted(names))


def backfill_labels(*, lookup=exact_release_labels, max_items=20):
    if not 1 <= max_items <= 100:
        raise LabelEnrichmentError("Invalid batch size")
    with catalog._connect() as db:
        missing = db.execute("""SELECT archive_path,musicbrainz_release_id,catalog_number
          FROM archive_items WHERE label='' AND catalog_number<>'' ORDER BY archive_path LIMIT ?""",
                             (max_items,)).fetchall()
    updated = 0
    unresolved = 0
    for item in missing:
        try:
            label = lookup(item["musicbrainz_release_id"], item["catalog_number"])
        except (mb.MusicBrainzError, LabelEnrichmentError, OSError, ValueError):
            unresolved += 1
            continue
        if not label:
            unresolved += 1
            continue
        with catalog._connect() as db:
            changed = db.execute("""UPDATE archive_items
                SET label=?,label_provenance='musicbrainz_exact_release_catalog_match'
                WHERE archive_path=? AND musicbrainz_release_id=? AND catalog_number=?
                AND label=''""", (label, item["archive_path"],
                                   item["musicbrainz_release_id"], item["catalog_number"]))
            updated += changed.rowcount
    return {"labels_updated": updated, "unresolved": unresolved,
            "provider": "MusicBrainz exact release and physical catalog number",
            "archive_modified": False,
            "note": "Read-only MusicBrainz lookup; only previously empty local labels filled."}
