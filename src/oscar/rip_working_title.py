"""Display-only MusicBrainz hints for completed staging rips."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import re
import tempfile
import threading
import time
import unicodedata

from oscar import musicbrainz, ripping, verification


_FILENAME = "working-title.json"
_LOCK = threading.Lock()
_PENDING = set()
_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="oscar-working-title")
_COMPLETED = {"needs_verification", "partial_diagnostic"}


def _key(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if c.isalnum())


def summarize(releases):
    """Use the majority album identity, ignoring formatting and pressing variants."""
    labels = {}
    votes = Counter()
    seen = set()
    for release in releases:
        if not isinstance(release, dict):
            continue
        release_id = release.get("id")
        if not isinstance(release_id, str) or not release_id or release_id in seen:
            continue
        seen.add(release_id)
        artist = " ".join(str(release.get("artist") or "").split())
        title = " ".join(str(release.get("title") or "").split())
        identity = (_key(artist), _key(title))
        if not all(identity):
            continue
        labels.setdefault(identity, f"{artist[:150]} — {title[:200]}")
        votes[identity] += 1
    if votes:
        identity, count = votes.most_common(1)[0]
        if count * 2 > len(seen):
            return labels[identity]
    return ""


def _cached(directory, job_id, disc_id):
    path = directory / _FILENAME
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("job_id") != job_id or value.get("disc_id") != disc_id:
        return {}
    return value


def _find(directory, job_id, disc_id, toc):
    try:
        try:
            label = summarize(musicbrainz.lookup_releases(disc_id, toc)["releases"])
            retry_at = time.time() + 86400
        except musicbrainz.MusicBrainzError:
            label = ""
            retry_at = time.time() + 300
        if not (directory / _FILENAME).is_symlink():
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                             prefix=".working-title-", delete=False) as stream:
                temp = directory / stream.name
                try:
                    json.dump({"job_id": job_id, "disc_id": disc_id,
                               "title": label, "retry_at": retry_at}, stream)
                    stream.close()
                    temp.replace(directory / _FILENAME)
                finally:
                    temp.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError, KeyError):
        pass
    finally:
        with _LOCK:
            _PENDING.discard(job_id)


def display(job_id, disc_id, *, schedule=False):
    """Read a saved hint and optionally queue a bounded lookup off the request path."""
    if not isinstance(disc_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{28}", disc_id):
        return ""
    try:
        directory = verification._safe_job(job_id)
        cached = _cached(directory, job_id, disc_id)
        if cached.get("title"):
            return str(cached["title"])[:353]
        if not schedule or not musicbrainz.lookup_enabled() or cached.get("retry_at", 0) > time.time():
            return ""
        state_path = verification._file_readonly(directory, "state.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("id") != job_id or state.get("status") not in _COMPLETED or state.get("disc_id") != disc_id:
            return ""
        plan_path = verification._file_readonly(directory, "plan.json")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        toc = plan.get("toc_string")
        if plan.get("disc_id") != disc_id or not isinstance(toc, str) or not re.fullmatch(
                r"[0-9]+(?: [0-9]+){3,102}", toc):
            return ""
        with _LOCK:
            if job_id not in _PENDING and len(_PENDING) < 50:
                _PENDING.add(job_id)
                _WORKER.submit(_find, directory, job_id, disc_id, toc)
    except (ripping.RipError, OSError, ValueError, TypeError, AttributeError):
        pass
    return ""
