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


def search_pressings(*, catalog, barcode, matrix, mastering_sid, mould_sid, opener=None):
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
    if not catalog and not barcode:
        raise DiscogsError("Enter a printed catalog number or barcode")
    query = {"type": "release", "format": "CD", "per_page": 5}
    if catalog:
        query["catno"] = catalog
    if barcode:
        query["barcode"] = barcode
    data = _get("/database/search", query=query, opener=opener)
    candidates = []
    for item in data.get("results", [])[:5]:
        release_id = item.get("id")
        if type(release_id) is not int or not 1 <= release_id <= 99_999_999:
            continue
        release = _get(f"/releases/{release_id}", opener=opener)
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
                           "barcode": next((x.get("value") for x in release.get("identifiers", [])
                                            if x.get("type") == "Barcode"), None),
                           "catalog_numbers": [x.get("catno") for x in release.get("labels", [])],
                           "variants": rows})
    pagination = data.get("pagination") or {}
    return {"releases": candidates, "search_total": pagination.get("items"),
            "inspection_limit": 5}
