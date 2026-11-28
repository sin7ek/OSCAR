"""Single-process MusicBrainz transport for all OSCAR metadata requests.

Serializes alias, release, and disc-ID calls through one rate limiter.  All
lookups are read-only.  No API failures are cached as negative results.
"""
import json
import time
import urllib.error
import urllib.request

from oscar import musicbrainz as mb

_MIN_INTERVAL = 1.1
_COOLDOWN_SECONDS = 90
_RETRYABLE = {429, 500, 502, 503, 504}
_UNAVAILABLE_UNTIL = 0.0


def _retry_delay(error, attempt):
    """Respect server Retry-After seconds (bounded) or use 3s, 6s backoff."""
    value = (error.headers or {}).get("Retry-After") if error.headers else None
    try:
        seconds = float(value)
        if seconds >= 0:
            return min(60.0, seconds)
    except (ValueError, TypeError):
        pass
    return 3.0 * (attempt + 1)


def _fetch(request, *, opener=None, timeout=12, max_bytes=1_000_000,
           allow_404=False):
    """Retrieve a bounded response, serially, with retries and a shared cooldown.

    No untrusted URLs: callers must construct validated MusicBrainz endpoints.
    Uses the original MusicBrainz module's lock and clock for compatibility
    with callers and existing test fixtures.
    """
    global _UNAVAILABLE_UNTIL
    with mb._LOCK:
        if time.monotonic() < _UNAVAILABLE_UNTIL:
            raise mb.MusicBrainzError("MusicBrainz temporarily unavailable (cooldown)")
        for attempt in range(3):
            delay = _MIN_INTERVAL - (time.monotonic() - mb._LAST_REQUEST)
            if delay > 0:
                time.sleep(delay)
            mb._LAST_REQUEST = time.monotonic()
            try:
                response = (opener or urllib.request.urlopen)(request, timeout=timeout)
                with response:
                    payload = response.read(max_bytes + 1)
                if len(payload) > max_bytes:
                    raise mb.MusicBrainzError("MusicBrainz response too large")
                return payload
            except urllib.error.HTTPError as exc:
                if exc.code == 404 and allow_404:
                    return None
                if exc.code in _RETRYABLE:
                    if attempt < 2:
                        time.sleep(_retry_delay(exc, attempt))
                        continue
                    _UNAVAILABLE_UNTIL = time.monotonic() + _COOLDOWN_SECONDS
                raise mb.MusicBrainzError(f"MusicBrainz HTTP {exc.code}") from exc
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < 2:
                    time.sleep(3.0 * (attempt + 1))
                    continue
                _UNAVAILABLE_UNTIL = time.monotonic() + _COOLDOWN_SECONDS
                raise mb.MusicBrainzError("Could not obtain MusicBrainz response") from exc
    raise AssertionError("Unreachable MusicBrainz transport state")


def fetch_json(request, *, opener=None, timeout=12, max_bytes=1_000_000,
               allow_404=False):
    payload = _fetch(request, opener=opener, timeout=timeout,
                     max_bytes=max_bytes, allow_404=allow_404)
    if payload is None:
        return None
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise mb.MusicBrainzError("Invalid MusicBrainz JSON response") from exc
    if not isinstance(data, dict):
        raise mb.MusicBrainzError("Unexpected MusicBrainz JSON response")
    return data


def fetch_text(request, *, timeout=12, max_bytes=256_000):
    payload = _fetch(request, timeout=timeout, max_bytes=max_bytes)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise mb.MusicBrainzError("Invalid MusicBrainz text response") from exc
