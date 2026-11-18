"""Offline regression checks for durable MusicBrainz metadata queue."""
import sqlite3

from fastapi.testclient import TestClient
from oscar import metadata_queue as q
from oscar.alias_cache import resolve_many
from oscar.api import app
from oscar.musicbrainz import MusicBrainzError

IDS = [f"00000000-0000-0000-0000-{i:012x}" for i in range(4)]


def test_persisted_deduplicated_job_across_connections(tmp_path):
    path = tmp_path / "queue.sqlite3"
    q.enqueue("artist", IDS[0], error="HTTP 503", path=path, now=10)
    q.enqueue("artist", IDS[0], error="HTTP 503", path=path, now=12)
    assert q.summary(path=path)["pending"] == 1
    assert q.claim(path=path, now=9) is None
    job = q.claim(path=path, now=12)
    assert job == {"entity_type": "artist", "entity_id": IDS[0], "attempts": 1}
    assert q.claim(path=path, now=12) is None
    q.complete("artist", IDS[0], path=path, now=14)
    assert q.summary(path=path)["done"] == 1
    q.enqueue("artist", IDS[0], path=path, now=15)
    assert q.summary(path=path)["pending"] == 0


def test_retry_backoff_and_recover_after_restart(tmp_path):
    path = tmp_path / "queue.sqlite3"
    q.enqueue("work", IDS[1], path=path, now=10)
    first = q.claim(path=path, now=10)
    q.fail("work", IDS[1], first["attempts"], "HTTP 503", path=path, now=11)
    assert q.claim(path=path, now=100) is None
    second = q.claim(path=path, now=101)
    assert second["attempts"] == 2
    # A worker crash leaves a recoverable lease after 180 seconds.
    assert q.claim(path=path, now=280) is None
    recovered = q.claim(path=path, now=281)
    assert recovered["attempts"] == 3


def test_transient_failure_eventually_resolves(tmp_path, monkeypatch):
    path = tmp_path / "queue.sqlite3"
    from oscar import alias_cache
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    q.enqueue("artist", IDS[2], path=path, now=10)
    calls = []
    def fake_fetch(kind, mbid):
        calls.append(mbid)
        if len(calls) == 1:
            raise MusicBrainzError("MusicBrainz HTTP 503")
        return {"entity_type": kind, "id": mbid, "original": "Чайковский",
                "english": "Tchaikovsky"}
    assert q.process_one(path=path, alias_path=tmp_path / 'aliases.db', fetcher=fake_fetch, now=10)
    assert q.summary(path=path)["pending"] == 1
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    assert q.process_one(path=path, alias_path=tmp_path / 'aliases.db', fetcher=fake_fetch, now=101)
    assert q.summary(path=path)["done"] == 1
    assert not q.process_one(path=path, alias_path=tmp_path / 'aliases.db', fetcher=fake_fetch, now=102)


def test_permanent_error_not_requeued(tmp_path):
    path = tmp_path / "queue.sqlite3"
    q.enqueue("artist", IDS[0], path=path, now=1)
    q.process_one(path=path, alias_path=tmp_path / 'aliases.db', fetcher=lambda *a: (_ for _ in ()).throw(
        MusicBrainzError("MusicBrainz HTTP 404")), now=1)
    assert q.summary(path=path)["failed"] == 1


def test_queue_requires_valid_artist_or_work_mbid(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        q.enqueue("release", IDS[0], path=tmp_path / "queue.db")
    with pytest.raises(ValueError):
        q.enqueue("artist", "../bad", path=tmp_path / "queue.db")


def test_transient_alias_failure_is_enqueued(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_METADATA_QUEUE_PATH", str(tmp_path / "queue.db"))
    from oscar import alias_cache
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    result = resolve_many([{"entity_type": "artist", "entity_id": IDS[3]}],
        fetcher=lambda *a: (_ for _ in ()).throw(MusicBrainzError("MusicBrainz HTTP 503")),
        path=tmp_path / "aliases.db")
    assert result[0]["queued_for_retry"] is True
    assert q.summary(path=tmp_path / "queue.db")["pending"] == 1


def test_queue_status_api(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_METADATA_QUEUE_PATH", str(tmp_path / "queue.db"))
    monkeypatch.delenv("OSCAR_ENABLE_METADATA_WORKER", raising=False)
    response = TestClient(app).get("/api/metadata-queue")
    assert response.status_code == 200
    assert response.json() == {"worker_enabled": False, "pending": 0,
                               "running": 0, "done": 0, "failed": 0}
