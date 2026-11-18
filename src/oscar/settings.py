"""Safe, dynamic optical-drive discovery and persisted per-drive settings."""
import json
import os
import re
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


def config_path() -> Path:
    return Path(os.environ.get("OSCAR_CONFIG_PATH", "/config/settings.json"))


def _read_attr(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def inspect_drives(
    sys_class: Path = Path("/sys/class/block"),
    by_id_dir: Path = Path("/dev/disk/by-id"),
    by_path_dir: Path = Path("/dev/disk/by-path"),
) -> list[dict[str, str | bool]]:
    """Discover every srN via sysfs, with udev identity if available.

    No media or block device is opened. /dev/srN is only an ephemeral path.
    """
    if not sys_class.is_dir():
        return []
    found: list[dict[str, str | bool]] = []
    for entry in sorted(sys_class.iterdir(), key=lambda p: int(p.name[2:]) if re.fullmatch(r"sr\d+", p.name) else 999999):
        if not re.fullmatch(r"sr\d+", entry.name):
            continue
        model = _read_attr(entry / "device/model")
        vendor = _read_attr(entry / "device/vendor")
        firmware = _read_attr(entry / "device/rev")
        # udev symlinks usually point to ../../srN; compare their target names
        # without requiring /dev/srN to be mounted in the container.
        ids: list[tuple[int, str]] = []
        for directory, priority in ((by_id_dir, 0), (by_path_dir, 1)):
            if not directory.is_dir():
                continue
            for link in directory.iterdir():
                if not link.is_symlink() or link.name.endswith("-part1"):
                    continue
                try:
                    if Path(os.readlink(link)).name == entry.name:
                        ids.append((priority, link.name))
                except OSError:
                    pass
        ids.sort(key=lambda pair: (pair[0], pair[1]))
        # In absence of a persistent ID, an ephemeral ID is displayed but
        # should not be interpreted as reliably bound to the physical drive.
        stable_id = ids[0][1] if ids else f"ephemeral-{entry.name}"
        found.append({
            "stable_id": stable_id,
            "device": f"/dev/{entry.name}",
            "label": " ".join(x for x in (vendor, model) if x) or entry.name,
            "firmware": firmware,
            "present": True,
            "identity_persistent": bool(ids),
        })
    return found


def read_settings(path: Path | None = None) -> OscarSettings:
    path = path or config_path()
    if not path.exists():
        return OscarSettings()
    return OscarSettings.model_validate_json(path.read_text(encoding="utf-8"))


def discover_settings(path: Path | None = None, discovered: list[dict] | None = None) -> OscarSettings:
    """Merge current drives without overwriting saved choices.

    Missing drives remain in settings, so unplugging does not erase offsets.
    """
    settings = read_settings(path).model_copy(deep=True)
    known = {drive.stable_id for drive in settings.drives}
    if discovered is None:
        discovered = inspect_drives()
    for drive in discovered:
        if drive["stable_id"] not in known:
            settings.drives.append(DriveSettings(
                stable_id=str(drive["stable_id"]),
                label=str(drive["label"])[:100],
            ))
            known.add(str(drive["stable_id"]))
    return settings


def save_settings(settings: OscarSettings, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
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
