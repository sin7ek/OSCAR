# OSCAR
**Open Source CD Archiving & Ripping**

*Preserve every note.*

Automated, archival-grade CD ripping with AccurateRip/CTDB verification, MusicBrainz metadata, FLAC, CUE sheets, and classical music support.

> Dedicated to Oscar, whose love of music inspired this project.

## Status
**v0.1.0-alpha: read-only metadata scaffold plus an opt-in experimental cyanrip staging rip.** This prototype can extract a test CD only after explicit configuration and confirmation, into a newly created staging directory. No independently verified archive, publishing, or cleanup is implemented. AccurateRip/CTDB evidence must be proven on hardware before claims of verified operation.

## Goals
- Detect audio CDs, record drive identity, read offset and table of contents (including pregaps and HTOA capability).
- Rip lossless FLAC using a proven secure ripping engine (cyanrip is a candidate).
- Verify audio using AccurateRip v1/v2, CTDB (tooling feasibility to be established on Linux), FLAC decoding, hashes and rip logs.
- Identify the **specific physical release** using MusicBrainz disc IDs, barcode, label/catalog numbers and artwork.
- Support classical works, movements, composers, conductors, orchestras, performers and multidisc boxsets.
- Produce preserved original CUE information, usable FLAC CUE sheets, `SOURCES.txt` and structured `manifest.json`.
- Stage, review, archive and clean up without ever risking an existing collection.

## Safety principles
1. Keep source audio and original logs immutable; metadata edits occur only on staged copies.
2. Audio-verification status and physical-release identification status are independent.
3. No AccurateRip/CTDB entry is **unverified**, not a mismatch.
4. A database match does not prove a particular physical release.
5. Do not publish ambiguous metadata or failed rips automatically.
6. No destructive cleanup without confirmed archival integrity; cleanup is initially disabled.
7. Never automatically move or rewrite an existing Archive.

## Development
Python 3.11+:
```bash
python -m pip install -e '.[dev]'
python -m pytest -q
uvicorn oscar.api:app --host 127.0.0.1 --port 8080
```
The `/health` endpoint reports **scaffold status only**; it does not detect discs.

For a new development session, start with [Project status and handoff](docs/PROJECT_STATUS.md), then [Architecture](docs/ARCHITECTURE.md), [Metadata retry queue](docs/METADATA_QUEUE.md), [First experimental rip](docs/FIRST_RIP_STAGING.md), and [Milestone 01](docs/MILESTONE_01.md).

## Experimental rip token (Unraid / Portainer)

The experimental cyanrip staging rip requires an explicitly configured secret
token. Generate one on the Unraid host with:

```bash
openssl rand -hex 32
```

This produces 32 random bytes as 64 hexadecimal characters. Store the result
as the `OSCAR_RIP_TOKEN` stack environment variable in Portainer. Reference
the variable in the existing compose definition without committing the secret:

```yaml
environment:
  OSCAR_ENABLE_RIPPING: "1"
  OSCAR_RIP_ROOT: /staging
  OSCAR_RIP_TOKEN: ${OSCAR_RIP_TOKEN}
```

These lines illustrate the relevant settings, not a replacement stack.
Keep your existing configuration, persistent `/config`, device mappings,
and the isolated `/mnt/user/ai-workspace:/staging:rw` mount.
The token is requested by the test-rip UI and is not a hash of a password.
Environment values can be read by people with Docker/Portainer admin access;
do not paste the token into GitHub, issue reports or screenshots. The app has
no built-in user login, so restrict network access as well.

See [First experimental rip](docs/FIRST_RIP_STAGING.md) for prerequisites,
permissions, logging, and safe staged output.

## Target archive layout
```text
Archive/<label>/[catalog] <release title> (<year>)/
  *.flac
  album.cue
  original-ripper.cue
  folder.jpg
  SOURCES.txt
  manifest.json
  Verification/
```
This is a proposed layout, not a deployed configuration.

## License
MIT — see [LICENSE](LICENSE).
