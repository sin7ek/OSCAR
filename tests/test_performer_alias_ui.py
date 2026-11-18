"""The inspector must enrich verified performer names without changing roles."""
from fastapi.testclient import TestClient
from oscar.api import app
from oscar.classical import recording_roles


def test_performer_aliases_are_automatically_queued():
    html = TestClient(app).get("/").text
    assert "for(const performer of track.performers||[])" in html
    assert "aliasNode('artist',performer.artist_id,performer.name)" in html
    assert "performer.role" in html
    assert "performer.attributes" in html
    assert "enrichNamesAutomatically(area)" in html


def test_performer_id_and_role_provenance_remain_intact():
    recording = {"relations": [
        {"target-type": "artist", "type": "conductor",
         "artist": {"id": "conductor-mbid", "name": "Геннадий Николаевич Рождественский"}},
        {"target-type": "artist", "type": "performing orchestra",
         "artist": {"id": "orchestra-mbid", "name": "London Symphony Orchestra"}}
    ]}
    data = recording_roles(recording)
    assert [p["artist_id"] for p in data["performers"]] == ["conductor-mbid", "orchestra-mbid"]
    assert [p["role"] for p in data["performers"]] == ["conductor", "performing orchestra"]
    assert data["composers"] == []


def test_aliases_are_deduplicated_across_composers_and_performers():
    html = TestClient(app).get("/").text
    assert "const key=button.dataset.aliasType+':'+button.dataset.aliasId;" in html
    assert "if(!keys.has(key))keys.set(key" in html
