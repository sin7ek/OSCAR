# OSCAR
**Open Source CD Archiving & Ripping**

*Preserve every note.*

Automated, archival-grade CD ripping with AccurateRip/CTDB verification, MusicBrainz metadata, FLAC, CUE sheets, and classical music support.

> Dedicated to Oscar, whose love of music inspired this project.

## Status
**v0.1.0-alpha: architecture and read-only API scaffold only.** Ripping, device access, publishing and cleanup are **not yet implemented**. AccurateRip/CTDB integrations must be proven on hardware before claims of verified operation.

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

For a new development session, start with the living [Project status and handoff](docs/PROJECT_STATUS.md), then [Architecture](docs/ARCHITECTURE.md), [Metadata retry queue](docs/METADATA_QUEUE.md) and [Milestone 01](docs/MILESTONE_01.md).

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
