# OSCAR — Developer handoff

**Matrix/runout:** MusicBrainz release-annotation search and optional disc-level operator transcription are available in the [archive publishing workflow](ARCHIVE_PUBLISHER.md). A new tagged copy carries `MATRIX_RUNOUT` through to the publication preview, archived `SOURCES.txt` and manifest. Tower acceptance is pending.

Last reconciled 2026-11-22 through feature PR [#140](https://github.com/sin7ek/OSCAR/pull/140) and open PR [#139](https://github.com/sin7ek/OSCAR/pull/139). Read the [work document](PROJECT_STATUS.md) for evidence and project decisions and the [dashboard](PROGRESS.md) for test and deployment status.

## Build and deployment

- DriveFit [#140](https://github.com/sin7ek/OSCAR/pull/140) is merged as `5368f6489da5755fe7fb53f99c41d0af7d01b17d`. [Python Tests](https://github.com/sin7ek/OSCAR/actions/runs/45072660464) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45072660444) passed. The GHCR `main` Linux/amd64 image's OCI revision was checked against that merge. The Tower pull and DriveFit acceptance have no recorded result.
- [#138](https://github.com/sin7ek/OSCAR/pull/138) is merged and included in that image. It renders the proposed and published `SOURCES.txt` from the same logic and preserves per-track recovery origin plus independent verification evidence. Tower preview and new publication remain open.
- [#139](https://github.com/sin7ek/OSCAR/pull/139) is open with green PR CI. It adds details for both the selected diagnostic and excluded original attempts to new recoveries, with an explicit missing-history marker for older jobs. It is outside the #140 image. See [archive publishing](ARCHIVE_PUBLISHER.md).

## Tower acceptance already recorded

| Fixture | Observed result | Acceptance boundary |
| --- | --- | --- |
| Carmen Gomes Inc. — *Desire* | Single-CD revision and subsequent read-only Verify passed. 12 revised tracks and 12 retained originals, approved catalog `CGi2010` and label `CFMusic`, Collection and CUE/evidence checked. | Full rescan, restart, and controlled interruption are separate checks. Collection remains Unclassified without GENRE. |
| Anastacia — *Freak of Nature* | Both journal entries Verify as `VERIFIED` after [#120](https://github.com/sin7ek/OSCAR/pull/120), including the superseded generation. Collection refresh showed Pop / Popular, 12 tracks, `published_verified`. | Historical generations remain retained. Collection display alone does not establish per-file GENRE inspection. |
| *Boulez Conducts Stravinsky*, 6 CDs | Initial preview saw only CDs 4/6 and 6/6. Later all six were present. Coordinated LABEL Apply revised CDs 4 and 6 only, 39 tracks across group `7e20981bad8a4145bc7e3ad6d9cecd61`. Read-only Verify returned `Integrity PASS`; 90/90 labels reported correct across the box. | This covers LABEL and the observed group integrity check. Multidisc GENRE Apply, interrupted-group recovery and archive cleanup remain separate. |
| Mahler / Bernstein — *The Symphonies*, 2010 DG, Disc 11 | Recovery job `3c13772b6d104964ac71eb19e881668b` reached Go! Archive Review after [#136](https://github.com/sin7ek/OSCAR/pull/136). Optiarc job `26766340b2a04813a27d6081f8eff3c1` provided 16 tracks and LG diagnostic job `033f1207b6ba4184b7130e20ff75b181` provided Track 07. OSCAR reported 17/17 independent AccurateRip v1 and v2 matches and CUE/SHA-256 checks. Archive Review showed 17 tagged tracks. | Physical edition remains `INFERRED`. Separate source-file inspection, the new SOURCES preview, and publication remain open for this disc. |

See [#116](https://github.com/sin7ek/OSCAR/pull/116) and [#137](https://github.com/sin7ek/OSCAR/pull/137) for the documented Boulez and recovery results. The work document keeps exact job IDs, accepted values and the historical sequence.

## Next on Tower

1. Open **DriveFit** on the #140 image. Check real per-drive samples and normalized GH42 speed. In the LG diagnostic drive history look for Mahler Disc 11 Track 07 while its staging evidence exists. See [DriveFit](DRIVEFIT.md) for thresholds and the limits of historical data.
2. Open the recovered Disc 11 in **Go! → Archive Review → Proposed SOURCES.txt** on the same image. Check Track 07 for the LG source, the other 16 for Optiarc, and independent `trackverify` attribution. Publication requires separate physical-edition review and explicit approval. The physical box is catalog `477 8668` / `00289 477 8668`; distinguish its barcode from a per-disc MCN. Track attempt details from #139 require that PR to ship and may need a fresh recovery fixture.
3. Keep the remaining real-hardware checks separate: per-drive ETA, tracked Go jobs, supported Eject/Close and confirmed Stop, refreshed Go metadata-copy adoption, genre-source comparison and coordinated GENRE Apply. The successful LG selected-track extraction covers that part of #132.

## Project workflow

- Start a new OSCAR development chat with this document from GitHub, then read [PROJECT_STATUS.md](PROJECT_STATUS.md), [PROGRESS.md](PROGRESS.md), the active technical docs and actual `main`/PR state. The repository is [sin7ek/OSCAR](https://github.com/sin7ek/OSCAR).
- Use a branch, focused tests and a PR. For a requested Tower-ready code change, follow required CI, fix failures, merge after green checks and verify `ghcr.io/sin7ek/oscar:main` against the merge revision before saying the operator can pull. A PR-only or review request stays open. Track operator pull and real Tower acceptance separately.
- Update the work document, dashboard and handoff with each relevant milestone or acceptance result. Place technical audit history in the work document. Preserve original extraction and archived generations. A matching Disc ID or passing audio verification does not prove the physical edition. Archive mutations require operator opt-in. Keep credentials out of GitHub.
- Technical starting points include the [archive metadata lifecycle](ARCHIVE_METADATA_LIFECYCLE.md), [multidisc revisions](MULTIDISC_ARCHIVE_REVISION.md), [genre evidence](GENRE_EVIDENCE_V1.md) and the [automation roadmap](AUTOMATION_ROADMAP.md). The example Unraid Compose is still a draft and a reviewed Getting Started guide remains open.
