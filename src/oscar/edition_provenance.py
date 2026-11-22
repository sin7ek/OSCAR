"""Persist the evidence offered during edition discovery, separately from approval."""
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from oscar import verification
from oscar.boxsets import RELEASE_ID


_FILES = {"disc_lookup": "edition-disc-lookup.json",
          "combined_search": "edition-combined-search.json"}
_FIELDS = {"catalog": "Catalog number", "barcode": "Barcode", "matrix": "Matrix/runout",
           "mastering_sid": "Mastering SID", "mould_sid": "Mould SID",
           "discogs_release": "Entered Discogs release ID"}


def save(job_id, disc_id, method, releases, *, identifiers=None, suggested=None, notices=()):
    """Save a bounded snapshot of the comparisons, excluding raw provider responses."""
    directory = verification._safe_job(job_id)
    candidates = {}
    for release in releases[:250]:
        release_id = release.get("id")
        if not isinstance(release_id, str) or not RELEASE_ID.fullmatch(release_id):
            continue
        candidates[release_id.lower()] = {
            "musicbrainz_country": release.get("country") or "",
            "search_sources": release.get("sources", ["disc_lookup"]),
            "catalog_matches": release.get("catalog_matches"),
            "barcode_matches": release.get("barcode_matches"),
            "barcode_conflict": bool(release.get("barcode_conflict")),
            "discogs": [
                {"id": ref["id"], "country": ref.get("country") or "",
                 "link": ref["link"], "variants": ref.get("variants", [])[:30]}
                for ref in release.get("discogs", [])[:20]
            ],
        }
    report = {"job_id": job_id, "disc_id": disc_id, "method": method,
              "identifiers": {key: value for key, value in (identifiers or {}).items()
                              if key in _FIELDS and value},
              "suggested_release_id": suggested, "candidates": candidates,
              "notices": list(notices)[:20]}
    path = directory / _FILES[method]
    if path.is_file() and not path.is_symlink() and path.stat().st_size <= 2_000_000:
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
            previous.pop("searched_at", None)
            if previous == report:
                return
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    report["searched_at"] = datetime.now(timezone.utc).isoformat()
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                             prefix=".edition-evidence-", delete=False) as out:
        temp = Path(out.name)
        try:
            json.dump(report, out, ensure_ascii=False)
            out.close()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def for_release(directory, job_id, disc_id, release_id):
    """Include only evidence for this copy's actual release and saved disc."""
    if not disc_id:
        return None
    results = []
    for method, filename in _FILES.items():
        file = directory / filename
        if file.is_symlink() or not file.is_file():
            continue
        try:
            if file.stat().st_size > 2_000_000:
                continue
            report = json.loads(file.read_text(encoding="utf-8"))
            if (report.get("job_id") != job_id or report.get("disc_id") != disc_id
                    or report.get("method") != method):
                continue
            evidence = report["candidates"].get(release_id.lower())
            if evidence is not None:
                results.append({
                    "method": method, "searched_at": report["searched_at"],
                    "identifiers": report["identifiers"],
                    "suggested_for_review": (report["suggested_release_id"] or "").lower() == release_id.lower(),
                    "candidate_count": len(report["candidates"]),
                    "notices": report.get("notices", []),
                    **evidence,
                })
        except (OSError, ValueError, AttributeError, TypeError, KeyError):
            continue
    return results or None


def _line(value):
    return " ".join(str(value).split())


def render(searches):
    lines = ["", "[Edition search]"]
    for record in searches:
        label = ("MusicBrainz lookup using the saved Disc ID and TOC"
                 if record["method"] == "disc_lookup" else "Combined identifier search")
        lines.append(f"{label} ({record['searched_at']})")
        lines.append(f"MusicBrainz candidates recorded: {record['candidate_count']}")
        lines.append("Candidate evidence: " + ", ".join(record["search_sources"]))
        if record["method"] == "combined_search":
            lines.append("Combined search suggested this candidate: " +
                         ("yes" if record["suggested_for_review"] else "no"))
        for key, value in record["identifiers"].items():
            lines.append(f"{_FIELDS[key]} (operator input): {_line(value)}")
        if record["catalog_matches"]:
            lines.append("Entered catalog matches MusicBrainz")
        if record["barcode_matches"]:
            lines.append("Entered barcode matches MusicBrainz")
        if record["barcode_conflict"]:
            lines.append("Entered barcode differs from MusicBrainz")
        country = record["musicbrainz_country"]
        if country:
            lines.append("MusicBrainz release country: " + _line(country))
        for ref in record["discogs"]:
            lines.append(f"Discogs reference: https://www.discogs.com/release/{ref['id']} "
                         f"({_line(ref['link'])})")
            if ref["country"]:
                lines.append("  Discogs release country: " + _line(ref["country"]))
            for variant in ref["variants"]:
                comparison = ", ".join(f"{_line(field)} {_line(status).replace('_', ' ')}"
                                       for field, status in variant["comparison"].items())
                lines.append(f"  {_line(variant['variant'])}: {comparison}")
        for notice in record["notices"]:
            lines.append("Lookup note: " + _line(notice))
    return lines
