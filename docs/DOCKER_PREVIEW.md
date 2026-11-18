# OSCAR Docker preview (not a ripper yet)

This preview only serves a local settings GUI, detects optical drive listings and stores configuration. It cannot open CD media or write the music archive.

## Image
After a successful GitHub Actions push to main, the image should be published to `ghcr.io/sin7ek/oscar:main`. The package may initially be private depending on GitHub package settings; configure package visibility if needed.

## Unraid / Portainer
Start from `compose.preview.yml`. The default mapping `127.0.0.1:8088:8080` intentionally exposes the GUI only on the Unraid host itself. For LAN access, provide authentication via a reverse proxy **before** binding to a non-loopback address.

Persistent settings live at `/mnt/user/appdata/oscar/settings.json`.

`/sys/class/block` may list drives inside Docker without additional device permissions. Bind-mounted `/dev/disk/by-id` and `/dev/disk/by-path` permit reading symlink names and targets; do not pass `/dev/srN` through in this preview.

No Docker socket, no privileged mode, no archive mounts, no deletion. Hotplug is discovered on API refresh but **the future rip worker will need a dedicated device-access solution**.

## Test endpoints
- `GET /` — settings screen
- `GET /api/drives` — all detected optical drives from sysfs
- `GET /api/settings` — merged default drive preferences
- `PUT /api/settings` — persist configuration
- `GET /health` — application status

**Do not use this build for a production rip.**
