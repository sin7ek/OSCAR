"""Bounded read-only evidence review for music genres.

Provider agreement is NOT a calibrated probability of genre truth.
No archive, local Collection, FLAC or SOURCES.txt writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
import urllib.parse
import urllib.request

from oscar import archive_genres
from oscar import musicbrainz as mb
from oscar import discogs_readonly as discogs
from oscar.mb_client import fetch_json

_UUID = re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}\Z")
_MAX_CLAIMS = 12
_POLICY = "genre-evidence-v1"


class GenreEvidenceError(ValueError):
    pass


def _safe_ref(value):
    if not isinstance(value, str) or not 0 < len(value) <= 500:
        raise GenreEvidenceError("Invalid evidence reference")
    return value


def _claim(provider, scope, ref, genres, *, status="classified",
           identity="verified_release_id", group=None, raw=None, extra=None):
    """Normalize one provider's album-level statement; preserve raw terms."""
    if not isinstance(genres, list) or len(genres) > 40:
        raise GenreEvidenceError("Malformed provider genre list")
    raw_genres = [v[:120] for v in genres if isinstance(v, str) and v.strip()]
    normalized = archive_genres.normalize_genres(raw_genres)
    if status == "classified" and not normalized:
        status = "no_supported_genre" if raw_genres else "no_genre"
    return {
        "provider": provider, "scope": scope, "reference": _safe_ref(ref),
        "identity_evidence": identity, "independence_group": group or provider,
        "status": status, "raw_genres": raw_genres[:40], "genres": normalized,
        "provider_details": dict(extra or {}),
    }


def analyze(claims, *, workflow="semi_automatic", profile=None):
    """Aggregate independently grounded source claims with transparent counts.

    Genres may be multiple; a missing/unsupported source is NOT an opposing
    vote. Distinct release/release-group views from the same provider only
    count once. A provider must not claim album identity by artist alone.
    """
    if workflow not in {"secure", "semi_automatic", "best_guess"}:
        raise GenreEvidenceError("Invalid OSCAR identification workflow")
    if not isinstance(claims, list) or len(claims) > _MAX_CLAIMS:
        raise GenreEvidenceError("Too many evidence claims")
    clusters = {}
    cleaned = []
    allowed_status = {"classified", "no_genre", "no_supported_genre",
                      "unavailable", "edition_unverified"}
    for item in claims:
        if not isinstance(item, dict):
            raise GenreEvidenceError("Malformed genre evidence")
        if item.get("status") not in allowed_status:
            raise GenreEvidenceError("Unknown provider status")
        provider = item.get("provider")
        cluster = item.get("independence_group")
        if not isinstance(provider, str) or not re.fullmatch(r"[a-z_]{2,35}", provider):
            raise GenreEvidenceError("Invalid evidence provider")
        if not isinstance(cluster, str) or not re.fullmatch(r"[a-z_]{2,35}", cluster):
            raise GenreEvidenceError("Invalid source independence group")
        vals = item.get("genres")
        if not isinstance(vals, list) or len(vals) > 40:
            raise GenreEvidenceError("Invalid normalized genres")
        values = archive_genres.normalize_genres(vals)
        # Claims are immutable provider observations, not user-provided votes.
        if set(values) != set(vals):
            raise GenreEvidenceError("Unrecognized genre in source claim")
        if item["status"] == "classified" and not values:
            raise GenreEvidenceError("Classified source has no usable genre")
        if item["status"] != "classified" and values:
            raise GenreEvidenceError("Only classified sources may support a genre")
        cleaned.append(item)
        if item["status"] == "classified":
            if cluster in clusters:
                raise GenreEvidenceError(
                    "Two positive observations from one provider must be resolved before voting"
                )
            clusters[cluster] = set(values)
    total = len(clusters)
    counts = {}
    for vote in clusters.values():
        for genre in vote:
            counts[genre] = counts.get(genre, 0) + 1
    rank = {name: i for i, name in enumerate(archive_genres._PREFERRED)}
    findings = []
    for genre, supporters in sorted(counts.items(), key=lambda p: (rank.get(p[0], 999), p[0])):
        ratio = supporters / total if total else 0
        if total >= 3 and supporters >= 3 and ratio >= .75:
            confidence = "high"
        elif supporters >= 2 and ratio > .5:
            confidence = "medium"
        elif total >= 2 and ratio <= .5:
            confidence = "conflict"
        else:
            confidence = "limited"
        findings.append({
            "genre": genre, "supporting_independent_sources": supporters,
            "applicable_independent_sources": total,
            "agreement_fraction": f"{supporters}/{total}",
            "agreement_percent": round(100 * ratio, 1),
            "confidence": confidence,
            "needs_review": confidence != "high" or workflow != "best_guess",
        })
    return {
        "policy_version": _POLICY, "workflow": workflow,
        "sources_checked": len(cleaned),
        "independent_sources_with_genres": total,
        "sources_without_applicable_genres": sum(
            x["status"] != "classified" for x in cleaned),
        "findings": findings, "sources": cleaned,
        "outcome": ("unclassified" if not findings else
                    "review_required" if all(x["confidence"] in {"limited", "conflict"}
                                             for x in findings) else "suggestion"),
        "automatic_archive_write": False,
        "note": ("Agreement is the proportion of independent, applicable source "
                 "claims; it is not a statistical probability. Read-only: "
                 "nothing is accepted, archived, or retagged."),
    }


def _mb_request(entity, entity_id, *, opener=None):
    if entity not in ("release", "release-group") or not _UUID.fullmatch(entity_id):
        raise GenreEvidenceError("Invalid MusicBrainz entity")
    url = f"https://musicbrainz.org/ws/2/{entity}/{entity_id}?inc=genres&fmt=json"
    request = urllib.request.Request(url, headers={
        "User-Agent": mb._UA, "Accept": "application/json",
    })
    payload = fetch_json(request, opener=opener, timeout=15, max_bytes=1_000_000)
    if payload.get("id", "").lower() != entity_id.lower():
        raise GenreEvidenceError("MusicBrainz identity differs from exact archived release")
    return payload, url


def musicbrainz_claims(release_id, *, opener=None):
    """Release and release-group are observations in ONE provider cluster.

    Prefer release if both provide genres. Group only supplies fallback and
    cannot increase independent source count.
    """
    payload, url = _mb_request("release", release_id, opener=opener)
    release = _claim("musicbrainz", "release", url,
                     [g.get("name") for g in (payload.get("genres") or [])
                      if isinstance(g, dict) and type(g.get("count")) is int
                      and g["count"] > 0 and isinstance(g.get("name"), str)],
                     extra={"positive_genre_votes": [
                         {"name": g["name"], "votes": g["count"]}
                         for g in (payload.get("genres") or [])
                         if isinstance(g, dict) and type(g.get("count")) is int
                         and g["count"] > 0 and isinstance(g.get("name"), str)
                     ][:40]})
    group = payload.get("release-group") or {}
    group_id = group.get("id") if isinstance(group, dict) else None
    if release["status"] == "classified" or not isinstance(group_id, str) or not _UUID.fullmatch(group_id):
        return [release]
    try:
        group_payload, group_url = _mb_request("release-group", group_id, opener=opener)
    except (mb.MusicBrainzError, GenreEvidenceError):
        return [release, _claim("musicbrainz", "release_group", url,
                                [], status="unavailable")]
    group_claim = _claim("musicbrainz", "release_group", group_url,
                         [g.get("name") for g in (group_payload.get("genres") or [])
                          if isinstance(g, dict) and type(g.get("count")) is int
                          and g["count"] > 0 and isinstance(g.get("name"), str)],
                         extra={"positive_genre_votes": [
                             {"name": g["name"], "votes": g["count"]}
                             for g in (group_payload.get("genres") or [])
                             if isinstance(g, dict) and type(g.get("count")) is int
                             and g["count"] > 0 and isinstance(g.get("name"), str)
                         ][:40]})
    return [group_claim, {**release, "status": "no_genre", "genres": []}]


def _squash(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def discogs_claim(discogs_release_id, *, catalog, barcode="", opener=None):
    """Explicit Discogs edition, never search by artist/title and claim match.

    A matching catalog+CD format is required; barcodes add evidence. This is
    an edition candidate, not independent proof of a pressing.
    """
    if type(discogs_release_id) is not int or not 1 <= discogs_release_id <= 99_999_999:
        raise GenreEvidenceError("Invalid Discogs release ID")
    if not isinstance(catalog, str) or not catalog.strip():
        raise GenreEvidenceError("Archived physical catalog number required for Discogs comparison")
    data = discogs._get(f"/releases/{discogs_release_id}", opener=opener)
    if data.get("id") != discogs_release_id:
        raise GenreEvidenceError("Discogs returned an unrelated release")
    labels = data.get("labels") or []
    matched_catalog = any(_squash(x.get("catno")) == _squash(catalog)
                          for x in labels if isinstance(x, dict))
    formats = data.get("formats") or []
    has_cd = any(str(x.get("name", "")).casefold() == "cd"
                 for x in formats if isinstance(x, dict))
    ref = f"https://www.discogs.com/release/{discogs_release_id}"
    if not matched_catalog or not has_cd:
        return _claim("discogs", "release", ref, [], status="edition_unverified",
                      identity="catalog_number_or_cd_format_mismatch",
                      extra={"matched_catalog": matched_catalog, "format_cd": has_cd})
    barcodes = [str(x.get("value") or "") for x in (data.get("identifiers") or [])
                if isinstance(x, dict) and str(x.get("type") or "").casefold() == "barcode"]
    barcode_match = bool(barcode and any(_squash(barcode) == _squash(b) for b in barcodes))
    raw = [*(data.get("genres") or []), *(data.get("styles") or [])]
    return _claim("discogs", "release", ref,
                  [str(x) for x in raw if isinstance(x, str)],
                  identity="catalog_number_and_cd_format",
                  extra={"matched_catalog": True, "format_cd": True,
                         "matched_barcode": barcode_match})


def report_for_archive(archive_path, *, discogs_release_id=None, mb_opener=None,
                       discogs_opener=None, workflow="semi_automatic"):
    from oscar import archive_metadata_scan as scanner, collection_catalog as catalog
    snapshot = scanner._archive_snapshot(archive_path)
    root = catalog.archive_root()
    relative = str(archive_path).removeprefix(str(root) + "/")
    # Require that the verified physical archive is already indexed.
    with catalog._connect() as db:
        row = db.execute(
            "SELECT catalog_number FROM archive_items WHERE archive_path=? "
            "AND musicbrainz_release_id=?",
            (snapshot["path"], snapshot["release_id"]),
        ).fetchone()
    if row is None:
        raise GenreEvidenceError("Import the verified archive into Collection before genre review")
    claims = musicbrainz_claims(snapshot["release_id"], opener=mb_opener)
    if discogs_release_id is not None:
        if discogs.configured():
            barcode = (snapshot["tracks"][0]["tags"].get("BARCODE") or [""])[0]
            claims.append(discogs_claim(discogs_release_id, catalog=row["catalog_number"],
                                        barcode=barcode, opener=discogs_opener))
        else:
            claims.append(_claim("discogs", "release",
                                 f"https://www.discogs.com/release/{discogs_release_id}",
                                 [], status="unavailable", identity="not_configured"))
    report = analyze(claims, workflow=workflow)
    report.update({
        "archive_path": snapshot["path"],
        "musicbrainz_release_id": snapshot["release_id"],
        "publish_id": snapshot["publish_id"],
        "archive_manifest_sha256": snapshot["manifest_sha256"],
        "disc_number": snapshot["disc_number"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_independence_note": ("MusicBrainz release and release-group are "
                                     "one source, not two. Discogs claims are "
                                     "provisional independence pending derivation review."),
    })
    report["evidence_fingerprint"] = hashlib.sha256(json.dumps({
        "policy": _POLICY, "release_id": snapshot["release_id"],
        "manifest": snapshot["manifest_sha256"], "claims": claims,
    }, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return report
