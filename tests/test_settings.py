from pathlib import Path

import pytest
from pydantic import ValidationError

from oscar.settings import (
    OscarSettings, DriveSettings, discover_settings, inspect_drives,
    read_settings, save_settings,
)


def test_new_install_has_no_hardcoded_drives(tmp_path):
    assert read_settings(tmp_path / "missing.json").drives == []


def test_settings_round_trip(tmp_path: Path):
    path = tmp_path / "settings.json"
    settings = OscarSettings(profile="classical", drives=[
        DriveSettings(stable_id="ata-Optiarc_DVD_RW_AD-7200S", label="Optiarc", enabled=True, offset_samples=48),
    ])
    save_settings(settings, path)
    assert read_settings(path) == settings
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_drive_discovery_from_sysfs_and_by_id(tmp_path: Path):
    sysclass = tmp_path / "sys"
    byid = tmp_path / "by-id"
    bypath = tmp_path / "by-path"
    for d in (sysclass, byid, bypath):
        d.mkdir()
    for name, model in (("sr1", "GH24NS95"), ("sr2", "GP95NB")):
        dev = sysclass / name / "device"
        dev.mkdir(parents=True)
        (dev / "model").write_text(model)
        (dev / "vendor").write_text("HL-DT-ST")
        (dev / "rev").write_text("1.00")
    (byid / "ata-HL-DT-ST_GH24NS95_ABC").symlink_to("../../sr1")
    (byid / "usb-HL-DT-ST_GP95NB_XYZ").symlink_to("../../sr2")
    found = inspect_drives(sysclass, byid, bypath)
    assert len(found) == 2
    assert found[1]["device"] == "/dev/sr2"
    assert found[1]["stable_id"] == "usb-HL-DT-ST_GP95NB_XYZ"
    assert found[1]["identity_persistent"] is True
    settings = discover_settings(tmp_path / "settings.json", found)
    assert len(settings.drives) == 2
    assert not any(d.enabled for d in settings.drives)


def test_missing_drive_keeps_saved_settings(tmp_path):
    path = tmp_path / "settings.json"
    saved = OscarSettings(drives=[
        DriveSettings(stable_id="usb-HL-DT-ST_GP95NB_XYZ", label="USB LG", enabled=True, offset_samples=12)
    ])
    save_settings(saved, path)
    assert discover_settings(path, []).drives[0] == saved.drives[0]


def test_read_only_inventory_unknown_directory(tmp_path: Path):
    assert inspect_drives(tmp_path / "missing") == []


def test_drive_id_rejects_paths():
    with pytest.raises(ValidationError):
        DriveSettings(stable_id="../../etc/passwd", label="bad")


def test_default_identification_policy_is_secure_and_existing_configs_migrate(tmp_path):
    path = tmp_path / "existing.json"
    path.write_text('{"profile":"archival","drives":[]}', encoding="utf-8")
    settings = read_settings(path)
    assert settings.identification_mode == "secure"
    assert settings.secure_review_level == "on_ambiguity"
    assert read_settings(tmp_path / "missing.json").identification_mode == "secure"


@pytest.mark.parametrize("mode,level", [
    ("best_guess", "on_ambiguity"),
    ("semi_automatic", "on_ambiguity"),
    ("secure", "on_ambiguity"),
    ("secure", "before_archive"),
    ("secure", "every_step"),
])
def test_identification_preferences_round_trip(tmp_path, mode, level):
    path = tmp_path / "settings.json"
    settings = OscarSettings(identification_mode=mode, secure_review_level=level)
    save_settings(settings, path)
    assert read_settings(path) == settings


@pytest.mark.parametrize("bad", [
    {"identification_mode": "full_auto"},
    {"identification_mode": "unsafe"},
    {"secure_review_level": "skip_all"},
])
def test_invalid_identification_preferences_rejected(bad):
    with pytest.raises(ValidationError):
        OscarSettings(**bad)


def test_identification_modes_visible_but_not_misrepresented_as_active():
    from fastapi.testclient import TestClient
    from oscar.api import app
    html = TestClient(app).get("/").text
    for text in ("identification-mode", "secure-review-level", "best_guess", "semi_automatic",
                 "on_ambiguity", "before_archive", "every_step",
                 "Best Guess automatic publication requires a separate container opt-in"):
        assert text in html


def test_semi_automatic_is_distinct_from_secure_submode(tmp_path):
    path=tmp_path/"settings.json"
    saved=OscarSettings(identification_mode="semi_automatic",
                        secure_review_level="every_step")
    save_settings(saved,path)
    loaded=read_settings(path)
    assert loaded.identification_mode=="semi_automatic"
    assert loaded.secure_review_level=="every_step"
    assert OscarSettings(identification_mode="secure").identification_mode=="secure"
