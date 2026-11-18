from pathlib import Path

from oscar.settings import (
    DEFAULT_SETTINGS, OscarSettings, DriveSettings,
    inspect_drives, read_settings, save_settings,
)


def test_default_devices_disabled():
    assert len(DEFAULT_SETTINGS.drives) == 3
    assert all(not drive.enabled for drive in DEFAULT_SETTINGS.drives)


def test_settings_round_trip(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = OscarSettings(profile="classical", drives=[
        DriveSettings(stable_id="ata-Optiarc_DVD_RW_AD-7200S", label="Optiarc", enabled=True, offset_samples=48),
    ])
    save_settings(settings, path)
    assert read_settings(path) == settings
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_read_only_inventory_unknown_directory(tmp_path: Path):
    assert inspect_drives(tmp_path / "missing") == []


def test_drive_id_rejects_paths():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        DriveSettings(stable_id="../../etc/passwd", label="bad")
