"""Persistent metadata cache tests, without hardware or network."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from oscar.alias_cache import get_alias, resolve_many
from oscar.api import app

ARTIST = "c278de2c-9696-4fdf-a919-0781cd945e2c"
OTHER = "f0f0d88c-d107-44cc-861c-450aedbf999d"


def fake_alias(kind, mbid):
    return {"entity_type":kind,"id":mbid,"original":"Игорь Стравинский",
            "english":"Igor Stravinsky", "english_source":"musicbrainz_alias",
            "sort_name":"Stravinsky, Igor"}


def test_first_lookup_and_persistent_cache(tmp_path):
    path = tmp_path/"cache.sqlite3"
    calls=[]
    def fetch(kind,id):
        calls.append(id)
        return fake_alias(kind,id)
    first=get_alias("artist",ARTIST,fetcher=fetch,path=path,now=100)
    second=get_alias("artist",ARTIST,fetcher=fetch,path=path,now=101)
    assert first["cache_status"]=="miss"
    assert second["cache_status"]=="hit"
    assert second["english"]=="Igor Stravinsky"
    assert calls==[ARTIST]


def test_cache_expires_after_thirty_days(tmp_path):
    path=tmp_path/"cache.sqlite3"
    calls=[]
    def fetch(kind,id):
        calls.append(id)
        return fake_alias(kind,id)
    get_alias("artist",ARTIST,fetcher=fetch,path=path,now=10)
    result=get_alias("artist",ARTIST,fetcher=fetch,path=path,now=32*86400)
    assert result["cache_status"]=="refreshed"
    assert len(calls)==2


def test_negative_alias_cache_is_shorter(tmp_path):
    path=tmp_path/"cache.sqlite3"
    calls=[]
    def fetch(kind,id):
        calls.append(id)
        return {**fake_alias(kind,id),"english":None}
    get_alias("artist",ARTIST,fetcher=fetch,path=path,now=10)
    assert get_alias("artist",ARTIST,fetcher=fetch,path=path,now=11)["cache_status"]=="hit"
    get_alias("artist",ARTIST,fetcher=fetch,path=path,now=8*86400)
    assert len(calls)==2


def test_alias_cache_is_separate_from_config_and_archive(tmp_path):
    path=tmp_path/"config"/"aliases.sqlite3"
    get_alias("artist",ARTIST,fetcher=fake_alias,path=path,now=1)
    assert path.exists()
    assert not (tmp_path/"music").exists()


def test_batch_deduplicates_and_uses_cache(tmp_path):
    calls=[]
    def fetch(kind,id):
        calls.append((kind,id))
        return fake_alias(kind,id)
    path=tmp_path/"aliases.sqlite3"
    req=[{"entity_type":"artist","entity_id":ARTIST},
         {"entity_type":"artist","entity_id":ARTIST},
         {"entity_type":"artist","entity_id":OTHER}]
    result=resolve_many(req,fetcher=fetch,path=path)
    assert len(result)==2
    resolve_many(req,fetcher=fetch,path=path)
    assert len(calls)==2


def test_reject_more_than_twelve(tmp_path):
    with pytest.raises(Exception,match="Too many"):
        resolve_many([{"entity_type":"artist","entity_id":ARTIST}]*13,path=tmp_path/"aliases.sqlite3")


def test_reject_bad_id_before_cache_write(tmp_path):
    path=tmp_path/"aliases.sqlite3"
    with pytest.raises(Exception,match="Invalid alias"):
        get_alias("artist","../../etc/passwd",path=path)
    assert not path.exists()


def test_batch_api_requires_opt_in(monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_MUSICBRAINZ",raising=False)
    result=TestClient(app).post("/api/name-aliases/batch",json=[
        {"entity_type":"artist","entity_id":ARTIST}
    ])
    assert result.status_code==403


def test_gui_enrichment_is_automatic():
    html=TestClient(app).get("/").text
    assert "enrichNamesAutomatically(area)" in html
    assert "/api/name-aliases/batch" in html
    assert "alias-enrichment" in html
