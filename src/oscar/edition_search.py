"""Cross-reference physical identifiers without accepting a release."""
import re
import urllib.parse
import urllib.request

from oscar import discogs_readonly, musicbrainz, ripping
from oscar.boxsets import RELEASE_ID
from oscar.mb_client import fetch_json
from oscar.physical_release import _normalized_catalog
from oscar.pressing_evidence import observed_matrix


def _digits(value):
    return re.sub(r"[^0-9]", "", str(value or ""))


def _discogs_links(ids):
    if not ids:
        return {}
    urls = {f"https://www.discogs.com/release/{n}": n for n in ids}
    params = [("inc", "release-rels"), ("fmt", "json")]
    params += [("resource", url) for url in urls]
    request = urllib.request.Request(
        "https://musicbrainz.org/ws/2/url?" + urllib.parse.urlencode(params),
        headers={"User-Agent": musicbrainz._UA, "Accept": "application/json"},
    )
    data = fetch_json(request, timeout=12, max_bytes=500_000, allow_404=True) or {}
    result = {}
    for item in data.get("urls", [data]):
        discogs_id = urls.get(item.get("resource"))
        if not discogs_id:
            continue
        for relation in item.get("relations", []):
            release = relation.get("release") or {}
            if RELEASE_ID.fullmatch(str(release.get("id") or "")):
                result.setdefault(release["id"], set()).add(discogs_id)
    return result


def _discogs_candidates(catalog, barcode, matrix, mastering_sid, mould_sid):
    return discogs_readonly.search_pressings(
        catalog=catalog, barcode=barcode, matrix=matrix,
        mastering_sid=mastering_sid, mould_sid=mould_sid,
    )["releases"]


def search(job_id, *, catalog, barcode, matrix, mastering_sid, mould_sid):
    if not musicbrainz.lookup_enabled():
        raise ValueError("MusicBrainz lookup is disabled")
    rip = ripping.status(job_id)
    if rip.get("status") != "needs_verification":
        raise ValueError("Select a completed full-disc rip")
    catalog, matrix, mastering_sid, mould_sid = map(
        observed_matrix, (catalog, matrix, mastering_sid, mould_sid))
    barcode = re.sub(r"[ -]", "", barcode or "")
    if barcode and not re.fullmatch(r"[0-9]{8,14}", barcode):
        raise ValueError("Enter the full printed barcode")
    if not any((catalog, barcode, matrix)):
        raise ValueError("Enter a catalog number, barcode or matrix")
    from oscar.go_controller import _source_plan
    plan = _source_plan(job_id)
    if plan.get("disc_id") != rip.get("disc_id"):
        raise ValueError("Saved disc identity differs from extraction")
    candidates = {}
    notices = []

    def add(releases, source):
        for release in releases:
            release_id = release.get("id")
            if not isinstance(release_id, str) or not RELEASE_ID.fullmatch(release_id):
                continue
            row = candidates.setdefault(release_id, {"id": release_id, "sources": set()})
            row["sources"].add(source)
            for field in ("title", "artist", "labels", "barcode", "country", "date", "formats"):
                if release.get(field):
                    row[field] = release[field]

    try:
        add(musicbrainz.lookup_releases(plan["disc_id"], plan["toc_string"])["releases"], "disc_lookup")
    except musicbrainz.MusicBrainzError as exc:
        notices.append("MusicBrainz disc lookup: " + str(exc))
    for field, value in (("barcode", barcode), ("catalog_number", catalog), ("matrix_runout", matrix)):
        if value:
            try:
                add(musicbrainz.search_release_candidates(**{field: value})["releases"], field)
            except musicbrainz.MusicBrainzError as exc:
                notices.append(f"MusicBrainz {field}: {exc}")
    discogs = []
    links = {}
    if catalog or barcode:
        if discogs_readonly.configured():
            try:
                discogs = _discogs_candidates(catalog, barcode, matrix, mastering_sid, mould_sid)
                links = _discogs_links([item["id"] for item in discogs])
            except (discogs_readonly.DiscogsError, musicbrainz.MusicBrainzError) as exc:
                notices.append("Discogs cross-reference: " + str(exc))
        else:
            notices.append("Discogs lookup needs OSCAR_DISCOGS_PAT.")
    for release_id in links:
        add([{"id": release_id}], "linked_discogs_release")
    ranked = []
    for row in candidates.values():
        formats = row.get("formats", [])
        if formats and not any("CD" in item.upper() for item in formats):
            continue
        sources = row["sources"]
        labels = row.get("labels", [])
        cat_matches = bool(catalog and any(
            _normalized_catalog(item.get("catalog_number")) == _normalized_catalog(catalog)
            for item in labels
        ))
        barcode_matches = bool(barcode and _digits(row.get("barcode")) == barcode)
        if barcode and row.get("barcode") and not barcode_matches:
            row["barcode_conflict"] = True
        references = []
        for item in discogs:
            linked = item["id"] in links.get(row["id"], ())
            shared = (cat_matches and barcode_matches
                      and _normalized_catalog(row.get("title")) == _normalized_catalog(item.get("title"))
                      and _normalized_catalog(row.get("artist")) == _normalized_catalog(item.get("artist"))
                      and _digits(item.get("barcode")) == barcode
                      and _normalized_catalog(catalog) in {
                          _normalized_catalog(value) for value in item.get("catalog_numbers", [])})
            if linked or shared:
                references.append({**item, "link": "MusicBrainz URL relation" if linked else
                                   "Shared artist, title, barcode and catalog number"})
        supported = any(
            all(value == "matches" for value in variant["comparison"].values())
            and "Matrix / Runout" in variant["comparison"]
            and variant["variant"] != "Unnumbered identifiers"
            for item in references for variant in item.get("variants", [])
        )
        row.update({"discogs": references, "catalog_matches": cat_matches,
                    "barcode_matches": barcode_matches, "sources": sorted(sources),
                    "score": (int(supported) * 8 + int("matrix_runout" in sources) * 6
                              + int(bool(references)) * 3 + int(barcode_matches) * 4
                              + int(cat_matches) * 3 + int("disc_lookup" in sources) * 2
                              - int(row.get("barcode_conflict", False)) * 15)})
        ranked.append(row)
    ranked.sort(key=lambda x: (-x["score"], x["id"]))
    ranked = ranked[:12]
    recommended = (ranked[0]["id"] if ranked and ranked[0]["score"] >= 5
                   and not ranked[0].get("barcode_conflict")
                   and (len(ranked) == 1 or ranked[0]["score"] > ranked[1]["score"]) else None)
    return {"releases": ranked, "recommended": recommended, "notices": notices,
            "unlinked_discogs": [item for item in discogs if not any(
                reference["id"] == item["id"]
                for release in ranked for reference in release["discogs"])]}
