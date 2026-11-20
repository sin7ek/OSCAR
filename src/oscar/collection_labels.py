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


def reconcile_applied_archive_labels():
    """Explicitly synchronize only sourced Collection labels after completed revisions.

    Earlier versions retained a partial label (e.g. Epic) when an approved
    archive revision wrote the full FLAC set (Daylight; Epic). Only operator-
    approved, journal-completed changes with verified actual FLAC tags may
    update existing catalog rows; manually edited or unknown provenance wins.
    """
    import json
    from oscar import archive_metadata_scan as scan, archive_revision

    allowed = {
        "", "archive_manifest_label_info", "archived_flac_label_tag",
        "musicbrainz_exact_release_catalog_match", "archive_revision_approved_labels",
    }
    updated = 0
    skipped_manual = 0
    verified = 0
    with archive_revision._db() as db:
        operations = db.execute(
            "SELECT operation_id,dest_path,proposal_fingerprints "
            "FROM archive_revision_operations WHERE status='completed' "
            "ORDER BY started_at"
        ).fetchall()
    for op in operations:
        with archive_revision._db() as db:
            rows = []
            for fp in json.loads(op["proposal_fingerprints"]):
                row = db.execute(
                    "SELECT field,status,after_json FROM metadata_proposals "
                    "WHERE fingerprint=?", (fp,)
                ).fetchone()
                if row and row["field"] == "LABEL" and row["status"] == "applied":
                    rows.append(row)
            if len(rows) != 1:
                continue
            names = json.loads(rows[0]["after_json"])
            if not isinstance(names, list) or not names or not all(
                isinstance(name, str) and name.strip() for name in names
            ):
                continue
            target = "; ".join(names)
            indexed = db.execute(
                "SELECT label,label_provenance FROM archive_items WHERE archive_path=?",
                (op["dest_path"],)
            ).fetchone()
            if indexed is None or indexed["label"] == target:
                continue
            # Nonempty labels with unknown/blank provenance may have been
            # manually entered by an older OSCAR version: preserve them.
            if (indexed["label_provenance"] not in allowed
                    or (indexed["label"] and not indexed["label_provenance"])):
                skipped_manual += 1
                continue
        # Before any SQLite change, read and rehash the archived, published
        # FLACs; do not trust a stale journal or a MusicBrainz lookup alone.
        snapshot = scan._archive_snapshot(op["dest_path"])
        if any(scan._canonical(t["tags"].get("LABEL", [])) != scan._canonical(names)
               for t in snapshot["tracks"]):
            raise LabelEnrichmentError(
                "Archived LABEL tags differ from approved revision; refusing Collection resync"
            )
        with archive_revision._db() as db:
            changed = db.execute(
                "UPDATE archive_items SET label=?,label_provenance=? "
                "WHERE archive_path=? AND label=? AND label_provenance=?",
                (target, "archive_revision_approved_labels", op["dest_path"],
                 indexed["label"], indexed["label_provenance"])
            )
            updated += changed.rowcount
            verified += 1
    return {
        "labels_updated": updated,
        "verified_completed_revisions": verified,
        "manual_values_preserved": skipped_manual,
        "archive_modified": False,
        "note": "Only approved revisions with matching actual archived LABEL tags are synchronized.",
    }
