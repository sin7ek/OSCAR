"""Read-only Discogs account discovery using local OSCAR_DISCOGS_PAK secret.

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
    return bool(os.environ.get("OSCAR_DISCOGS_PAK", "").strip())


def _get(path: str, *, opener=None):
    token = os.environ.get("OSCAR_DISCOGS_PAK", "").strip()
    if not token:
        raise DiscogsError("Set OSCAR_DISCOGS_PAK in your private Portainer stack environment")
    if not re.fullmatch(r"[A-Za-z0-9_-]{12,200}", token):
        raise DiscogsError("Invalid OSCAR_DISCOGS_PAK setting")
    if not path.startswith("/") or ".." in path or "?" in path:
        raise DiscogsError("Invalid Discogs resource")
    request = urllib.request.Request("https://api.discogs.com" + path, headers={
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
