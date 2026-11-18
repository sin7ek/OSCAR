"""Artist and work aliases are explicit, never machine-guessed or overwritten."""
import json

import pytest
from fastapi.testclient import TestClient
from oscar import aliases
from oscar.api import app
from oscar.settings import OscarSettings, read_settings, save_settings

ARTIST="c278de2c-9696-4fdf-a919-0781cd945e2c"
WORK="10e1b739-2492-4e99-b1df-72d6d8022561"


class FakeReply:
    def __init__(self, data):
        self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n): return json.dumps(self.data).encode()


def test_prefers_current_primary_english_alias():
    result=aliases.choose_english_alias([
        {"locale":"en","name":"Igor Stravinsky","primary":True},
        {"locale":"en","name":"Old name","primary":True,"ended":True},
        {"locale":"en","name":"I. Stravinsky"},
        {"locale":"fr","name":"Igor Stravinski"},
    ],"Игорь Фёдорович Стравинский")
    assert result["english"]=="Igor Stravinsky"
    assert result["source"]=="musicbrainz_alias"


def test_no_english_alias_is_not_fabricated():
    assert aliases.choose_english_alias([
        {"locale":"fr","name":"Nom français"},
        {"locale":"ru","name":"Русское имя"}
    ],"Игорь Фёдорович Стравинский")["english"] is None


def test_artist_alias_lookup_returns_original_and_english(monkeypatch):
    import oscar.musicbrainz as mb
    monkeypatch.setattr(mb.time,"monotonic",lambda:100000.0)
    monkeypatch.setattr(mb.time,"sleep",lambda n:None)
    captured=[]
    def open_fake(request,timeout):
        captured.append(request.full_url)
        return FakeReply({
            "id":ARTIST,"name":"Игорь Фёдорович Стравинский",
            "sort-name":"Stravinsky, Igor",
            "aliases":[{"locale":"en","name":"Igor Stravinsky","primary":True}]
        })
    data=aliases.lookup_aliases("artist",ARTIST,opener=open_fake)
    assert data["original"]=="Игорь Фёдорович Стравинский"
    assert data["english"]=="Igor Stravinsky"
    assert data["sort_name"]=="Stravinsky, Igor"
    assert data["id"]==ARTIST
    assert "inc=aliases" in captured[0]


def test_work_alias_lookup_can_have_english_work_title(monkeypatch):
    import oscar.musicbrainz as mb
    monkeypatch.setattr(mb.time,"monotonic",lambda:100000.0)
    monkeypatch.setattr(mb.time,"sleep",lambda n:None)
    data=aliases.lookup_aliases("work",WORK,opener=lambda request,timeout:FakeReply({
        "id":WORK,"title":"Pastorale","aliases":[
            {"locale":"en","name":"Pastoral","primary":True}
        ]
    }))
    assert data["english"]=="Pastoral"
    assert data["entity_type"]=="work"


def test_untrusted_entity_types_and_ids_blocked():
    with pytest.raises(Exception): aliases.lookup_aliases("release",ARTIST)
    with pytest.raises(Exception): aliases.lookup_aliases("artist","../../secret")
    with pytest.raises(Exception): aliases.lookup_aliases("work","bad")


def test_user_language_prefs_persist_without_damaging_drives(tmp_path):
    path=tmp_path/"settings.json"
    settings=OscarSettings(name_display="original_and_english",english_alias_fallback="sort_name")
    save_settings(settings,path)
    got=read_settings(path)
    assert got.name_display=="original_and_english"
    assert got.english_alias_fallback=="sort_name"
    assert got.drives==[]
    assert (path.stat().st_mode & 0o777)==0o600


def test_existing_config_defaults_to_bilingual(tmp_path):
    path=tmp_path/"settings.json"
    path.write_text('{"profile":"classical","drives":[]}')
    cfg=read_settings(path)
    assert cfg.name_display=="original_and_english"
    assert cfg.english_alias_fallback=="original"


def test_alias_api_requires_opt_in(monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_MUSICBRAINZ",raising=False)
    r=TestClient(app).get("/api/name-aliases",params={"entity_type":"artist","entity_id":ARTIST})
    assert r.status_code==403


def test_language_settings_available_in_gui():
    html=TestClient(app).get("/").text
    assert 'id="name-display"' in html
    assert 'id="alias-fallback"' in html
    assert "aliasNode('artist'" in html
    assert "aliasNode('work'" in html
