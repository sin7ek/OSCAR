"""Persistent, bounded cache for MusicBrainz artist/work aliases.

Stored beside OSCAR settings in /config. No archive or audio access.
"""
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from oscar.aliases import lookup_aliases
from oscar.settings import config_path

_CACHE_LOCK = threading.RLock()
_POSITIVE_TTL = 30 * 86400
_NEGATIVE_TTL = 7 * 86400


def cache_path() -> Path:
    return Path(os.environ.get("OSCAR_ALIAS_CACHE_PATH", str(config_path().parent / "aliases.sqlite3")))


def _connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=20)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aliases (
          entity_type TEXT NOT NULL,
          entity_id TEXT NOT NULL,
          response_json TEXT NOT NULL,
          checked_at INTEGER NOT NULL,
          PRIMARY KEY (entity_type, entity_id)
        )
    """)
    return conn


def get_alias(entity_type: str, entity_id: str, *, fetcher=lookup_aliases,
              path: Path | None = None, now: int | None = None) -> dict:
    # Validation also happens in lookup_aliases; enforce before any DB write.
    from oscar.aliases import _ID, _TYPES
    if entity_type not in _TYPES or not _ID.fullmatch(entity_id):
        from oscar.musicbrainz import MusicBrainzError
        raise MusicBrainzError("Invalid alias entity")
    entity_id = entity_id.lower()
    path = path or cache_path()
    now = int(time.time()) if now is None else now
    with _CACHE_LOCK:
        with _connect(path) as db:
            row = db.execute(
                "SELECT response_json, checked_at FROM aliases WHERE entity_type=? AND entity_id=?",
                (entity_type, entity_id),
            ).fetchone()
            if row:
                data = json.loads(row[0])
                ttl = _POSITIVE_TTL if data.get("english") else _NEGATIVE_TTL
                if now - row[1] < ttl:
                    return {**data, "cache_status": "hit"}
            # Never overwrite a good cache entry when MusicBrainz is unavailable.
            data = fetcher(entity_type, entity_id)
            db.execute(
                """INSERT INTO aliases(entity_type,entity_id,response_json,checked_at)
                VALUES(?,?,?,?) ON CONFLICT(entity_type,entity_id) DO UPDATE SET
                response_json=excluded.response_json,checked_at=excluded.checked_at""",
                (entity_type, entity_id, json.dumps(data, ensure_ascii=False), now),
            )
            db.commit()
            return {**data, "cache_status": "refreshed" if row else "miss"}


def resolve_many(entities: list[dict], *, fetcher=lookup_aliases,
                 path: Path | None = None) -> list[dict]:
    """Return each unique requested entity, capping remote requests per call."""
    from oscar.musicbrainz import MusicBrainzError
    if len(entities) > 12:
        raise MusicBrainzError("Too many aliases in a request (maximum 12)")
    unique = set()
    results = []
    for entity in entities:
        if not isinstance(entity, dict):
            raise MusicBrainzError("Invalid alias request")
        entity_type = entity.get("entity_type")
        entity_id = entity.get("entity_id")
        if not isinstance(entity_type, str) or not isinstance(entity_id, str):
            raise MusicBrainzError("Invalid alias entity")
        key = (entity_type, entity_id.lower())
        if key in unique:
            continue
        unique.add(key)
        try:
            results.append(get_alias(*key, fetcher=fetcher, path=path))
        except MusicBrainzError as exc:
            results.append({"entity_type": key[0], "id": key[1], "error": str(exc)})
    return results
