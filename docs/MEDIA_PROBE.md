# Milestone 01b — Test disc presence with one optical drive

This is an **opt-in, read-only hardware preview**, not a ripper.

## Functionality
The GUI offers **Check inserted discs**, calling `GET /api/media`:
- Requires `OSCAR_ENABLE_MEDIA_PROBE=1` **and** an enabled, identified drive in saved GUI settings.
- Uses `open("/dev/srN", O_RDONLY | O_NONBLOCK | O_CLOEXEC)` followed by Linux `CDROM_DRIVE_STATUS` and, where a disc is present, `CDROM_DISC_STATUS` ioctls.
- Reports `disc_present`, `no_disc`, `tray_open`, `not_ready`, permission errors and (if supported) `audio`/`data`/`mixed`.
- Does **not** read a TOC, read samples, rip, eject, mount, write files or delete anything.
- A disc being detected does **not** prove that it is an audio CD that can be ripped reliably.

See the [Linux CD-ROM userspace API](https://docs.kernel.org/userspace-api/ioctl/cdrom.html).

## Unraid / Portainer one-drive test

**Keep your existing Portainer stack, its volumes and custom `br0` network/IP unchanged.** Update only these sections of its OSCAR service:

```yaml
services:
  oscar:
    image: ghcr.io/sin7ek/oscar:main
    environment:
      OSCAR_CONFIG_PATH: /config/settings.json
      OSCAR_ENABLE_MEDIA_PROBE: "1"
    devices:
      - /dev/sr2:/dev/sr2:r
    group_add:
      - "${OSCAR_OPTICAL_GID}"
```

`OSCAR_OPTICAL_GID` must be defined as a Portainer **stack environment variable** with the numeric group ID that grants read permission to `/dev/sr2`. Determine it on Unraid:

```bash
ls -l /dev/sr2
stat -c 'device=%n owner=%u group=%g perms=%a' /dev/sr2
```

For example, if the owner/group/mode is `root:cdrom 660`, use the numeric group ID from `stat`. **Do not assume group 24**. The image runs as a non-root `oscar` user. If host permissions are more restrictive, stop and assess rather than grant full privileged Docker access.

`/dev/sr2` is an ephemeral kernel identifier: before each deployment confirm that it still resolves to the Optiarc AD-7200S. Compose `devices:` is evaluated when creating a container, so unplugging/reconnecting or adding more drives may require a controlled redeploy. Automatic discovery in the GUI is separate from Docker device permissions.

The existing `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, `/config` persistent mount and sysfs/udev read-only mounts should all remain. **Do not mount the music Archive yet.**

## Try it
1. Deploy a new build only after its Docker publishing workflow succeeds on `main`.
2. In the GUI select and enable **Optiarc**, then **Save settings**.
3. With no disc, click **Check inserted discs** and note the result.
4. Insert a **test CD** and click again. Expect `disc_present` and hopefully `audio`; some drives may return `unknown` for the disc type.
5. Copy `GET /api/media` JSON and logs into issue #1 (without personal/private filenames).

There is no automatic polling yet; a status request occurs only when a user clicks the button.

## Security
This API is not authenticated yet. Run only on a trusted LAN or behind authentication. Status requests can briefly activate/spin optical media, and the drive should not be simultaneously accessed by a different ripper.
