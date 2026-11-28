"""Local cache of the official MusicBrainz genre names."""
from functools import lru_cache
import logging
from pathlib import Path
import tempfile
import time
from urllib.request import Request

from oscar import mb_client, musicbrainz
from oscar.settings import config_path

_URL = "https://musicbrainz.org/ws/2/genre/all?fmt=txt"
_REFRESH_AGE = 7 * 24 * 60 * 60
_CHECK_INTERVAL = 60 * 60
_LOG = logging.getLogger(__name__)


def _path():
    return config_path().with_name("musicbrainz-genre-vocabulary.txt")


def _parse(text):
    names = [line.strip() for line in text.splitlines() if line.strip()]
    keys = {name.casefold() for name in names}
    if (not {"classical", "jazz", "rock"} <= keys
            or any(len(name) > 150 or not name.isprintable()
                   or "<" in name or ">" in name for name in names)):
        raise ValueError("Invalid MusicBrainz genre vocabulary")
    return {
        name.casefold(): " ".join(part[:1].upper() + part[1:] for part in name.split())
        for name in names
    }


@lru_cache(maxsize=4)
def _read(path: Path, revision):
    try:
        return _parse(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def names():
    """Return cached names without a network request."""
    path = _path()
    try:
        stat = path.stat()
    except OSError:
        return {}
    return _read(path, (stat.st_ino, stat.st_mtime_ns, stat.st_size))


def _refresh():
    path = _path()
    if names() and time.time() - path.stat().st_mtime < _REFRESH_AGE:
        return
    request = Request(_URL, headers={
        "Accept": "text/plain",
        "User-Agent": musicbrainz._UA,
    })
    text = mb_client.fetch_text(request)
    vocabulary = _parse(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        temp = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    _LOG.info("Cached %d MusicBrainz genre names", len(vocabulary))


def refresh_worker(stop):
    while not stop.is_set():
        try:
            _refresh()
        except (musicbrainz.MusicBrainzError, OSError, ValueError) as exc:
            _LOG.warning("Unable to refresh MusicBrainz genre vocabulary: %s", exc)
        stop.wait(_CHECK_INTERVAL)
