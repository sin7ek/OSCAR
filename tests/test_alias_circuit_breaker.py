"""A failed MusicBrainz alias lookup must not trigger an N-work request storm."""
import sqlite3
import time
import pytest

from oscar import alias_cache
from oscar.alias_cache import get_alias, resolve_many
from oscar.musicbrainz import MusicBrainzError

IDS = [f"00000000-0000-0000-0000-{i:012x}" for i in range(8)]


def test_503_stops_further_requests_in_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    calls = []

    def overloaded(kind, mbid):
        calls.append(mbid)
        raise MusicBrainzError("MusicBrainz HTTP 503")

    entities = [{"entity_type": "work", "entity_id": x} for x in IDS]
    responses = resolve_many(entities, fetcher=overloaded, path=tmp_path / "aliases.db")
    assert len(responses) == len(IDS)
    assert len(calls) == 1
    assert all("error" in response for response in responses)


def test_stale_alias_served_on_503_without_overwriting_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    path = tmp_path / "aliases.db"
    original = {"entity_type": "artist", "id": IDS[0],
                "original": "Original name", "english": "English name"}
    get_alias("artist", IDS[0], fetcher=lambda *_: original, path=path, now=1)
    def overloaded(*_):
        raise MusicBrainzError("MusicBrainz HTTP 503")
    result = get_alias("artist", IDS[0], fetcher=overloaded, path=path,
                       now=40 * 86400)
    assert result["cache_status"] == "stale"
    assert result["english"] == "English name"
    with sqlite3.connect(path) as db:
        assert db.execute("select checked_at from aliases").fetchone()[0] == 1


def test_cooldown_expires_then_lookup_resumes(tmp_path, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(alias_cache.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    calls = []

    def fetch(kind, mbid):
        calls.append(mbid)
        if len(calls) == 1:
            raise MusicBrainzError("MusicBrainz HTTP 503")
        return {"entity_type": kind, "id": mbid,
                "original": "A", "english": "B"}

    path = tmp_path / "aliases.db"
    with pytest.raises(MusicBrainzError):
        get_alias("artist", IDS[0], fetcher=fetch, path=path)
    with pytest.raises(MusicBrainzError, match="cooldown"):
        get_alias("artist", IDS[1], fetcher=fetch, path=path)
    assert len(calls) == 1
    clock[0] += 91
    assert get_alias("artist", IDS[1], fetcher=fetch, path=path)["english"] == "B"
    assert len(calls) == 2


def test_invalid_entity_does_not_open_circuit(tmp_path, monkeypatch):
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    with pytest.raises(MusicBrainzError, match="Invalid alias"):
        get_alias("artist", "invalid", path=tmp_path / "cache.db")
    assert alias_cache._UNAVAILABLE_UNTIL == 0.0
