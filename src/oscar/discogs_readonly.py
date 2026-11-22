"""Read-only Discogs account discovery using local OSCAR_DISCOGS_PAT secret.

Never log/return token; never persist Discogs Restricted Data. Calls use only
fixed HTTPS Discogs API host and constant endpoint paths.
"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request


class DiscogsError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.environ.get("OSCAR_DISCOGS_PAT", "").strip())


def _get(path: str, *, query=None, opener=None):
    token = os.environ.get("OSCAR_DISCOGS_PAT", "").strip()
    if not token:
        raise DiscogsError("Set OSCAR_DISCOGS_PAT in your private Portainer stack environment")
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,200}", token):
        raise DiscogsError("Invalid OSCAR_DISCOGS_PAT setting")
    if not path.startswith("/") or ".." in path or "?" in path:
        raise DiscogsError("Invalid Discogs resource")
    url = "https://api.discogs.com" + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={
        "Authorization": "Discogs token=" + token,
        "User-Agent": "OSCAR-CD-Archive/0.1 (+https://github.com/sin7ek/OSCAR)",
        "Accept": "application/json",
    })
    try:
        client = opener or urllib.request.urlopen
        with client(request, timeout=12) as response:
            body = response.read(250_001)
            if len(body) > 250_000:
                raise DiscogsError("Discogs response exceeded size limit")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        # Do not echo provider-provided bodies or request details (credentials).
        reason = "rate_limited" if exc.code == 429 else "unauthorized" if exc.code in (401, 403) else "api_error"
        raise DiscogsError(f"Discogs request failed ({reason}, HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise DiscogsError("Discogs temporarily unreachable") from None
    except (UnicodeError, ValueError) as exc:
        raise DiscogsError("Invalid Discogs API response") from None


def account_summary(*, opener=None) -> dict:
    """Identity and folders only; no collection details stored or modified."""
    if not configured():
        return {"connected": False, "message": "Discogs personal token is not configured"}
    identity = _get("/oauth/identity", opener=opener)
    username = identity.get("username")
    if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", username):
        raise DiscogsError("Discogs did not return a valid account name")
    folders = _get("/users/" + urllib.parse.quote(username, safe="") +
                   "/collection/folders", opener=opener)
    values = folders.get("folders") or []
    if not isinstance(values, list):
        raise DiscogsError("Invalid Discogs folder listing")
    cleaned = []
    for entry in values[:200]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), int):
            continue
        cleaned.append({"id": entry["id"], "name": str(entry.get("name") or "")[:120],
                        "count": entry.get("count") if isinstance(entry.get("count"), int) else None})
    return {"connected": True, "username": username, "folders": cleaned,
            "read_only": True, "provider": "Discogs",
            "notice": "Folders are live Discogs account data, not part of the local export. No collection writes."}


def _identifier_key(kind, value):
    compact = re.sub(r"\s+", "", str(value or "").upper())
    return compact if kind == "Matrix / Runout" else compact.removeprefix("IFPI")


def pressing_release_id(value):
    """Accept a release ID or public Discogs release link."""
    value = value.strip()
    if not value:
        return None
    match = re.fullmatch(r"(?:(?:https://(?:www\.)?discogs\.com/release/))?"
                         r"([1-9][0-9]{0,8})(?:-[^/?#]+)?/?(?:[?#].*)?", value)
    if not match:
        raise DiscogsError("Enter a Discogs release ID or release URL")
    return int(match[1])


def search_pressings(*, catalog, barcode, matrix, mastering_sid, mould_sid,
                     discogs_release="", expanded=False, opener=None):
    """Compare live Discogs identifiers by variant without combining different variants."""
    from oscar.pressing_evidence import observed_matrix

    observed = {
        "Matrix / Runout": observed_matrix(matrix),
        "Mastering SID Code": observed_matrix(mastering_sid),
        "Mould SID Code": observed_matrix(mould_sid),
    }
    catalog = observed_matrix(catalog)
    barcode = re.sub(r"[ -]", "", barcode or "")
    if barcode and not re.fullmatch(r"[0-9]{8,14}", barcode):
        raise DiscogsError("Enter the full printed barcode")
    pinned = pressing_release_id(discogs_release)
    if not catalog and not barcode and not pinned:
        raise DiscogsError("Enter a printed catalog number, barcode or Discogs release")
    limit = 20 if expanded else 5
    query = {"type": "release", "format": "CD", "per_page": limit}
    ids = [pinned] if pinned else []
    search_total = 0
    if catalog or barcode:
        primary = ({"barcode": barcode} if barcode and expanded else
                   {key: value for key, value in (("catno", catalog), ("barcode", barcode)) if value})
        data = _get("/database/search", query={**query, **primary}, opener=opener)
        items = data.get("results", [])
        search_total = (data.get("pagination") or {}).get("items") or len(items)
        if expanded and barcode and catalog and len(items) < limit:
            extra = _get("/database/search", query={**query, "catno": catalog, "barcode": barcode},
                         opener=opener)
            items = [*items, *extra.get("results", [])]
            search_total = max(search_total, (extra.get("pagination") or {}).get("items") or 0)
        for item in items:
            release_id = item.get("id")
            if type(release_id) is int and 1 <= release_id <= 999_999_999 and release_id not in ids:
                ids.append(release_id)
    candidates = []
    errors = []
    for release_id in ids[:limit]:
        try:
            release = _get(f"/releases/{release_id}", opener=opener)
        except DiscogsError as exc:
            if not expanded:
                raise
            errors.append(f"Discogs {release_id}: {exc}")
            if "rate_limited" in str(exc) or "unauthorized" in str(exc):
                break
            continue
        if release.get("id") != release_id or not any(
            x.get("name", "").casefold() == "cd" for x in release.get("formats", [])
        ):
            continue
        variants = {}
        for identifier in release.get("identifiers", []):
            kind = identifier.get("type")
            if kind not in observed:
                continue
            description = identifier.get("description") or ""
            variant = re.search(r"\bvariant\s*(\d+)\b", description, flags=re.IGNORECASE)
            name = f"Variant {variant[1]}" if variant else "Unnumbered identifiers"
            variants.setdefault(name, {}).setdefault(kind, []).append(
                str(identifier.get("value") or "")[:250])
        rows = []
        for name, identifiers in variants.items():
            comparison = {}
            for kind, value in observed.items():
                values = identifiers.get(kind, [])
                if value:
                    comparison[kind] = ("matches" if _identifier_key(kind, value) in
                                        {_identifier_key(kind, x) for x in values}
                                        else "differs" if values else "not_documented")
            if comparison:
                rows.append({"variant": name, "comparison": comparison})
        candidates.append({"id": release_id, "title": release.get("title"),
                           "country": release.get("country"), "year": release.get("year"),
                           "artist": " & ".join(str(a.get("name") or "")
                                                for a in release.get("artists", [])),
                           "barcodes": [x.get("value") for x in release.get("identifiers", [])
                                        if x.get("type") == "Barcode"],
                           "catalog_numbers": [x.get("catno") for x in release.get("labels", [])],
                           "variants": rows})
    return {"releases": candidates, "search_total": search_total,
            "inspection_limit": limit, "errors": errors,
            "truncated": search_total > limit or len(ids) > limit}
