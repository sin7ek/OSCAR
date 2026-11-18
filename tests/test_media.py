"""Mocked tests: no physical optical drives are opened."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
import oscar.media as media
from oscar.api import app


def test_probe_denied_by_default(monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_MEDIA_PROBE", raising=False)
    assert TestClient(app).get("/api/media").status_code == 403


def test_drive_probe_returns_audio(monkeypatch):
    closed = []
    requests = []
    monkeypatch.setattr(media.os, "stat", lambda path: SimpleNamespace(st_mode=0o060000))
    monkeypatch.setattr(media.os, "open", lambda path, flags: 42)
    monkeypatch.setattr(media.os, "close", lambda fd: closed.append(fd))
    def fake_ioctl(fd, cmd, arg):
        requests.append((fd, cmd, arg))
        return 4 if cmd == media.CDROM_DRIVE_STATUS else 100
    monkeypatch.setattr(media.fcntl, "ioctl", fake_ioctl)
    result = media.probe_device("/dev/sr2")
    assert result["status"] == "disc_present"
    assert result["disc_type"] == "audio"
    assert closed == [42]
    assert requests == [(42, 0x5326, 0x7FFFFFFF), (42, 0x5327, 0)]


def test_drive_probe_no_disc_does_not_request_disc_type(monkeypatch):
    requested = []
    monkeypatch.setattr(media.os, "stat", lambda path: SimpleNamespace(st_mode=0o060000))
    monkeypatch.setattr(media.os, "open", lambda path, flags: 5)
    monkeypatch.setattr(media.os, "close", lambda fd: None)
    def fake_ioctl(fd, cmd, arg):
        requested.append(cmd)
        return 1
    monkeypatch.setattr(media.fcntl, "ioctl", fake_ioctl)
    assert media.probe_device("/dev/sr2")["status"] == "no_disc"
    assert requested == [media.CDROM_DRIVE_STATUS]


def test_invalid_device_path_is_rejected():
    assert media.probe_device("/dev/sda")["status"] == "error"


def test_probe_requires_enabled_and_persistent_identity(monkeypatch):
    from oscar.settings import OscarSettings, DriveSettings
    monkeypatch.setattr(media, "discover_settings", lambda: OscarSettings(drives=[
        DriveSettings(stable_id="ata-Optiarc", label="Optiarc", enabled=True),
        DriveSettings(stable_id="ephemeral-sr4", label="USB", enabled=True)
    ]))
    monkeypatch.setattr(media, "inspect_drives", lambda: [
        dict(stable_id="ata-Optiarc", device="/dev/sr2", label="Optiarc", identity_persistent=True),
        dict(stable_id="ephemeral-sr4", device="/dev/sr4", label="USB", identity_persistent=False),
        dict(stable_id="ata-HP", device="/dev/sr3", label="HP", identity_persistent=True)
    ])
    probed = []
    monkeypatch.setattr(media, "probe_device", lambda device: (probed.append(device) or {"status": "no_disc"}))
    result = media.probe_enabled_drives()
    assert probed == ["/dev/sr2"]
    assert len(result) == 2
    assert result[1]["status"] == "unavailable"


def test_gui_contains_manual_probe_button():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Check inserted discs" in response.text
