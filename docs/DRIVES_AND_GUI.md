# GUI: optical drive settings (prototype)

The settings page is available on `/`, the API on `/api/settings` and the read-only inventory on `/api/drives`.

## Reference devices (Unraid, 2026-11-18)

| Device | Stable /dev/disk/by-id name | Firmware |
|---|---|---|
| LG GH24NS95 | `ata-HL-DT-ST_DVDRAM_GH24NS95_KRQCCM33843` | RN00 |
| Optiarc AD-7200S | `ata-Optiarc_DVD_RW_AD-7200S` | 1.06 |
| HP DH16AAL | `ata-hp_DVD_A_DH16AAL_2B9950003803` | LHDE |

Do **not** persist `/dev/sr1` etc. as canonical identity: kernel numbering changes. The Optiarc by-id name lacks a serial, so confirm uniqueness when more than one identical drive is present.

## Deployment constraints
- Set `OSCAR_CONFIG_PATH=/config/settings.json` and bind-mount a persistent appdata directory at `/config`.
- For *read-only inventory*, expose host `/dev/disk/by-id` as appropriate; symlinks may resolve outside a container unless underlying nodes are also visible. Until device passthrough is set up, inventory can report 'not detected'; settings are still editable.
- Do **not** expose this prototype UI to the internet. Use localhost or authenticated reverse proxy when deployed.
- No device reads, rip commands, archive writes or cleanup actions are implemented in this milestone.
- User-configured offsets are not validated against physical drive capabilities. Unknown should remain blank until calibration.
- Hardware profile and rip-routing configuration will be extended after real-drive tests.
