# OSCAR — Development progress dashboard

**Last assessed:** 2026-11-19  
**Assessment type:** qualitative estimates by the project team / ChatGPT, **not measured engineering KPIs**.  
**Canonical status and evidence:** [PROJECT_STATUS.md](PROJECT_STATUS.md)  
**Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)

> This dashboard tracks implementation maturity toward the eventual **insert CD → Go** experience. The percentages are subjective progress estimates, not test pass rates, promises or objective milestones. Passing CI does not mean a feature has been accepted on real Unraid hardware. Do not calculate a single overall project completion percentage from these different domains.

## Progress by area

| Area | Progress | Visual progress | Evidence / remaining gaps |
|---|---:|---|---|
| CD ripping on Unraid | **90%** | `█████████░` | Multiple optical drives and successful physical rips; unattended detection and recovery remain |
| FLAC & staging verification | **85%** | `████████▌░` | FLAC decode, SHA-256, CUE and cyanrip evidence; independent verification is separate |
| MusicBrainz & release selection | **75%** | `███████▌░░` | Risk-based Disc ID candidate inspection and catalog conflict prompts; persistent evidence-backed auto-approval still missing |
| Classical metadata | **70%** | `███████░░░` | Works, performers and multidisc review; further edge cases remain |
| Archive publishing | **85%** | `████████▌░` | Anastacia published; new read-only auditor tested on Unraid with expected legacy evidence warning; source-evidence embedding still awaits hardware acceptance |
| Independent AccurateRip / CTDB | **20%** | `██░░░░░░░░` | Cyanrip AccurateRip evidence is parsed; no independent full verification engine |
| Automatic end-to-end workflow | **30%** | `███░░░░░░░` | Best Guess / Secure preference UI and persistence added; no unattended tagging/archive orchestration yet |
| Recovery, resume & cleanup | **20%** | `██░░░░░░░░` | Delayed cleanup, crash recovery and safe resume remain major work |

### Bar chart

This Mermaid chart uses the same baseline estimates as the table above (scale 0–100). The table is the accessible fallback when a GitHub client does not render Mermaid charts.

```mermaid
xychart-beta
    title "OSCAR development maturity estimates — 2026-11-19"
    x-axis ["Ripping", "FLAC staging", "MusicBrainz", "Classical", "Publishing", "AR/CTDB", "Automation", "Recovery"]
    y-axis "Estimated progress (%)" 0 --> 100
    bar [90, 85, 75, 70, 85, 20, 30, 20]
```

## How to update this living dashboard

1. **At every meaningful feature PR:** review impacted percentages, the supporting evidence and remaining gaps alongside [PROJECT_STATUS.md](PROJECT_STATUS.md). A PR should link both documents when it changes a roadmap domain.
2. Update **the table, text bars, Mermaid chart and date together**. If estimates do not change, explicitly record *reviewed, no percentage change* in the PR summary rather than raising numbers just because code merged.
3. Only count **Unraid hardware acceptance** when it was actually completed; differentiate *implemented*, *CI passed*, *Docker image built*, *hardware tested* and *operationally proven*.
4. Require a brief explanation when an estimate changes (new verified behavior, reduced risk, regression or changed scope). Percentages may go **down** when new gaps are discovered.
5. Do not treat this as an automatic performance gauge. Until metrics are instrumented, **values are editorial judgments**, maintained with code/documentation changes rather than dynamically derived from CI.
6. Never confuse a successful `flac -t` or a cyanrip log claim with an **independent AccurateRip/CTDB verification**.

## Assessment log

| Date | Change | Evidence |
|---|---|---|
| 2026-11-19 | Reassessed after PR #58 configuration UI (Best Guess / three Secure review levels); no percentage change because execution policies and unattended orchestration remain future work. | Settings migration/validation tests and [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 2026-11-19 | Reassessed after risk-based physical edition candidate UI; percentages unchanged pending Unraid testing and server-enforced approval evidence. | Unique candidates inspected read-only; ambiguous candidates prompt for catalog; see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 2026-11-19 | Reassessed; no percentage change. PR #52's archive-audit CLI ran on real Unraid: 1 album, 12 FLACs, PASS_WITH_WARNINGS (expected EVIDENCE_NOT_EMBEDDED). Source-evidence embedding from PR #51 and independent CTDB are still untested. | User's terminal output of `docker exec oscar python -m oscar.archive_audit /archive`; [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 2026-11-19 | Initial baseline: 90 / 85 / 75 / 70 / 85 / 20 / 30 / 20 | Physical multi-drive tests, verified Anastacia archive publishing (PR #50), source evidence preservation (PR #51, CI-tested), read-only archive auditor (PR #52, CI-tested), documented in [PROJECT_STATUS.md](PROJECT_STATUS.md) |

## Track-level collection evidence + Go! roadmap (PR #62)

Source-backed track/credit/Work indexes and a strictly exact-release+catalog MusicBrainz label-backfill action have been added to the collection workflow. **No completion-percentage increase yet:** CI and actual Unraid verification are separate; a persistent per-disc controller and safe metadata decision engine are not implemented. The next development priority is [AUTOMATION_ROADMAP.md](AUTOMATION_ROADMAP.md), not continued collection UI polish.

## Nextcloud-compatible exports and classical album discovery (PR #61)

Adds XLSX download plus read-only album-level search/sort by label and classical performers; safe in-place SQLite migration, and explicit label evidence recorded in *future* publication manifests. Track-level classical Work/Soloist tables, independent backfill of old label metadata and remote Discogs collection writes are still missing. Do **not** inflate existing percentages until CI, actual Unraid import and Nextcloud editor checks.

## Phase 1 collection catalog progress (PR #60)

Local database of OSCAR published archives, ODS/CSV export, sortable UI, read-only Discogs PAK identity/folder access and fixed metadata rip attribution are implemented in code. These do not yet provide a comprehensive physical ownership database, remote collection write, edition matching or automatic workflow. Keep all existing qualitative percentages unchanged pending CI and real Unraid acceptance.

## Proposed collection management extension

[Discogs and OSCAR local catalog design](DISCOGS_COLLECTION_CATALOG.md) covers secondary physical-edition discovery, optional collection sync, condition/sleeve/notes/folder entry, per-copy identity and sortable **ODS-first** export. **Design only: no implementation or progress-percentage change** until concrete features and tests exist. The eight existing maturity estimates remain unchanged.

## Development priorities

- Test PR #51 embedded extraction evidence in a *new* archive publication; PR #52's initial read-only audit has now passed on real Unraid for Anastacia.
- Add archive audit results to the web UI without overstating verification.
- Investigate independent AccurateRip/CTDB checks and source confidence.
- Build resumable workflow orchestration and safe, evidence-based automatic progression.
- Allow conservative, explicit cleanup only after proven archival integrity.

*This is a planning aid, not a substitute for releases, CI logs, actual test reports or documented source evidence.*
