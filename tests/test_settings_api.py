from fastapi.testclient import TestClient
import oscar.settings as drive_settings

from oscar.api import app


def test_settings_api_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(drive_settings, "inspect_drives", lambda: [
        {"stable_id": "usb-HL-DT-ST_GP95NB_123", "device": "/dev/sr4",
         "label": "LG GP95NB", "firmware": "1.0", "present": True, "identity_persistent": True}
    ])
    client = TestClient(app)
    response = client.get("/api/settings")
    assert response.status_code == 200
    settings = response.json()
    assert len(settings["drives"]) == 1
    assert not settings["drives"][0]["enabled"]
    settings["profile"] = "classical"
    settings["drives"][0]["enabled"] = True
    updated = client.put("/api/settings", json=settings)
    assert updated.status_code == 200
    assert client.get("/api/settings").json() == settings


def test_reject_unknown_rip_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(drive_settings, "inspect_drives", lambda: [])
    client = TestClient(app)
    settings = client.get("/api/settings").json()
    settings["auto_delete"] = True
    assert client.put("/api/settings", json=settings).status_code == 422


def test_reject_duplicate_devices(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(drive_settings, "inspect_drives", lambda: [
        {"stable_id":"ata-ONE", "device":"/dev/sr1", "label":"One"}
    ])
    client = TestClient(app)
    settings = client.get("/api/settings").json()
    settings["drives"].append(settings["drives"][0])
    assert client.put("/api/settings", json=settings).status_code == 422


def test_gui_is_available():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Optical drives" in response.text
    assert "Original ripping files are preserved" in response.text
