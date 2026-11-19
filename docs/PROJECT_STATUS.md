# OSCAR — project status and handoff

**Last reviewed:** 2026-11-19  
**Repository:** https://github.com/sin7ek/OSCAR  
**Purpose:** Open Source CD Archiving & Ripping — archival-grade, verification-first CD digitization for Unraid/Linux, with classical-music metadata and an eventual **insert CD → Go** workflow. Dedicated to Oscar.

> **How to resume after a chat ends:** Read this document first, then `docs/ARCHITECTURE.md`, `README.md`, recent merged PRs and open PRs, and GitHub Actions for the branch under development. Do not infer that a successful CI run establishes real optical hardware functionality.

## Current implementation (v0.1.0-alpha)

- Read-only FastAPI/HTML UI for enabled optical drive configuration, device probing and TOC / MusicBrainz Disc ID inspection, subject to opt-in flags and hardware/container permissions.
- MusicBrainz release candidate discovery; exact Disc ID + track count medium matching, including multidisc editions. Physical edition still requires human confirmation.
- Verified MusicBrainz artist/work relationships for composers, work hierarchies, conductors, orchestras and performers. Do not infer role from generic artist credits.
- Original-language names preserved with MusicBrainz English aliases (no machine translation). Composer/work aliases automatically deduplicated and cached in SQLite at `/config/aliases.sqlite3`. Positive TTL 30 days, negative TTL 7 days.
- PR #16: cooldown and stale fallback after persistent alias API failures.
- PR #17: shared single-process MusicBrainz transport across Disc ID / release medium / alias lookups, 1.1 s spacing, bounded retries, optional Retry-After and temporary circuit-breaker.
- PR #18: enrich conductor/orchestra/soloist names in the tracklist with the same artist alias mechanism, preserving roles and instrument attributes (merged).
- PR #19: persistent MusicBrainz artist/work alias retry queue (merged), SQLite-backed deduplicated jobs for transient artist/work alias errors, exponential backoff, crash-recoverable leases and an optional single worker activated by `OSCAR_ENABLE_METADATA_WORKER=1`. `GET /api/metadata-queue` reports status. Unit-tested without hardware.

- Experimental staging rip prototype (current feature PR): explicit opt-in, token-protected cyanrip FLAC extraction, drive identity/offset validation, new UUID staging folder, captured console logs, file hashes and no automatic archive operations. Documented at [FIRST_RIP_STAGING.md](FIRST_RIP_STAGING.md). First Unraid test reached cyanrip but failed immediately due to unsupported `-B`; see [FIRST_RIP_STAGING.md](FIRST_RIP_STAGING.md).

- Archive naming preview feature in progress: read-only `/api/archive/name-preview` for album, compilation and classical paths, catalog-number prefix and optional reviewed conductor/ensemble suffix (see [ARCHIVE_NAMING.md](ARCHIVE_NAMING.md)). No file operations; pending CI and manual UI integration.

- Drive-offset assistant (pending CI): AccurateRip web lookup for detected model with conservative/conflict-aware suggestions, optional user-triggered cyanrip `-f` reference-CD calibration, external manual fallback URL. Only prefills a blank offset in the browser and requires Save settings; existing offsets never overwritten automatically. GH24NS95 has conflicting database rows (+6 vs +667) and must be reviewed. See [DRIVE_OFFSET.md](DRIVE_OFFSET.md).

- Staging verification report (feature in progress): explicit, token-protected per-job verification with cyanrip's recorded AccurateRip v1/v2/EAC CRC32 evidence, per-FLAC SHA-256 rehash and FLAC decoding, CUE file-reference check, log ripping errors and a per-track web table. Persists only a new `verification-report.json`, never modifies staged audio or promotes it. See [STAGING_VERIFICATION.md](STAGING_VERIFICATION.md). Hardware retest against the first 28-track reference job still needed.

**Not implemented:** full unattended CD ripping, independent AccurateRip/CTDB verification, verified CUE and FLAC decode checks, full archive-quality tags, final archive promotion, full release/Disc ID background queueing, or automatic cleanup. The new queue retries only artist/work alias enrichment; deployment requires opting in to the worker. Metadata review does not validate extracted audio.

## Decisions / invariants

1. Audio integrity and physical edition certainty are independent.
2. Retain original rip logs and CUE; never claim INDEX 00 or HTOA detection from a basic TOC.
3. Original names, entity IDs and verified MusicBrainz relationship provenance must remain intact; English aliases are additional display metadata.
4. Missing English alias (`EN —`) is not a failure; transient failure (`EN ↻`), stale alias (`EN ~`) and other lookup error (`EN !`) are separate states. `EN ✓` is an English alias.
5. One CD may correspond to multiple editions; do not silently auto-select without adequate physical evidence.
6. Never overwrite or delete existing music files from prototype endpoints; initial Archive access read-only.
7. Shared MusicBrainz limiter is **process-local only**; concurrent workers or multiple OSCAR installations require a cross-process/host-wide rate limiter before scaling.
8. SQLite alias cache and retry queue are distinct: `/config/aliases.sqlite3` holds resolved aliases; `/config/metadata_queue.sqlite3` holds transient artist/work retry tasks. A cross-process, cross-container IP-wide MusicBrainz rate limiter remains future work.

## Real-world manual checks (not automated acceptance tests)

- **Händel:** `Water Music / Music for the Royal Fireworks`, Jordi Savall, Le Concert des Nations, Astrée Auvidis ES 99220 (1999). Physical CD on an enabled drive; Disc ID `ROkQlooU5tDdgVZOkfXXTy.S4oU-`, 28 tracks, 1 candidate and exact medium+track-count match. Earlier API returned repeated HTTP 503 during alias lookups. Work groups/composer/roles visible; some EN errors and in-progress entities at capture time.
- **Tchaikovsky:** `Symphony no. 5 in E minor, op. 64 / Capriccio Italien, op. 45`, Gennady Rozhdestvensky / London Symphony Orchestra. 5 tracks, exact disc and track-count match, 4 symphony movements correctly grouped, Capriccio separate. Alias processing reported 6 resolved, 0 pending/errors; composer displayed as original Cyrillic + Pyotr Ilyich Tchaikovsky, but conductor stayed Cyrillic. This motivated automatic performer alias enrichment.
- **Stravinsky:** earlier classical sample used to check language aliases and recording/work relationships.
- **First real cyanrip invocation on Optiarc AD-7200S (2026-11-18):** `/dev/sr2`, offset +48, MusicBrainz Disc ID `sT6cTPp0_qZRfvu1jHQ8VBNx.X4-`, 32 tracks. Staging folder created but cyanrip returned 1 with `invalid option -- 'B'`. No audio extracted. Fix under PR for CLI compatibility; do not mark this as a completed rip.
- **First complete hardware rip — 2026-11-19:** Händel *Water Music / Music for the Royal Fireworks* (Jordi Savall), Disc ID `ROkQlooU5tDdgVZOkfXXTy.S4oU-`, drive `ata-HL-DT-ST_DVDRAM_GH24NS95_KRQCCM33843`, staging job `f41806152a614b1a9006b10456b9bbd4`. cyanrip exit code 0, `status=needs_verification`, 28/28 FLAC files with recorded SHA-256 hashes, ripping errors 0, console log reports 28/28 tracks accurately ripped with AccurateRip v1 and 28/28 with v2 (confidence varies). User independently ran `flac -t --silent` on all 28 files, which passed, and confirmed a ~3.0 KB CUE file. **Boundary:** this verifies the experimental pipeline and checks on hardware; OSCAR does not yet parse/report verification per track, independently query AccurateRip/CTDB, or archive/publish files. Do not delete staging evidence.
- **Initial verification-engine regression (2026-11-19):** First run on the completed 28-track Händel staging job returned `review_required` solely because the saved cyanrip-console.log exceeded the old 6 MB guard. No FLAC failure was reported. PR follow-up streams the verbose log, keeps only proof lines for analysis, and permits retry of incomplete failed reports without reripping; original failed report is retained as history. Actual post-deploy retest pending.
- **First successful real-world OSCAR verification report — 2026-11-19:** After streaming-log fix PR #26, the original Händel/Jordi Savall staging job `f41806152a614b1a9006b10456b9bbd4` returned `checks_passed`: 28/28 FLAC, SHA-256 rehashes and FLAC decoder checks passed, 28/28 cyanrip-reported AccurateRip v1 matches (confidence 25–27), 28/28 v2 matches (confidence 47–50), CUE references match, and ripping errors 0. This proves the on-hardware end-to-end staged extraction and post-rip verification report workflow. AccurateRip evidence is transcribed from cyanrip (not independently queried), and CTDB, physical-release approval, tagging, and archive publishing remain unimplemented. Preserve the staging files.
- **Safety note:** these checks concern metadata identification only, not secure ripping or AccurateRip validation.

## Next steps in priority order

1. Confirm PR #18 merged after CI; deploy newly built `ghcr.io/sin7ek/oscar:main` to Unraid and re-test Tchaikovsky conductor spelling against real MusicBrainz alias availability.
2. Validate the metadata retry queue on Unraid with `OSCAR_ENABLE_METADATA_WORKER=1`; then extend queue to Disc ID/release lookups, add cancellation and per-task progress in the GUI. Never block rip verification on MusicBrainz.
3. Validate archive naming preview on single-composer and mixed-composer classical CDs; refine album/work/movement/performer tag plan, catalog numbers, collision checks and correct boxset disc numbering; maintain source provenance.
4. Test the experimental cyanrip staging rip on one real optical drive using /mnt/user/ai-workspace only; inspect CLI log, CUE/FLAC output and drive permissions; no archive access.
5. Exercise the staging verification report on the original 28-track Handel reference job; implement independent AccurateRip/CTDB verification later, including confidence provenance and FLAC integrity. Logged cyanrip matches are strong evidence, but not an independent OSCAR database query.
6. Implement staged, collision-safe archive publication with a manifest and conservative cleanup policy.
7. Test unattended insert→Go workflow only after the above has proven safe.

## Deployment and safety reminders

- Repo: `sin7ek/OSCAR`; CI uses GitHub Actions; image: `ghcr.io/sin7ek/oscar:main` after successful publish.
- Main working environment: Unraid + Portainer; current pilot uses optical drive `/dev1` as shown in GUI (verify the underlying stable drive ID; do not assume Linux device path `/dev1`).
- `/config` is persistent; keep credentials/private device settings out of GitHub. UI does not have built-in authentication. Preserve both alias and queue SQLite files across updates. Set `OSCAR_ENABLE_METADATA_WORKER=1` in the existing Portainer stack to enable automated retries after a new deployment.
- Experimental test output host path: `/mnt/user/ai-workspace` -> container `/staging` (opt-in RW mount). See [first rip instructions](FIRST_RIP_STAGING.md). No existing music share mounted writable.
- Existing `compose.preview.yml` is a conservative template, not necessarily the full running Portainer stack. Do not replace live stack mounts/flags without comparing them.
- Test locally with `python -m pytest -q` and observe GitHub Actions before merge.
- Keep this handoff updated in every major feature PR with **implemented**, **tested in CI**, **tested on hardware**, **known limitations**, and **next steps**.

## Useful links

- [Repository](https://github.com/sin7ek/OSCAR)
- [Pull requests](https://github.com/sin7ek/OSCAR/pulls)
- [GitHub Actions](https://github.com/sin7ek/OSCAR/actions)
- [Architecture](ARCHITECTURE.md)
