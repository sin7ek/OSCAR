"""Every metadata endpoint shares the same MusicBrainz transport."""
import json
import urllib.error

import pytest
from oscar import mb_client, musicbrainz as mb
from oscar.aliases import lookup_aliases
from oscar.boxsets import lookup_release_medium

ARTIST = "c278de2c-9696-4fdf-a919-0781cd945e2c"
DISC = "I5l9cCSFccLKFEKS.7wqSZAorPU-"
RELEASE = "423f636d-742d-47b0-9ba2-51515a6fdfd2"


class Response:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return json.dumps(self.payload).encode()


def error(code, headers=None):
    return urllib.error.HTTPError("https://musicbrainz.org", code, "test", headers or {}, None)


def test_global_cooldown_blocks_disc_and_release_after_alias_503(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(mb_client.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(mb_client.time, "sleep", lambda s: clock.__setitem__(0, clock[0]+s))
    attempts = []
    def overloaded(req, timeout):
        attempts.append(req.full_url)
        raise error(503)
    with pytest.raises(mb.MusicBrainzError, match="503"):
        lookup_aliases("artist", ARTIST, opener=overloaded)
    assert len(attempts) == 3
    with pytest.raises(mb.MusicBrainzError, match="cooldown"):
        mb.lookup_releases(DISC, "1 2 37500 150 15150", opener=overloaded)
    with pytest.raises(mb.MusicBrainzError, match="cooldown"):
        lookup_release_medium(RELEASE, DISC, 2, opener=overloaded)
    assert len(attempts) == 3


def test_cooldown_recovers_after_delay(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(mb_client.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(mb_client.time, "sleep", lambda s: clock.__setitem__(0, clock[0]+s))
    with pytest.raises(mb.MusicBrainzError, match="503"):
        lookup_aliases("artist", ARTIST, opener=lambda req, timeout: (_ for _ in ()).throw(error(503)))
    clock[0] += 91
    reply = Response({"id": ARTIST, "name": "Original", "aliases":[]})
    result = lookup_aliases("artist", ARTIST, opener=lambda req, timeout: reply)
    assert result["original"] == "Original"


def test_404_disc_id_only_is_no_match():
    result = mb.lookup_releases(DISC, "1 2 37500 150 15150",
        opener=lambda req,timeout: (_ for _ in ()).throw(error(404)))
    assert result["status"] == "no_match"


def test_404_alias_is_not_negative_alias():
    with pytest.raises(mb.MusicBrainzError, match="404"):
        lookup_aliases("artist", ARTIST,
            opener=lambda req,timeout: (_ for _ in ()).throw(error(404)))


def test_retry_after_header(monkeypatch):
    clock=[1000.0]
    sleeps=[]
    monkeypatch.setattr(mb_client.time, "monotonic", lambda:clock[0])
    def sleep(s):
        sleeps.append(s)
        clock[0]+=s
    monkeypatch.setattr(mb_client.time,"sleep",sleep)
    attempts=[]
    def opener(req,timeout):
        attempts.append(1)
        if len(attempts)==1:
            raise error(429, {"Retry-After": "7"})
        return Response({"id": ARTIST,"name": "OK","aliases":[]})
    assert lookup_aliases("artist",ARTIST,opener=opener)["original"] == "OK"
    assert 7.0 in sleeps


def test_no_503_is_cached_as_success():
    # JSON errors do not open cooldown or claim absence.
    with pytest.raises(mb.MusicBrainzError, match="Invalid MusicBrainz JSON"):
        mb_client.fetch_json(
            __import__("urllib.request",fromlist=["Request"]).Request("https://musicbrainz.org/ws/2/"),
            opener=lambda req,timeout: BadResponse())


class BadResponse:
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return b"not-json"
