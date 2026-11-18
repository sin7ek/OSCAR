# Optical drive discovery and GUI (prototype)

OSCAR discovers all `/sys/class/block/srN` devices at startup/request time, including SATA and USB drives such as LG GP95NB. Drives are **not hardcoded**.

- `GET /api/drives`: discover read-only via sysfs and udev symlinks.
- `GET /api/settings`: merge discovered devices with persisted preferences; newly seen devices default disabled.
- `PUT /api/settings`: save per-drive labels, enabled state and optional read offset.
- `/`: settings web GUI.

The initial reference host had LG GH24NS95 (`sr1`), Optiarc AD-7200S (`sr2`) and HP DH16AAL (`sr3`). An additional USB LG GP95NB is planned.

## Identity and hotplug
Device numbers `sr0`, `sr1`, etc. **may change** across boots/reattachment. OSCAR attempts `/dev/disk/by-id` first, then `/dev/disk/by-path`. If neither exists, it uses an `ephemeral-srN` identity and must warn that persistent settings may move to another physical drive. USB drives can appear/disappear, and stored settings for absent drives are retained.

## Docker caveat
Seeing `/sys/class/block/srN` is **not the same as having block-device permissions inside Docker**. Bind-mounting host sysfs and the udev symlink directories permits discovery, but the rip worker later requires restricted access to selected optical devices. Docker `--device` is typically evaluated at container creation, not automatically updated for later USB hotplug. Plan a deliberately scoped worker/device broker (or controlled container recreation) rather than granting the entire API container `privileged` access.

## Safety
This stage implements **no media reads, no rips, no archive publication and no cleanup**. Keep GUI behind authentication or bound to localhost until access control is implemented. Real-hardware tests still needed.
