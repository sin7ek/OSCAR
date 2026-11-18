"""Configuration storage and read-only optical-drive inventory.

Settings cannot start a rip, write to Archive or trigger deletion.
"""
import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DriveSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stable_id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.-]+$")
    label: str = Field(min_length=1, max_length=100)
    enabled: bool = False
    offset_samples: int | None = Field(default=None, ge=-2000, le=2000)


class OscarSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str = Field(default="archival", pattern=r"^(archival|classical)$")
    drives: list[DriveSettings] = Field(default_factory=list)
    # Deliberately no destructive or rip-start flags until worker integration.


DEFAULT_SETTINGS = OscarSettings(drives=[
    DriveSettings(stable_id="ata-HL-DT-ST_DVDRAM_GH24NS95_KRQCCM33843", label="LG GH24NS95"),
    DriveSettings(stable_id="ata-Optiarc_DVD_RW_AD-7200S", label="Optiarc AD-7200S"),
    DriveSettings(stable_id="ata-hp_DVD_A_DH16AAL_2B9950003803", label="HP DH16AAL"),
])


def config_path() -> Path:
    return Path(os.environ.get("OSCAR_CONFIG_PATH", "/config/settings.json"))


def read_settings(path: Path | None = None) -> OscarSettings:
    path = path or config_path()
    if not path.exists():
        return DEFAULT_SETTINGS.model_copy(deep=True)
    return OscarSettings.model_validate_json(path.read_text(encoding="utf-8"))


def save_settings(settings: OscarSettings, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement; never overwrite partially written JSON.
    fd, tmp = tempfile.mkstemp(prefix=".oscar-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(settings.model_dump(mode="json"), stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def inspect_drives(by_id_dir: Path = Path("/dev/disk/by-id")) -> list[dict[str, str | bool]]:
    """Read-only device-listing: caller must mount /dev/disk/by-id to see host names."""
    if not by_id_dir.is_dir():
        return []
    found = []
    for entry in sorted(by_id_dir.glob("ata-*")):
        if not entry.is_symlink() or not any(x in entry.name.lower() for x in ("dvd", "dvdram", "cd", "optiarc")):
            continue
        # resolve(strict=False) never accesses media.
        target = entry.resolve(strict=False)
        found.append({"stable_id": entry.name, "device": str(target), "present": target.exists()})
    return found
