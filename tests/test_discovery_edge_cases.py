"""Additional discovery edge cases for optional USB optical drives."""
from pathlib import Path

from oscar.settings import DriveSettings, OscarSettings, discover_settings, inspect_drives, save_settings


def test_unidentified_sr_device_is_visible_but_not_persistent(tmp_path: Path):
    sysclass = tmp_path / "sys"
    dev = sysclass / "sr9" / "device"
    dev.mkdir(parents=True)
    (dev / "vendor").write_text("USB")
    (dev / "model").write_text("GP95NB")
    result = inspect_drives(sysclass, tmp_path / "missing-by-id", tmp_path / "missing-by-path")
    assert len(result) == 1
    assert result[0]["device"] == "/dev/sr9"
    assert result[0]["stable_id"] == "ephemeral-sr9"
    assert result[0]["identity_persistent"] is False


def test_drive_settings_survive_usb_disconnect(tmp_path: Path):
    path = tmp_path / "config.json"
    saved = DriveSettings(
        stable_id="usb-LG_GP95NB_serial123", label="Dad's CD drive",
        enabled=True, offset_samples=24,
    )
    save_settings(OscarSettings(drives=[saved]), path)
    assert discover_settings(path, []).drives == [saved]
