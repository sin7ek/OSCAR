# OSCAR — Developer handoff

Last reconciled 2026-11-23 through the Collection edition fix [#157](https://github.com/sin7ek/OSCAR/pull/157) and archive date and country revisions [#158](https://github.com/sin7ek/OSCAR/pull/158) and open PR [#139](https://github.com/sin7ek/OSCAR/pull/139). Read the [work document](PROJECT_STATUS.md) for evidence and project decisions and the [dashboard](PROGRESS.md) for test and deployment status.

## Build and deployment

- [PR #154](https://github.com/sin7ek/OSCAR/pull/154) archives edition search evidence in SOURCES.txt and the manifest. [PR #155](https://github.com/sin7ek/OSCAR/pull/155) shows the historical DriveFit labels on Go! drive cards. Python Tests and Docker build passed for both PRs. The Linux/amd64 `ghcr.io/sin7ek/oscar:main` OCI revision matched merge `d415045d2497548fd92e5b179b2b58a3ec7199c6` at manifest digest `sha256:1787063c75fe98df4b942286e82b0808cb36981ac7afc88b1380ac15cf93800b`. Live Tower checks remain open.
- [PR #151](https://github.com/sin7ek/OSCAR/pull/151) expands Discogs coverage and shows release country disagreements. Python Tests and Docker build passed. The Linux/amd64 `ghcr.io/sin7ek/oscar:main` OCI revision matched merge `9678bd5767960468cf9f65de8af94dc1e8f850b0` at manifest digest `sha256:a41bdd7f6832b480290441092ed298b650b4d8afa76fed8d996ffe339cfdce43`. Tower Équinoxe search and evidence display passed.
- [PR #149](https://github.com/sin7ek/OSCAR/pull/149) adds display-only rip working titles and integrated MusicBrainz/Discogs edition review. Python Tests and Docker build passed. The registry Linux/amd64 image `ghcr.io/sin7ek/oscar:main` reports revision `db0df556f9743d0b02c0f13a86e5ee205d80ba08` at digest `sha256:d44a401ad2d106340ebc637d420e24aaa47604bbe147a42d8dec46e47d4b15bf`. Live Tower acceptance remains open.
- [PR #145](https://github.com/sin7ek/OSCAR/pull/145) ships independent, operator-triggered CTDB verification and read-only Discogs pressing comparison. PR Tests and Docker build passed. The Linux/amd64 `ghcr.io/sin7ek/oscar:main` OCI revision matched merge `ca4bfe47ad3e6cacd232c0d5448417300da8619c` at manifest digest `sha256:8ba24a6c041843fb48f3557eaf627df1808d531e548922acaecd99bdab184f7d`. A live lookup with a two-track test signal produced the expected CTDB no-audio-match result (`0/1`). Known-good audio and Discogs variant acceptance on Tower are pending.
- Matrix/runout [PR #142](https://github.com/sin7ek/OSCAR/pull/142) adds annotation search and operator transcription in FLAC tags and archive evidence. [PR Tests](https://github.com/sin7ek/OSCAR/actions/runs/45077525913), [PR Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45077525924) and the [main image build](https://github.com/sin7ek/OSCAR/actions/runs/45077599992) passed. The registry's Linux/amd64 `ghcr.io/sin7ek/oscar:main` OCI revision was checked against merge `cfd01bf79b079b88aa28bf008b066fbac406e308` at manifest digest `sha256:b88d8607e6337987a77ca3494f79d24b69de4cc5aed4b25e8342ff0e63ef9aea`. Tower manual preview and copy creation passed.
- DriveFit [#140](https://github.com/sin7ek/OSCAR/pull/140) is merged as `5368f6489da5755fe7fb53f99c41d0af7d01b17d`. [Python Tests](https://github.com/sin7ek/OSCAR/actions/runs/45072660464) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45072660444) passed. The GHCR `main` Linux/amd64 image's OCI revision was checked against that merge. The Tower pull and DriveFit acceptance have no recorded result.
- [#138](https://github.com/sin7ek/OSCAR/pull/138) is merged and included in that image. It renders the proposed and published `SOURCES.txt` from the same logic and preserves per-track recovery origin plus independent verification evidence. Tower preview and new publication remain open.
- [#139](https://github.com/sin7ek/OSCAR/pull/139) is open with green PR CI. It adds details for both the selected diagnostic and excluded original attempts to new recoveries, with an explicit missing-history marker for older jobs. It is outside the #140 image. See [archive publishing](ARCHIVE_PUBLISHER.md).

## Tower acceptance already recorded

On Tower, the manual Metadata & tagging preview for *Jagged Little Pill* showed the operator-transcribed `MATRIX_RUNOUT` value `936245901-2.2 WME` and successfully created 13 tagged staging copies for MusicBrainz release `fbf0a5ee-f9ef-3077-a38a-f990a1b9c8eb` (copy `25b4b47c4f814b4a96498e4b4767c96b`). Manual Proposed SOURCES.txt also displayed the matrix correctly for the same copy. Direct FLAC readback, publication, annotation search and Go! matrix entry remain open.

| Fixture | Observed result | Acceptance boundary |
| --- | --- | --- |
| Carmen Gomes Inc. — *Desire* | Single-CD revision and subsequent read-only Verify passed. 12 revised tracks and 12 retained originals, approved catalog `CGi2010` and label `CFMusic`, Collection and CUE/evidence checked. | Full rescan, restart, and controlled interruption are separate checks. Collection remains Unclassified without GENRE. |
| Anastacia — *Freak of Nature* | Both journal entries Verify as `VERIFIED` after [#120](https://github.com/sin7ek/OSCAR/pull/120), including the superseded generation. Collection refresh showed Pop / Popular, 12 tracks, `published_verified`. | Historical generations remain retained. Collection display alone does not establish per-file GENRE inspection. |
| *Boulez Conducts Stravinsky*, 6 CDs | Initial preview saw only CDs 4/6 and 6/6. Later all six were present. Coordinated LABEL Apply revised CDs 4 and 6 only, 39 tracks across group `7e20981bad8a4145bc7e3ad6d9cecd61`. Read-only Verify returned `Integrity PASS`; 90/90 labels reported correct across the box. | This covers LABEL and the observed group integrity check. Multidisc GENRE Apply, interrupted-group recovery and archive cleanup remain separate. |
| Mahler / Bernstein — *The Symphonies*, 2010 DG, Disc 11 | Recovery job `3c13772b6d104964ac71eb19e881668b` reached Go! Archive Review after [#136](https://github.com/sin7ek/OSCAR/pull/136). Optiarc job `26766340b2a04813a27d6081f8eff3c1` provided 16 tracks and LG diagnostic job `033f1207b6ba4184b7130e20ff75b181` provided Track 07. OSCAR reported 17/17 independent AccurateRip v1 and v2 matches and CUE/SHA-256 checks. Archive Review showed 17 tagged tracks. | Physical edition remains `INFERRED`. Separate source-file inspection, the new SOURCES preview, and publication remain open for this disc. |

See [#116](https://github.com/sin7ek/OSCAR/pull/116) and [#137](https://github.com/sin7ek/OSCAR/pull/137) for the documented Boulez and recovery results. The work document keeps exact job IDs, accepted values and the historical sequence.

## Next on Tower

- OSCAR automatically checks eligible full-disc staging rips against CTDB after extraction and records the result in Review, SOURCES.txt and publication evidence. AccurateRip keeps its existing verdict. Tower acceptance with known-good CD audio and a real CTDB lookup remains open.

- The operator confirmed single-disc changes were applied and verified on Tower. The new boxset metadata preview combines LABEL, GENRE and RELEASECOUNTRY for one coordinated revision. Tower acceptance is pending for Boulez and Mahler: scan missing metadata, approve DE on affected CDs, preview the group, apply and verify it on each set.

- MusicBrainz release and release-group genres take precedence. When both lack a curated genre, matching Discogs CDs can suggest a genre at staging review or as a Collection metadata addition for a published single CD. Verify the Electronic proposal and source URL for Équinoxe on Tower before approving it alongside DATE and RELEASECOUNTRY.

- After MusicBrainz exposes the reviewed 1985 date and DE country for Équinoxe `800 025-2` (`e410a90a`), run both selected-album metadata scans on Tower. Approve the date and country proposals and preview the new folder `[800 025-2] Équinoxe (1985) [e410a90a]`. Apply and Verify together. Check both Équinoxe editions remain in Collection and the original archive generation is retained.

- Collection imports verified archives with and without a known release year. Distinct archive paths keep editions separate. On Tower, re-import the existing Équinoxe archives and confirm both catalog numbers appear.

- DriveFit tags are shown on the corresponding Go! drive cards with their evidence available on hover. Verify card-to-drive correspondence on Tower.

- Edition search evidence is captured on lookup and included in proposed and published SOURCES.txt and the manifest for the actual MusicBrainz release and disc. Verify the Équinoxe comparison and country discrepancy in the Tower archive preview.

- Combined identifier search inspects up to 20 Discogs releases and accepts an optional known release ID or URL. The review exposes provider country differences and shows physical comparisons for unlinked Discogs entries. The Équinoxe regression fixture exercises Discogs 4709815 outside the first five results. Tower acceptance (Équinoxe, #151): with catalog `800 025-2` and barcode `3259180002527`, the combined search suggested MusicBrainz `e410a90a-d96c-3ac1-a65c-ac947016ffb1` and displayed Discogs `4709815` via shared identifiers. Matrix `800 025-2 02` matched variant 1 and differed from variant 2. The review displayed MusicBrainz Canada versus Discogs Germany and showed other entries sharing the identifiers. This confirms search, ranking and evidence display. Release approval, tagging and publication were not reported.

- Go! identifier search combines the staged disc lookup, MusicBrainz catalog, barcode and matrix searches, and Discogs links or matching release identifiers. It suggests a unique leading MusicBrainz candidate for manual selection and staging metadata review. Test provider lookups and the handoff on Tower.

- Completed staging jobs use a display-only artist and album working title when enabled MusicBrainz lookup has a majority album identity. The title is saved beside the staged rip and shown in Go! and Review, with lazy lookup for older jobs. Working titles provide no release approval and do not enter tags or archive paths. Tower acceptance is pending.

- Check the Advanced Review progression from a verified rip to the read-only archive preview, then check identifier handoffs in both Go! review modes.

- Verify a complete staged disc against CTDB and compare the result with a known CUETools log. Then reopen Proposed SOURCES.txt. Test Discogs against Jagged Little Pill with all three physical identifiers. See [archive publishing](ARCHIVE_PUBLISHER.md).

- On Tower, search for `936245901-2.2 WME` in MusicBrainz release annotations. Check the tagged copy and **Proposed SOURCES.txt** from manual publication preview, and exercise matrix entry in Go! release review.

1. Open **DriveFit** on the #140 image. Check real per-drive samples and normalized GH42 speed. In the LG diagnostic drive history look for Mahler Disc 11 Track 07 while its staging evidence exists. See [DriveFit](DRIVEFIT.md) for thresholds and the limits of historical data.
2. Open the recovered Disc 11 in **Go! → Archive Review → Proposed SOURCES.txt** on the same image. Check Track 07 for the LG source, the other 16 for Optiarc, and independent `trackverify` attribution. Publication requires separate physical-edition review and explicit approval. The physical box is catalog `477 8668` / `00289 477 8668`; distinguish its barcode from a per-disc MCN. Track attempt details from #139 require that PR to ship and may need a fresh recovery fixture.
3. Keep the remaining real-hardware checks separate: per-drive ETA, tracked Go jobs, supported Eject/Close and confirmed Stop, refreshed Go metadata-copy adoption, genre-source comparison and coordinated GENRE Apply. The successful LG selected-track extraction covers that part of #132.

## Project workflow

- Start a new OSCAR development chat with this document from GitHub, then read [PROJECT_STATUS.md](PROJECT_STATUS.md), [PROGRESS.md](PROGRESS.md), the active technical docs and actual `main`/PR state. The repository is [sin7ek/OSCAR](https://github.com/sin7ek/OSCAR).
- Use a branch, focused tests and a PR. For a requested Tower-ready code change, follow required CI, fix failures, merge after green checks and verify `ghcr.io/sin7ek/oscar:main` against the merge revision before saying the operator can pull. A PR-only or review request stays open. Track operator pull and real Tower acceptance separately.
- Update the work document, dashboard and handoff with each relevant milestone or acceptance result. Place technical audit history in the work document. Preserve original extraction and archived generations. A matching Disc ID or passing audio verification does not prove the physical edition. Archive mutations require operator opt-in. Keep credentials out of GitHub.
- Technical starting points include the [archive metadata lifecycle](ARCHIVE_METADATA_LIFECYCLE.md), [multidisc revisions](MULTIDISC_ARCHIVE_REVISION.md), [genre evidence](GENRE_EVIDENCE_V1.md) and the [automation roadmap](AUTOMATION_ROADMAP.md). The example Unraid Compose is still a draft and a reviewed Getting Started guide remains open.
