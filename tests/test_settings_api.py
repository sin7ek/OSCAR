from fastapi.testclient import TestClient

from oscar.api import app


def test_settings_api_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    client = TestClient(app)
    response = client.get("/api/settings")
    assert response.status_code == 200
    settings = response.json()
    assert len(settings["drives"]) == 3
    assert all(not d["enabled"] for d in settings["drives"])

    settings["profile"] = "classical"
    settings["drives"][1]["enabled"] = True
    updated = client.put("/api/settings", json=settings)
    assert updated.status_code == 200
    assert client.get("/api/settings").json() == settings
    assert (tmp_path / "settings.json").exists()


def test_reject_unknown_rip_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    client = TestClient(app)
    settings = client.get("/api/settings").json()
    settings["auto_delete"] = True
    assert client.put("/api/settings", json=settings).status_code == 422


def test_reject_duplicate_devices(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    client = TestClient(app)
    settings = client.get("/api/settings").json()
    settings["drives"].append(settings["drives"][0])
    assert client.put("/api/settings", json=settings).status_code == 422


def test_gui_is_available():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Optical drives" in response.text
    assert "no ripping" in response.text
