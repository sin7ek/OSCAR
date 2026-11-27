"""Opt-in Linux optical-media presence probe.

Only queries drive and disc status through documented read-only CD-ROM ioctls.
Never reads raw sectors, ejects, seeks, mounts, rips or writes optical media.
"""
import fcntl
import os
import re
import stat
import sys

from oscar.settings import discover_settings, inspect_drives

CDROM_DRIVE_STATUS = 0x5326
CDROM_DISC_STATUS = 0x5327
CDROMREADTOCHDR = 0x5305
CDROMREADTOCENTRY = 0x5306
CDROM_LBA = 1
CDROM_DATA_TRACK = 4
CDSL_CURRENT = 0x7FFFFFFF

DRIVE_STATUS = {
    0: "no_info",
    1: "no_disc",
    2: "tray_open",
    3: "not_ready",
    4: "disc_present",
}
DISC_STATUS = {
    100: "audio",
    101: "data",
    102: "data",
    103: "data",
    104: "data",
    105: "mixed",
}


def _track_types(fd):
    """Read TOC track control flags, especially when CD-Extra reports as data."""
    header = bytearray(2)
    fcntl.ioctl(fd, CDROMREADTOCHDR, header)
    first, last = header
    if not 1 <= first <= last <= 99:
        raise OSError("Invalid CD TOC header")
    audio = data = 0
    for number in range(first, last + 1):
        # Linux struct cdrom_tocentry: track, ADR/control bitfields, format,
        # padding, address union (4 bytes), data mode and trailing padding.
        entry = bytearray(12)
        entry[0] = number
        entry[2] = CDROM_LBA
        fcntl.ioctl(fd, CDROMREADTOCENTRY, entry)
        control = entry[1] >> 4 if sys.byteorder == "little" else entry[1] & 15
        if control & CDROM_DATA_TRACK:
            data += 1
        else:
            audio += 1
    return audio, data


def probe_device(device: str) -> dict[str, str | int | None]:
    """Issue Linux CDROM_DRIVE_STATUS then optionally CDROM_DISC_STATUS."""
    if not re.fullmatch(r"/dev/sr\d+", device):
        return {"status": "error", "error": "Not a /dev/srN device"}
    fd = None
    try:
        if not stat.S_ISBLK(os.stat(device).st_mode):
            return {"status": "error", "error": "Not a block device"}
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        drive_code = int(fcntl.ioctl(fd, CDROM_DRIVE_STATUS, CDSL_CURRENT))
        result: dict[str, str | int | None] = {
            "status": DRIVE_STATUS.get(drive_code, "unknown"),
            "drive_code": drive_code,
            "disc_type": None,
        }
        if drive_code == 4:
            try:
                disc_code = int(fcntl.ioctl(fd, CDROM_DISC_STATUS, 0))
                result["disc_type"] = DISC_STATUS.get(disc_code, "unknown")
                result["disc_code"] = disc_code
            except OSError:
                result["disc_type"] = "unknown"
            if result["disc_type"] in {"audio", "data", "mixed", "unknown"}:
                try:
                    audio, data = _track_types(fd)
                    result["audio_tracks"] = audio
                    result["data_tracks"] = data
                    result["disc_type"] = (
                        "mixed" if audio and data else "audio" if audio else "data")
                except OSError:
                    # Non-CD media or a drive without readable TOC.
                    pass
        return result
    except PermissionError:
        return {"status": "permission_denied", "error": "Read access to optical device denied"}
    except OSError as error:
        return {"status": "unavailable", "error": f"{error.__class__.__name__}: {error.strerror}"}
    finally:
        if fd is not None:
            os.close(fd)


def probe_enabled_drives() -> list[dict]:
    """Only probe configured, enabled drives that match *current* sysfs discovery."""
    configured = discover_settings()
    enabled = {drive.stable_id for drive in configured.drives if drive.enabled}
    entries = []
    for drive in inspect_drives():
        stable_id = str(drive["stable_id"])
        if stable_id not in enabled:
            continue
        device = str(drive["device"])
        result = {"stable_id": stable_id, "device": device, "label": drive["label"]}
        # We must not probe an ambiguous device whose identity is ephemeral.
        if not drive["identity_persistent"]:
            result.update({"status": "unavailable", "error": "Persistent identity required"})
        else:
            result.update(probe_device(device))
        entries.append(result)
    return entries
