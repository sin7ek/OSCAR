# OSCAR — initial architecture

## Design goal
A verification-first, open-source CD archival orchestrator for Unraid/Linux, including metadata-rich classical collections.

## Processing pipeline
1. **DISC_DETECTED** — identify optical drive and disc TOC (disc ID, sessions, indices, drive offset).
2. **RIPPING** — read the disc with an established secure ripper into immutable staging; capture raw log and CUE.
3. **VERIFYING** — collect track and disc evidence: AccurateRip v1/v2, CTDB, secure-read reports, FLAC decode and hashes.
4. **IDENTIFYING** — query MusicBrainz by disc ID, then discriminate physical editions by barcode, label/catalog number, artwork and performer/recording relationships.
5. **AWAITING_REVIEW** — request human selection when evidence is ambiguous, especially for classical releases and multi-disc boxsets.
6. **READY_TO_ARCHIVE** — validate CUE references, file counts, tags, checksum manifest, source provenance and destination collision safety.
7. **ARCHIVED** — atomically promote staged copy, then re-verify published files.
8. **CLEANUP_ELIGIBLE** — only when publication and verification passed; delayed cleanup is a separate explicit action.

## Non-negotiable distinctions
- **Audio quality / rip verification** and **metadata / release certainty** are independent.
- AccurateRip not found is **not** AccurateRip mismatch.
- CTDB-confirmed audio may be valid even with an AccurateRip mismatch; document each result.
- Matching repeated local rips is not independent verification.
- A correct MusicBrainz disc ID can still identify several physical editions.
- Preserve original CUE and original rip logs; write a playable CUE separately.
- Preserve pregap / INDEX 00 information where hardware allows; never imply HTOA was captured if not.
- Audio checksums must remain stable across metadata/artwork changes.

## Components (planned)
- **API/UI:** FastAPI; review dashboard and progress.
- **Drive worker:** discover devices and drive capabilities; one job per drive.
- **Rip adapter:** cyanrip candidate; feasibility and reproducibility tests before selection.
- **Verification adapter:** AccurateRip plus independent CTDB tool (Linux feasibility to be validated).
- **Metadata adapter:** MusicBrainz/Cover Art Archive; support classical work/movement/performance relationships and multi-disc releases.
- **Publisher:** stage copy, manifest and SOURCES.txt, checks, atomic promotion, cleanup controls.
- **State:** persistent SQLite jobs and event records, resumable state transitions.

## Unraid safety
- Initially mount the existing Archive **read-only**.
- Do not grant the development container Docker socket access.
- Do not expose optical hardware until explicit drive-read tests.
- Do not add automatic deletion or overwrite endpoints before acceptance testing.
- Keep hardware-specific config (drive offset, paths) outside version control.

## Early tests
Reuse documented reference cases:
- Ruffneck Collection Part VI: track 17 AccurateRip mismatch, CTDB match.
- Ruffneck Collection Part VIII: no AccurateRip entry, CTDB 19/19.
- The Origin Of Core – Datafile I: two-disc, scratched source and replacement provenance.
- Classical sample: multiple possible release matches and work/movement performers.
