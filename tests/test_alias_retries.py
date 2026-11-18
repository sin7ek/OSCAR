"""MusicBrainz 503/429 must be retried safely, never stored as a missing alias."""
import io
import json
import urllib.error

import pytest
from oscar import aliases
from oscar import musicbrainz as mb
from oscar.alias_cache import get_alias

ID="c278de2c-9696-4fdf-a919-0781cd945e2c"


class Reply:
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n):
        return json.dumps({"id":ID,"name":"Игорь Фёдорович Стравинский",
                           "aliases":[{"locale":"en","primary":True,"name":"Igor Stravinsky"}]}).encode()


def error(code):
    return urllib.error.HTTPError("https://musicbrainz.org",code,"temporary",{},None)


def test_503_then_success_retries_without_losing_name(monkeypatch):
    import oscar.aliases as module
    clock=[10000.0]
    sleeps=[]
    monkeypatch.setattr(module.time,"monotonic",lambda:clock[0])
    def sleep(seconds):
        sleeps.append(seconds)
        clock[0]+=seconds
    monkeypatch.setattr(module.time,"sleep",sleep)
    monkeypatch.setattr(mb,"_LAST_REQUEST",0.0)
    attempts=[]
    def opener(req,timeout):
        attempts.append(req.full_url)
        if len(attempts)==1: raise error(503)
        return Reply()
    data=aliases.lookup_aliases("artist",ID,opener=opener)
    assert data["english"]=="Igor Stravinsky"
    assert len(attempts)==2
    assert 3 in sleeps


def test_persistent_503_is_not_cached(monkeypatch,tmp_path):
    import oscar.aliases as module
    monkeypatch.setattr(module.time,"sleep",lambda seconds:None)
    monkeypatch.setattr(module.time,"monotonic",lambda:100000.0)
    monkeypatch.setattr(mb,"_LAST_REQUEST",0.0)
    attempts=[]
    def failing(kind,id):
        return aliases.lookup_aliases(kind,id,opener=lambda req,timeout: (
            attempts.append(1), (_ for _ in ()).throw(error(503))
        )[1])
    path=tmp_path/"aliases.sqlite3"
    with pytest.raises(mb.MusicBrainzError,match="503"):
        get_alias("artist",ID,fetcher=failing,path=path,now=1)
    assert len(attempts)==3
    import sqlite3
    with sqlite3.connect(path) as db:
        count=db.execute("SELECT count(*) FROM aliases").fetchone()[0]
    assert count==0


def test_nontransient_404_does_not_retry(monkeypatch):
    import oscar.aliases as module
    monkeypatch.setattr(module.time,"monotonic",lambda:100000.0)
    monkeypatch.setattr(mb,"_LAST_REQUEST",0.0)
    attempts=[]
    def opener(req,timeout):
        attempts.append(1)
        raise error(404)
    with pytest.raises(mb.MusicBrainzError,match="404"):
        aliases.lookup_aliases("work",ID,opener=opener)
    assert len(attempts)==1


def test_rate_limit_clock_advances_between_calls(monkeypatch):
    import oscar.aliases as module
    t=[10000.0]
    sleeps=[]
    monkeypatch.setattr(module.time,"monotonic",lambda:t[0])
    monkeypatch.setattr(module.time,"sleep",lambda delta:(sleeps.append(delta),t.__setitem__(0,t[0]+delta)))
    monkeypatch.setattr(mb,"_LAST_REQUEST",0.0)
    aliases.lookup_aliases("artist",ID,opener=lambda req,timeout:Reply())
    aliases.lookup_aliases("artist",ID,opener=lambda req,timeout:Reply())
    assert any(delta>=1.0 for delta in sleeps)
