"""Keep MusicBrainz process-global rate limiting isolated across offline tests."""
import pytest
from oscar import mb_client, alias_cache, musicbrainz


@pytest.fixture(autouse=True)
def reset_mb_request_state(monkeypatch):
    monkeypatch.setattr(mb_client, "_UNAVAILABLE_UNTIL", 0.0)
    monkeypatch.setattr(alias_cache, "_UNAVAILABLE_UNTIL", 0.0)
    monkeypatch.setattr(musicbrainz, "_LAST_REQUEST", 0.0)
