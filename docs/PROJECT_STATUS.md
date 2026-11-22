# OSCAR — project status and handoff

## Current status — 2026-11-22, through PR #149

**Latest feature on `main` and GHCR:** [PR #149](https://github.com/sin7ek/OSCAR/pull/149) adds display-only rip working titles and integrated MusicBrainz/Discogs edition review. Python Tests and Docker build passed. The registry Linux/amd64 image `ghcr.io/sin7ek/oscar:main` reports revision `db0df556f9743d0b02c0f13a86e5ee205d80ba08` at digest `sha256:d44a401ad2d106340ebc637d420e24aaa47604bbe147a42d8dec46e47d4b15bf`. Live Tower acceptance remains open.

**CTDB and Discogs:** [PR #145](https://github.com/sin7ek/OSCAR/pull/145) ships independent, operator-triggered CTDB verification and read-only Discogs pressing comparison. PR Tests and Docker build passed. The Linux/amd64 `ghcr.io/sin7ek/oscar:main` OCI revision matched merge `ca4bfe47ad3e6cacd232c0d5448417300da8619c` at manifest digest `sha256:8ba24a6c041843fb48f3557eaf627df1808d531e548922acaecd99bdab184f7d`. A live lookup with a two-track test signal produced the expected CTDB no-audio-match result (`0/1`). Known-good audio and Discogs variant acceptance on Tower are pending.

**Discogs coverage:** Combined identifier search inspects up to 20 Discogs releases and accepts an optional known release ID or URL. The review exposes provider country differences and shows physical comparisons for unlinked Discogs entries. The Équinoxe regression fixture exercises Discogs 4709815 outside the first five results. Live Tower retest remains open.

**Combined identifier search:** Go! identifier search combines the staged disc lookup, MusicBrainz catalog, barcode and matrix searches, and Discogs links or matching release identifiers. It suggests a unique leading MusicBrainz candidate for manual selection and staging metadata review. Test provider lookups and the handoff on Tower.

**Rip working titles:** Completed staging jobs use a display-only artist and album working title when enabled MusicBrainz lookup has a majority album identity. The title is saved beside the staged rip and shown in Go! and Review, with lazy lookup for older jobs. Working titles provide no release approval and do not enter tags or archive paths. Tower acceptance is pending.

**Advanced Review:** Advanced Review links verified rips, tagged copies and archive previews with prefilled IDs. Semi Secure and Secure offer optional per-job physical identifiers and handoffs to MusicBrainz and Discogs. Tower acceptance is pending. See [the workflow](AUTOMATION_ROADMAP.md#advanced-review-handoffs).

**Matrix/runout:** [PR #142](https://github.com/sin7ek/OSCAR/pull/142) adds release-annotation search and disc-level transcription in the [archive publishing workflow](ARCHIVE_PUBLISHER.md). [PR Tests](https://github.com/sin7ek/OSCAR/actions/runs/45077525913), [PR Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45077525924) and the [main image build](https://github.com/sin7ek/OSCAR/actions/runs/45077599992) passed. The registry's Linux/amd64 `ghcr.io/sin7ek/oscar:main` OCI revision was checked against merge `cfd01bf79b079b88aa28bf008b066fbac406e308` at manifest digest `sha256:b88d8607e6337987a77ca3494f79d24b69de4cc5aed4b25e8342ff0e63ef9aea`. 

On Tower, the manual Metadata & tagging preview for *Jagged Little Pill* showed the operator-transcribed `MATRIX_RUNOUT` value `936245901-2.2 WME` and successfully created 13 tagged staging copies for MusicBrainz release `fbf0a5ee-f9ef-3077-a38a-f990a1b9c8eb` (copy `25b4b47c4f814b4a96498e4b4767c96b`). Manual Proposed SOURCES.txt also displayed the matrix correctly for the same copy. Direct FLAC readback, publication, annotation search and Go! matrix entry remain open.


**DriveFit:** [#140 DriveFit](https://github.com/sin7ek/OSCAR/pull/140) merged as `5368f6489da5755fe7fb53f99c41d0af7d01b17d`. GitHub [Tests](https://github.com/sin7ek/OSCAR/actions/runs/45072660464) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45072660444) passed. The OCI revision of `ghcr.io/sin7ek/oscar:main` for Linux/amd64 matched that commit at registry digest `sha256:ecbd840da41f318446145ce686f73d73baf2a20f9492d5545a75b39878150e56`. Tower pull and DriveFit acceptance remain open.

| Change | GitHub and image | Tower evidence |
| --- | --- | --- |
| [#140 DriveFit](https://github.com/sin7ek/OSCAR/pull/140) | Merged, both checks green, GHCR revision confirmed. Replaces draft #111 as the shipped implementation. | Check samples, normalized GH42 speed and LG diagnostic Track 07. Historical metrics depend on surviving staging; new summaries persist in SQLite. |
| [#139 Both Track Recovery attempts in provenance](https://github.com/sin7ek/OSCAR/pull/139) | Open at `023e06b`; [Tests](https://github.com/sin7ek/OSCAR/actions/runs/45070962329) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45070962389) passed. Outside the #140 image. | Pending. New jobs capture both attempted sources and their available extraction evidence; older jobs can identify unavailable history. Digital acquisition remains a future input. |
| [#138 Per-track archival SOURCES](https://github.com/sin7ek/OSCAR/pull/138) | Merged as `255c4f1`; [Tests](https://github.com/sin7ek/OSCAR/actions/runs/45067284484) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45067284462) passed; included in #140. | Read-only **Proposed SOURCES.txt** and subsequent publication remain open. Track 07 should name the LG diagnostic job, other tracks the Optiarc job, with verification attributed separately to `trackverify`. |
| [#134](https://github.com/sin7ek/OSCAR/pull/134) / [#136](https://github.com/sin7ek/OSCAR/pull/136) Track Recovery | Merged and shipped. #136 fixes the bundled verifier's runtime extraction failure. | Mahler Disc 11 reached Archive Review after 17/17 independent AccurateRip v1/v2 matches. Physical edition approval and publication are open for Disc 11. |
| [#132 Optical controls](https://github.com/sin7ek/OSCAR/pull/132), [#131 Tracked Go jobs](https://github.com/sin7ek/OSCAR/pull/131), [#130 USB drive IDs](https://github.com/sin7ek/OSCAR/pull/130), [#127 ETA](https://github.com/sin7ek/OSCAR/pull/127), [#126 Refreshed-copy adoption](https://github.com/sin7ek/OSCAR/pull/126) | Merged and included in #140; PR checks passed. | LG selected-track extraction worked. Tray/Stop, full four-drive UI regression check, tracked job filtering, ETA and refreshed-copy adoption still need distinct acceptance results. |

## Reconciliation with OSCAR chat 5 and subsequent Tower results

- **Single-CD revisions:** reported read-only Verify passed for Carmen Gomes Inc. and Anastacia, 12 current and 12 retained FLACs per revision. The later [#120](https://github.com/sin7ek/OSCAR/pull/120) check also passed for Anastacia's superseded generation. Anastacia's Collection subsequently showed Pop / Popular. Applying a revision, running Verify, and testing Clean are separate. No cleanup was performed in the recorded tests.
- **Boulez LABEL:** [#108](https://github.com/sin7ek/OSCAR/pull/108) initially showed CDs 4 and 6 of a six-CD release, 39 tracks needing review. After all six were present, 51 tracks were already correct. [#110](https://github.com/sin7ek/OSCAR/pull/110) applied the approved changes only on CDs 4 and 6 and retained originals. [#112](https://github.com/sin7ek/OSCAR/pull/112) read-only Verify returned `Integrity PASS` with 90/90 correct labels reported across the box. This does not establish multidisc GENRE Apply or failure recovery. The optional physical Classical/Popular split remains undecided ([#115](https://github.com/sin7ek/OSCAR/pull/115)).
- **Other acceptance from the chat:** the Anne-Sophie Mutter reverify reported `checks_passed`, 7/7 FLACs, matching CUE, SHA-256 and AccurateRip v1/v2, with zero reported ripping errors. The second Roxy Music extraction had 5/10 AccurateRip-confirmed tracks and remains a damaged-disc example, separate from the successfully recovered Mahler fixture.
- **Pending work:** beginner Compose review and Getting Started, broader artwork workflows, cyanrip follow-ups beyond the shipped progress/diagnostics changes, production-path GENRE acceptance for new rips and boxsets, and live [Genre Evidence](GENRE_EVIDENCE_V1.md) provider review. Preserve original archive generations. See the [dashboard](PROGRESS.md) for next acceptance checks and the [handoff](DEVELOPER_HANDOFF.md) for the current test fixtures.

### Mahler staging references and optical inventory

The operator recorded these original staging jobs for the 11-CD *The Symphonies* (2010 DG, catalog `477 8668` / `00289 477 8668`):

| Disc | Staging job |
| --- | --- |
| 01 | `8da1c3736e3c4ce0ace53d953f962187` |
| 02 | `5b48c63b756a473197af192b65505a63` |
| 03 | `e4ca0a116f744e0799d2dbf04161f6f1` |
| 04 | `8665644102f241c69d981abb640ef8f1` |
| 05 | `9338aea7c2b64f90b3ffb5542fae5e24` |
| 06 | `f51c0969972c46d1b36bd57adfcf113e` |

These IDs are staging references. Later Collection output reported discs 02, 03, 05 and 07 as `published_verified`; disc 07 still had an `INFERRED` edition. The recovered Disc 11 remains in Archive Review. Keep box catalog/barcode and individual-disc MCNs distinct. The operator identified the USB LG GP95NB70 RC00 on Tower and observed advertised C2/CD-Text capabilities in `sg_get_config`. This was a capability query. DriveFit speed, errors and recovery comparisons require actual saved rip evidence.

## Milestone history

The dated entries below retain the state at the time of each report. See the current status above for later results and superseded acceptance gates.

## 2026-11-22 — Track Recovery v1 verified on Unraid through Archive Review

On Tower, the operator reported that recovery job `3c13772b6d104964ac71eb19e881668b` reused 16 tracks from Optiarc job `26766340b2a04813a27d6081f8eff3c1` and replaced track 7 from LG diagnostic job `033f1207b6ba4184b7130e20ff75b181`. OSCAR reported 17/17 independent AccurateRip v1 and v2 matches, CUE and SHA-256 checked. The integrated verifier requires both versions at offset zero. The supplied Go! Archive Review shows all 17 classical FLAC tag rows and 17 CUE tracks for Mahler/Bernstein, *The Symphonies* (2010), Disc 11, Disc ID `1FGELhYaLaSf9MIPUxtlZGDbQU8-`. The release is still INFERRED and publication remains pending explicit physical-edition review and approval.

PR #134 implemented recovery and registers verified jobs in Semi Automatic. PR #136 (`5879783`) installs the verifier unpacked after the first Tower run failed during PyInstaller extraction of `libpython3.11.so.1.0`. GitHub Tests and the Docker smoke test passed before deployment. A separate filesystem inspection of recovery provenance, copied files and source hashes remains pending if needed for acceptance.

## 2026-11-22 — PR #132 optical controls and selected-track diagnostics merged; Unraid acceptance pending

**Merged main** `577c876db26f973a5bb4a15c1699ed306ba7b13e`, PR #132: Go drive Eject/Close (Linux CDROM ioctl on read-only device, disabled while ripping), confirmed Stop that interrupts only OSCAR's cyanrip child and **retains partial staging, log and ledger**, plus advanced comma-separated selected-track diagnostics using cyanrip 0.9.3 `-l` in a **new isolated staging job** marked `partial_diagnostic`. This cannot enter normal Go, full-disc verification or archive publication. GitHub **Tests success, Docker build success** for final feature head `5e50088dc7f6e187157d6d6b55934bc14a986c28`; **real Unraid hardware acceptance not yet performed**. Test idle Eject/Close separately on SATA and USB (unsupported tray close possible), disabled controls while active, Stop on sacrificial CD with preserved logs/files and `RIP_INTERRUPTED`, selected track 7 on HP `/dev/sr2` cross-check against the original Optiarc job `26766340b2a04813a27d6081f8eff3c1` (16/17 full AR, track7 partial AR450); no automatic cleanup and no manual replacement of original FLAC. Source snapshots `OSCAR_MAX_CONCURRENT_RIPS=4` / read-only `/dev/sr*` mappings unchanged.

## 2026-11-22 — USB LG GP95NB70 stable ID rejects colon: Unraid 500 regression fix

**Observed on real Unraid after plugging fourth optical drive:** /dev/sr3 HL-DT-ST DVDRAM GP95NB70 firmware RC00 detected and mapped into OSCAR Docker correctly, but both `GET /api/settings` and `GET /api/media` raised 500 on `discover_settings()`: `DriveSettings.stable_id` regex `^[A-Za-z0-9_.-]+$` rejected real persistent udev symlink basename `usb-HL-DT-ST_DVDRAM_GP95NB70_K0LKBCC3829-0:0` due to the colon in USB SCSI-LUN suffix `-0:0`. Fix: minimally accept colon in otherwise restricted drive IDs while rejecting paths, whitespace, shell metacharacters; preserve complete udev identifier and independently stored offset. Add tests for exact real USB ID, settings save/read/merge, `/api/settings` and `/api/media`, and invalid IDs. No changes to Docker `:r` mappings or the operator's working media/staging. **GitHub CI is not equivalent to Unraid acceptance**; after merge operator should pull rebuilt main and reload GUI, ensure four drives appear and no 500. Operator has set `OSCAR_MAX_CONCURRENT_RIPS: "4"` as correct override of the default 3. No user archive changes.

## 2026-11-22 — Live per-drive cyanrip progress/ETA (PR #127 merged)

**Merged in [#127](https://github.com/sin7ek/OSCAR/pull/127); GitHub Tests and Docker build passed; Unraid acceptance pending.** Go! cards for concurrent drives now show a read-only extraction bar, current/finished track counts, elapsed time and *rough* dynamic ETA, refreshed every ~3.5 seconds with previously authorized dashboard headers while the Go tab is visible. Backend `src/oscar/ripping.py::_progress` uses existing per-job `plan.json` track count and contiguous numbered FLAC output files. A currently opened/actively written FLAC is **not** considered completed until the next numbered track appears. Percentage counts **tracks** (not disc sectors/audio duration) and never claims 100% while cyanrip is still running. ETA is shown only after >=2 completed tracks and derives from elapsed/finished track average; severe inaccuracy possible for long Mahler movements, repairs/retries and last track. Unavailable data yields an unknown ETA, not a fabricated value. No changes to optical drive commands, staging files, archive or integrity verification. New tests and `docs/RIP_PROGRESS_ETA.md`; passing GitHub CI and real three-drive Unraid acceptance must be logged separately. Current operator hardware: HL-DT-ST GH24NS95, Optiarc AD-7200S, hp DH16AAL. **User requested ETA during three concurrent Mahler boxset rips.** Never confuse a progress estimate with AccurateRip/CTDB verification.

## 2026-11-22 — PR #126: Select refreshed Go metadata copy before first archive publication

**Merged in [#126](https://github.com/sin7ek/OSCAR/pull/126); GitHub Tests and Docker build passed; Unraid acceptance pending.** For an accepted Semi Automatic Go job still in `METADATA_READY` and never previously reserved for archive publication, after an explicitly generated and readback-verified refreshed MusicBrainz tagged staging copy, a new authenticated operator-confirmed action can atomically replace Go's active `metadata_copy_id` and metadata fingerprint before its FIRST publication. Original rip and previous tagged copy are retained; no publication/archival writes happen. In SQLite, publication reservation interlock and durable event prevent silent history rewriting. Identity checks cover exact release, Disc ID, track ordering, original rip file SHA evidence, new tagged SHA/STREAMINFO MD5/Vorbis tags; a fresh Go archive preview is required afterwards. **Physical edition remains INFERRED; no pressing proof.** See `docs/GO_REFRESHED_COPY_ADOPTION.md` and PR #126. Existing already-published Carmen Gomes reprocessing remains separate and cannot be adopted into its former Go job.

**Mahler/Bernstein (2010 DG *The Symphonies*, physical 11-CD box, catalogs 477 8668 / 00289 477 8668) operator-supplied exact staging mapping:** CD **02** `5b48c63b756a473197af192b65505a63`; CD **03** `e4ca0a116f744e0799d2dbf04161f6f1`; CD **04** `8665644102f241c69d981abb640ef8f1`. None published as of operator confirmation. Three other CDs currently being ripped; disc/job identities not yet reported. Operator added physical-spine photo and alternate catalog `477 8668` in MusicBrainz. Updated metadata comparison for Disc 03 showed added catalog in album/labels/three track tags. The first catalog field remains `002894778668`, so **the current archive destination may still use that number**; do not claim `477 8668` is automatically preferred. Test all three independently in staging before any publishing.

## 2026-11-22 — Genre Evidence v1 merged (#124); Mahler/Bernstein 11-CD physical review

**Merged code:** PR #124 `0c5b7b51d063585435190b0431833c37740436f4` adds a **read-only** authenticated Collection `Genre evidence — source comparison` preview; exact-release MusicBrainz positive genre votes and release-group fallback (one source cluster), optional operator-provided catalog+CD-format-matched Discogs release ID, per-source claims, raw/canonical genre, independence groups, abstentions, agreement fraction and review status. Python Tests and Docker build green at final PR head; **actual Unraid UI/provider acceptance not yet done**. No source-based automatic metadata approvals or archive writes; durable consent, Qobuz (terms/API), genre lineage provenance in new `SOURCES.txt`/manifest and reviewed versioned updates to old archives remain future implementation. See `docs/GENRE_EVIDENCE_V1.md` and open design PR #123. Preserve current archives and old `SOURCES.txt` byte-identically.

**Mahler test (preview, not published):** Operator reports three freshly ripped CDs from an approximately 12-CD Mahler box; one OSCAR Archive Review for `The Symphonies` (2010) `Mahler; Leonard Bernstein/[002894778668] .../Disc 03`, 3 FLAC tracks of Mahler Symphony No. 3 movements I–III, inferred (NOT physical-edition verified), proposed release short `f0a7ab08`, CUE MCN `0028947786719`. Independent external reference MusicWeb International 2010 `Deutsche Grammophon 477 8668` explicitly reports **11 CDs**, with Disc 3 exactly those three movements (60:04) and disc-performer New York Philharmonic. Library catalog reference https://ci.nii.ac.jp/ncid/BB01473472 lists box booklet number `00289 477 8668` and per-CD numbers 00289 477 8669–8679; disc3 corresponds `00289 477 8671`. UPC for boxed item 0028947786689. Proposed folder component `[002894778668]` appears barcode-like/partial, while external catalog number is `477 8668`; **verify physical packaging, actual box catalog and barcode in the OSCAR physical release compare before publishing.** Do not conflate per-disc MCN with box barcode/catalog, and do not assert Disc ID+tracklist proves pressing. Check other two staging previews against same correct 11-disc release, with explicit operator confirmation. No new publication recorded.

## 2026-11-22 — Unraid acceptance: historical single-CD revision chain Verify (PR #120)

**Operator-reported real Unraid PASS after pulling updated main:** All three single-CD revision journal entries returned `VERIFIED`. Anastacia – *Freak of Nature*: latest revision `12 new FLACs + 12 originals, 1 approved change; CUE/evidence and Collection OK`; earlier (superseded) revision `12 new FLACs + 12 originals, 1 approved change; CUE/evidence and Collection OK. Historical generation (superseded by a later revision); cleanup prohibited.` Carmen Gomes Inc. – *Desire*: `12 new FLACs + 12 originals, 2 approved changes; CUE/evidence and Collection OK`. Read-only Verify reports no archive bytes changed. This resolves the earlier false failure `Archive publication ancestry differs from journal` for successive Anastacia publications.

**Acceptance boundary:** Historical journal chain/retained-generation Verify is now CI-tested **and** operator-verified on Unraid. No Clean/Verify & Clean was performed, and historical generations must remain retained. These reports do not establish a per-field manual inspection of current GENRE tags or classification in Collection. **Next:** confirm Anastacia's final Collection genre `Pop` and library section `Popular` and corresponding GENRE in current archived FLACs; distinguish it from the separate pending acceptance of multidisc GENRE Apply and new-rip staging genre writes. Do not physically split Classical/Popular archives without explicit opt-in.

## 2026-11-21 — Reviewed MusicBrainz GENRE to FLAC (PRs #117, #118 merged; live Unraid pending)

**Implementation:** PR #117 (merged as `6322f109d1d297e353615bab6d98e5471612f027`) adds curated official MusicBrainz positive-count `genres` on an exact release or its exact release group (release preferred; no artist guesses/free-form `tags`), with source in the new-rip metadata preview. After explicit operator confirmation, new tagged staging FLAC copies contain independent multivalue Vorbis `GENRE` comments. Previously published single CDs get read-only `GENRE` proposals in archive metadata scan, durable Accept/Ignore, opt-in versioned Archive Revision Apply, retained originals and Collection genre/section update. PR #118 (merged as `13342b89d31a78f9454ea98a24235888e73504c0`) adds a **separate GENRE-mode** coordinated boxset preview/Apply using the existing `OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS=1` gate, release fingerprint and recovery journal; updates Collection after full group verification. The new Verify compares every FLAC metadata tag and allows only the explicitly approved GENRE change (old LABEL journal entries remain LABEL-only). User-facing buttons: **Preview coordinated multidisc genres (read-only)** and journal **Verify original, audio, metadata and Collection**.

**Testing:** Both feature PRs had successful GitHub Python Tests and Docker build. Tests include synthetic metadata/archived-original rollback and optional real FLAC integration (skipped without FLAC executable). **Neither GENRE workflow is yet Unraid-accepted.** The earlier Boulez LABEL migration was accepted separately: 90/90 labels correct and completed read-only integrity Verify for discs 4 (7 tracks) and 6 (32 tracks), operation `7e20981bad8a4145bc7e3ad6d9cecd61`. Never infer new genre-Apply validation from that result.

**Next live acceptance:** pull fresh `main` only when operator is ready. Check a new rip metadata preview displays genre candidates/source. Scan missing GENRE proposals for Anastacia/Carmen on already indexed single CDs; accept only matching physical edition and editorial genre values, preview single-disc revision, and explicitly Apply only with backup and `OSCAR_ENABLE_ARCHIVE_REVISIONS=1` enabled. For Boulez, use the separate GENRE group preview, review all six medium approvals, and do not Apply until plan/safety reviewed; independent Verify afterward. No automatic archive changes or physical Classical/Popular move. The physical split remains **optional and undecided**. See `docs/REVIEWED_GENRE_TAGGING.md` and `docs/MULTIDISC_GENRE_ARCHIVE_REVISION.md`. SemVer prerelease is deferred pending Unraid acceptance.

## Unraid acceptance — coordinated Boulez archive revision (2026-11-21)

**Operator-reported real Unraid verification: PASS.** The operator ran **Verify original, audio, metadata and Collection (read-only)** for the completed *Boulez Conducts Stravinsky* (MusicBrainz release `423f636d-742d-47b0-9ba2-51515a6fdfd2`) group operation `7e20981bad8a4145bc7e3ad6d9cecd61`. OSCAR returned `Integrity PASS`; **Disc 4: pass (7 tracks)** and **Disc 6: pass (32 tracks)**. The read-only verifier checks retained originals and revised generations, decoded-audio identity, manifest and FLAC hashes, non-audio evidence, every Vorbis comment against the approved LABEL-only change, and Collection state/decisions. Earlier operator checks reported 90/90 correct LABEL across six discs and 39/39 decoder tests for the revised CDs, with all six group preview statuses `already_correct`.

**Scope:** this is genuine operator-reported Unraid acceptance of this specific completed multidisc metadata migration and its read-only integrity verification; it is **not** a guarantee that all failure/recovery paths or other releases have been hardware-tested. The exact physical MusicBrainz edition is **not** independently authenticated by archive-integrity Verify. PRs #112/#113 were merged and had green PR Python/Docker CI, but genre search and library section UI still await Unraid acceptance. A physical Classical/Popular archive split is deferred and may only be opt-in (PR #115 documentation decision pending). Retained generations must not be cleaned or moved as part of this test.

## Initial coordinated LABEL preview for incomplete releases (2026-11-20, PR #108)

The next implementation adds `src/oscar/archive_revision_boxset.py` plus an authenticated Collection **Preview coordinated multidisc labels (read-only)** action. The operator selects any archived disc of the release in the existing Advanced Collection album selector. OSCAR verifies **all indexed/published leaves** under the same physical MusicBrainz release ID, each live FLAC manifest SHA-256 and Disc ID/CD medium/recording identity, exact current MusicBrainz release labels, and corresponding accepted per-disc label decisions. One group summary reports available and missing disc numbers, target label, each disc's tag status and approval fingerprint. Specifically, the operator's *Boulez Conducts Stravinsky* 6CD can show discs **4 and 6 present**, discs **1, 2, 3 and 5 missing**, with approved **Deutsche Grammophon** proposals on available discs if current metadata still agrees.

**No Apply exists in this preview.** `apply_supported: false` explicitly prevents accidentally running the single-CD migration on a boxset. **Next separate milestone**: design and test a durable, coordinated all-or-none multi-leaf apply/reconciliation journal with no invented data for missing media and full physical-CD/manifest provenance. Neither current boxset FLACs nor Collection labels are modified by preview. GitHub tests are not equivalent to a real Unraid boxset preview.

---

## Verified archive revision maintenance: Verify / Clean / Verify & Clean (2026-11-20, PR #107 merged, CI green, Unraid acceptance pending)

An explicitly operator-triggered maintenance layer is being added to Collection's **Archive Metadata Migration** journal. Its safety boundaries are:

- **Verify** reopens the currently published and the retained original version, verifies exact manifest / publication lineage and original SHA-256 hashes, independently runs `flac -t` for ALL FLACs in BOTH generations, compares STREAMINFO decoded audio MD5, rechecks all approved metadata values, CUE/extraction evidence and every non-FLAC file, and validates the Collection row, catalog number, label provenance and proposal `applied` states. It does not intentionally modify archive files.
- **Clean** is an **irreversible** removal of *one* retained original publication directory selected by its exact **completed** journal operation ID; it NEVER deletes the current published album or the entire shared history tree. It requires `OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP=1` as a separate explicit opt-in (OFF by default), the content-bound receipt from a successful Verify, double operator confirmation including declaration of a **tested external backup**, and a second, fresh full Verify inside the same archive-publisher lock. It journals `prepared` intent before deletion and `completed` after success. An interrupted cleanup must be inspected manually; there is no automatic destructive retry.
- **Verify & Clean** runs Verify and then offers the same explicit destructive confirmations; it does not silently delete on scan, archive apply, startup, import or ordinary Refresh.
- Clean deliberately sacrifices OSCAR's retained original evidence and built-in rollback capability. It breaks the ability to independently verify the historical parent publication from inside OSCAR after cleanup. **Exclude `.oscar-archive-versions` from Plex, Navidrome, Jellyfin etc. or mount only current published albums if possible; this is the safer default than deletion.** The OS/kernel and filesystem permissions must support safe symlink-aware removal.
- **Multidisc/boxset migrations remain deliberately blocked**. Do not use this single-CD Verify/Clean workflow as a substitute for a coordinated Boulez 6CD migration. Only physical discs 4 and 6 of 6 are known published on this system. A multidisc plan needs exact medium verification per disc, one release-level review, atomic promotion/recovery of all present discs, explicit policy for absent discs, and Collection synchronization.
- **Testing:** synthetic GitHub Python and Docker tests are necessary, not sufficient. Real Unraid Verify of Carmen Gomes and Anastacia is pending; opt-in cleanup must first be tested on a sacrificial test album with a restorable external backup before any consideration for these two genuine retained originals. No cleanup is requested, performed or approved by recording this design.

---

## Anastacia live-Unraid label-only archive revision verified; Collection label normalization (2026-11-20)

The operator independently verified the second successful single-CD revision, Anastacia *Freak of Nature* (2001): **12/12 new FLACs** have the reviewed `LABEL` values **Daylight** and **Epic** and the correct MusicBrainz release UUID; **12/12** pass `flac -t`; **12/12** retained originals match the original publication manifest SHA-256 checks. Read-only Collection query confirms the original album path (unchanged catalog `504757 2`), `track_count=12`, proposal `LABEL` status `applied`, but Collection's local `label` shows only `Epic` after UI Refresh: this is a **real catalog projection inconsistency**, not a FLAC retagging failure.

Root cause: `archive_revision._finalize` previously filled local `label` **only when blank**, retaining an older MusicBrainz-enriched source label `Epic` even after approved FLAC revision to `Daylight; Epic`. In PR #106 the finalization updates Collection labels from explicitly approved revisions **only if their existing provenance is known to be OSCAR/MusicBrainz-sourced or blank**, and records `archive_revision_approved_labels`; genuinely manual/unknown values remain untouched. UI wording changes from **Record label** to **Label**. Both refer to the release's record label; `RECORDLABEL` is treated as a legacy FLAC alias of canonical `LABEL`, **not** another distinct label entity. The existing Anastacia row can now be repaired through an explicit **Synchronize applied labels (Collection only)** action: it verifies the completed revision's FLAC hashes and exact approved label tags and changes only OSCAR/MusicBrainz-sourced local labels, preserving manual values. This feature has GitHub regression coverage but needs live Unraid acceptance.

Remaining operator requests: archive **Verify** (actual FLAC/manifest/CUE/source evidence, original-generation and Collection checks), operator-approved **Clean** and **Verify & Clean** to remove only explicitly verified retained generations with clear irreversible-loss warnings and strong journaling/race protection, plus **coordinated multi-disc** support for Boulez (discs 4 and 6 present, others absent). DO NOT silently delete `.oscar-archive-versions` or attempt single-disc apply to a boxset. Media servers may index hidden history; advise exclusions or separate archive mounts until cleanup is safely implemented. These are scoped follow-up engineering milestones, **not delivered in PR #106**.

---

## Second real-Unraid archive revision recorded — Anastacia label-only, same destination (2026-11-20)

The operator's live **View archive revision history** now reports **2 completed operations**:

- **Anastacia — *Freak of Nature* (2001)**, MusicBrainz release prefix `4b370e6c`: `completed`, **source and destination intentionally identical**: `/archive/Anastacia/[504757 2] Freak of Nature (2001) [4b370e6c]`. This is a label-only metadata revision; `504757 2` was already the reviewed catalog number, so no album-directory rename is needed. Original generation retained according to journal at `/archive/.oscar-archive-versions/5ff97661e98742afbf5db690f827d0f1/f5e41eef584c44288cc76a2a8477e635`. Previously approved `LABEL` values were `Daylight` and `Epic`. **Evidence is operator-provided revision-history status only.** Independent new FLAC-tag checks, `flac -t`, original manifest SHA-256 checks, and Collection/proposal SQLite checks have **not yet been reported**; do not call Anastacia fully validated.
- **Carmen Gomes Inc. — *Desire* (2010)**: `completed`, original `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]` → revised `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`, retained original at `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`. This operation already passed independently verified 12/12 tags, decoder, original FLAC hash and SQLite/decision checks.

**Next:** collect the operator's read-only independent verification results for Anastacia (new FLAC labels `Daylight` and `Epic`, release UUID, `flac -t`, SHA-256 against retained original manifest, and Collection `label`, archive path, `applied` proposal); separately verify post-revision full-archive scan, restart persistence and failure recovery. Never migrate the Boulez 6CD with the current single-CD engine.

---

## Carmen Gomes single-CD archive migration — live Unraid primary happy-path ACCEPTED (2026-11-20)

Operator supplied independent **read-only** SQLite queries against the running OSCAR container *after* the migration finished. Results:

- Exactly **one** `archive_items` row for MusicBrainz release `fa89edc1-32f9-4290-8788-bbac2e366a46`, with `archive_path=/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`, `catalog_number=CGi2010`, `label=CFMusic`, and `track_count=12`.
- Exactly two matched `metadata_proposals` rows: `CATALOGNUMBER` and `LABEL`, both **`status=applied`**, originating from `before_json=[]`, targeting `["CGi2010"]` and `["CFMusic"]`.
- Corresponding `archive_revision_operations` reports **`completed`**, the correct old/new paths and original retained generation `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`.
- From previous independent Unraid checks: all **12/12 new FLACs** contain the approved catalog/label and correct MusicBrainz release ID (Mutagen), **12/12 new FLACs** pass `flac -t`, and **12/12 retained original FLAC SHA-256s** match their original publication manifest.

**Acceptance judgment:** the normal **single-CD archive-revision apply, version retention, metadata write, audio decode, proposal state transition, and Collection SQLite rebind** are now validated on real Unraid. This is **not** proof of complete crash/restart resilience. Still pending: post-apply repeat whole-archive scan (no duplicate or stale proposals), container restart and persistence, interrupted-journal recovery under controlled failure, full non-FLAC CUE/evidence hash verification, and a separate boxset-safe migration (not implemented). No additional archive mutation is authorized or necessary for these read-only checks.

---

**Real-Unraid retained-original integrity acceptance (2026-11-20):** the operator used a read-only Python SHA-256 check of each FLAC against the original archived `manifest.json` under `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`. **All twelve originals passed (12/12 SHA-256 matches)**. Together with independently confirmed 12/12 migrated FLAC tags and 12/12 successful `flac -t` checks, this verifies the engine's promised retained original audio-file bytes against publication evidence. Still outstanding for full end-to-end Unraid acceptance: Collection SQLite archive path/catalog link and two proposal `applied` statuses, post-migration scanner, restart persistence and recovery from interrupted journal. A retained-manifest self-hash or non-FLAC CUE/evidence reread has not been separately established by this test.

---

**Real Unraid post-migration audio acceptance (2026-11-20):** the operator ran `docker exec -i oscar python - <<'PY'` against the twelve new FLAC files in `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`. The script invoked `flac -t --silent` independently on **all 12 files**, and every track returned `OK` (`Resultaat: 12/12 FLAC-bestanden geslaagd`). Combined with the earlier 12/12 Mutagen checks, the revised publication now has independently confirmed catalog `CGi2010`, label `CFMusic`, release ID and successful FLAC decoding for every track. **Not yet confirmed independently:** retained original version hashes/contents, Collection SQLite path and revision linkage, rerun scanner suppression, restart persistence or journal crash recovery. Do not state full end-to-end acceptance until appropriate checks complete.

---

**Unraid independent FLAC tag acceptance (2026-11-20, after completed archive revision):** operator ran `docker exec oscar python` using Mutagen on all twelve FLACs under `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]` and pasted full per-track results. **All 12/12** contain `CATALOGNUMBER=['CGi2010']`, `LABEL=['CFMusic']`, `MUSICBRAINZ_ALBUMID=['fa89edc1-32f9-4290-8788-bbac2e366a46']`, and `RECORDLABEL=[]`. This independently confirms the new published FLAC tags for all twelve tracks after the UI reported revision `completed`. **Now independently verified:** `flac -t` on all 12 new files (12/12 passed). **Still pending:** original retained-generation SHA-256/byte integrity, final Collection SQLite row/path and rerun-scanner suppression, restart persistence and interrupted-journal recovery. Do not call full end-to-end acceptance complete yet.

---

**Subsequent operator evidence (same date):** after explicitly clicking Apply, the OSCAR UI reports `1 recorded archive revision operation(s)` with status **`completed`**, source `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]`, destination `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`, and retained-original path `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`. Unraid file-manager screenshots show the renamed album directory, `ExtractionEvidence` and visible newly modified FLACs (first ten of twelve on screen). **This confirms user-visible completion and filesystem promotion; a subsequent Mutagen read confirmed `LABEL=CFMusic`/`CATALOGNUMBER=CGi2010` on all 12 tracks. Still NOT independently verified: `flac -t` integrity, retained original file digests, Collection SQLite linkage, restart persistence, or archive rescan.** Request independent `metaflac` / `flac -t` shell results before upgrading acceptance to fully verified.

## Carmen Gomes real-Unraid read-only archive migration preview acceptance (2026-11-20)

Operator provided output of the deployed **Verified archive migration preview** for *Carmen Gomes Inc. — Desire (2010)*. It correctly reports source `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]`, target `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`, reviewed catalog number `CGi2010`, **2 accepted changes**, **12 tracks**, and original publish ID `3908eef79f114450b0a7eb76bec44926`. UI explicitly states **No changes yet**. This confirms live read-only preview wiring and proposal-to-path planning, **NOT** an actual archive revision, backup, source retention, FLAC audio re-verification, SQLite rebind, or crash recovery. Next acceptance checks: ensure archive and `/config` Collection DB have restorable backups and enough free space, verify whole-archive scan and Anastacia preview, then perform any apply only after explicit operator review. Boulez 6CD boxset remains ineligible for single-disc apply. Keep original archive untouched until approved.

---

## Seven operator-approved metadata events; LABEL alias correction and developer handoff (2026-11-20)

The operator supplied 7 historical metadata decision events in the live Unraid UI, including accepted `LABEL = Deutsche Grammophon` for `Disc 06` (21:57:37.921509 UTC) and `Disc 04` (21:57:41.643189 UTC) of *Boulez Conducts Stravinsky* (2010), MusicBrainz release `423f636d-742d-47b0-9ba2-51515a6fdfd2`; previous accepted Carmen Gomes Inc. (catalog number CGi2010 and CFMusic label) and Anastacia (Daylight/Epic) remain in the audit. **Acceptance is approval only, not evidence that FLACs or the multidisc album were migrated.** Multidisc migration remains explicitly unsupported in the v1 versioned migration engine.

PR #98 (merged; GitHub Tests and Docker build green, real-Unraid label-tag acceptance pending). Root cause of repeated label additions: `archive_metadata_scan._fresh_values` checks actual FLAC `LABEL`, not Collection `label` or archived `label_info`, and initial metadata staging previously did not emit `LABEL` despite fetching label information. Merged changes fix new staging to populate `LABEL` from the exact MusicBrainz release (including multi-label releases); recognizes legacy `RECORDLABEL` as an alternative for read-only scans and Collection indexing; conflicting simultaneous `LABEL` and `RECORDLABEL` are treated as an unsafe discrepancy. Previously accepted `LABEL` decisions are not discarded or silently applied. CI and live Unraid validation are separate requirements.

New **[DEVELOPER_HANDOFF.md](DEVELOPER_HANDOFF.md)** preserves a reusable future-chat context: exact code map, latest operator evidence, safe architecture constraints, open issues, PR workflow, validation gates and next recommended actions. It complements rather than duplicates this canonical project status, progress dashboard and detailed lifecycle design. Its contents need updating after each significant milestone; no personal access tokens are stored.

---

## Open-source onboarding — draft Compose and planned Getting Started (2026-11-20)

**Documentation draft created, NOT validated for publication:** [`compose.unraid.example.yml`](../compose.unraid.example.yml). This is a thoroughly commented **Unraid/Portainer-specific example** inspired by the operator's own working Compose. The operator intentionally keeps **their existing production Compose unchanged**. Do not assume this sample is deployment-ready or use it to alter their current paths, mounted optical drives, UID/GID, br0 IP or security settings.

**Mandatory follow-up: thoroughly review the example together before treating it as recommended documentation.** The audit must cover:
- Docker Compose syntax via `docker compose -f compose.unraid.example.yml config` using test-only environment values and Portainer stack interpolation compatibility (including `${...}` required/default values);
- the correct current OSCAR environment flags, ports and runtime UID/GID, read-only root filesystem, tmpfs size, group/device access and Unraid shfs filesystem permissions;
- dedicated, nonoverlapping staging vs archive host paths; persistent Collection SQLite location, backups, release history and safety of destructive actions;
- secure external/private br0 networking, static IP and trusted-local-UI implications; a separate basic-bridge example for general Linux/Docker users;
- source-supported Discogs Personal Access Token `OSCAR_DISCOGS_PAT` instructions, secure storage, accurate MusicBrainz OAuth future-only status;
- opt-in `OSCAR_ENABLE_ARCHIVE_REVISIONS=0`, `OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH=0` safety defaults and the fact that `:main` is a development image;
- verify actual optical-drive behavior on Unraid and explicitly check beginner-readability and copy/paste outcomes with a clean test environment.

**Planned deliverable: `docs/GETTING_STARTED.md`**, written for people with no Docker experience, covering:
1. Plain-language image/container/stack/volume/bind mount/environment variable/network definitions and why OSCAR needs them.
2. Prerequisites (Unraid or Linux host, Portainer optional, Docker/Compose, sufficient disk space, CD drive, permissions, safe backup strategy).
3. Decide between simple default bridge with local published port and the advanced Unraid br0 network; explain network exposure and lack of an OSCAR user login.
4. Create host config/staging/archive directories and keep staging completely separate from archive; check owner UID/GID and CD-device access.
5. Generate/store a local RIP token, optionally connect Discogs PAT, explain MusicBrainz metadata lookup vs unimplemented OAuth.
6. Select the correct Compose, understand every placeholder, validate configuration and deploy through Portainer or Docker Compose.
7. Open OSCAR, identify the optical drive, inspect a disc, run a safe first verified staging rip, review metadata, publish only after explicit approval.
8. Verify the published archive/Collection, explain read-only metadata scans and the reviewed opt-in archive-revision path, backups and restore.
9. Beginner troubleshooting (missing `/dev/sr0`, permissions, disabled features, failing mounts, empty archive scan, MusicBrainz rate-limits, network/Portainer errors).
10. Update and roll back the image without deleting persistent data; where to ask for community support and how to file a useful GitHub issue.

**Open-source release principle:** make OSCAR reproducible by others, not just its original Unraid operator. Publish a conservative beginner-friendly bridge example and a separate power-user Unraid example only after review. Respect third-party credits/licenses and the repository's remaining distribution/licence acceptance work. Documentation work alone does not increase implementation progress percentages.

---

## Staging-independent Archive Metadata Migration — 2026-11-20 (PR #95 merged; real Unraid acceptance pending)

An opt-in, single-CD **archive revision** implementation was merged from `feature/archive-revision-migration` in PR #95 (commit `9250586`) after GitHub Python Tests and Docker CI passed. It previews exactly the existing `accepted` metadata proposals against the original published archive and current MusicBrainz CD medium, and calculates the new album directory (e.g. `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`). Upon explicit confirmation and with `OSCAR_ENABLE_ARCHIVE_REVISIONS=1`, a background worker creates an isolated, newly tagged archive copy; checks original and new FLAC hashes, audio STREAMINFO MD5, `flac -t`, the original CUE and extraction evidence; adds a child manifest with fresh publish ID and full parent evidence; promotes the new archive and retains the untouched previous generation under `.oscar-archive-versions`. A durable journal supports explicit recovery after a crash between filesystem changes and SQLite updates. The existing Collection row is rebound transactionally to the new path, preserving user-curated fields; approved proposal states change from `accepted` to `applied`, with audit events.

**No staging files required; nothing automatically applies on Accept or Scan.** Single-disc operations only; coordinated boxset migration is deliberately blocked. Archived original generations are never deleted. Operator must review destination path, storage needs, collision safety and recovery options before enabling this in Portainer. Full-archive scans additionally now discover OSCAR-shaped manifests directly under the archive root, even when a valid released leaf was not yet imported into Collection; malformed leaves are reported individually. Applying metadata to an unindexed album still requires Collection import.

**Validation status:** offline regression tests exercise approved catalog and label application, immutability of retained original bytes, parent manifest lineage, no new pending proposals after revision, database path rebinding, deliberately failed promotion rollback and interrupted-transaction recovery. These tests use synthetic FLAC stand-ins; GitHub Python Tests and Docker build are green. Actual `flac -t` integration was skipped on the runner because the CLI was unavailable, so real Unraid audio-integrity/shfs and crash-recovery validation remain necessary before treating production archive migration as accepted. Full design: [ARCHIVE_METADATA_LIFECYCLE.md](ARCHIVE_METADATA_LIFECYCLE.md). Progress percentages unchanged.

---

## Archive-wide metadata scanning and Discogs PAT naming — 2026-11-20 (PR #94 merged; Unraid test pending)

The operator requested **full-archive** scans as the normal Collection experience, instead of requiring album-by-album selection. Implementation: background per-album scan of every OSCAR-shaped published archive manifest under the archive root, including unindexed leaves, tracking total/processed/failed and reporting individual MusicBrainz/verification failures while continuing with the rest. Both existing scan modes and accepted/ignored suppression remain unchanged; exact per-album scan is kept under an Advanced expander. No staging required and no archive files changed. Whole-archive scanning does not require Collection import, but a specific album must be imported before applying a reviewed archive migration. The scan is deliberately bounded to 10,000 indexed leaves; worker progress is process-local, but proposals and decisions survive restart in SQLite.

The older **Fill missing labels from exact MusicBrainz release** button remains in an Advanced subsection because it writes missing `archive_items.label` data in Collection, whereas Archive Metadata Scan proposes reviewed FLAC tag additions. It should be retired after source-aware, approved archive metadata migration/reindexing supersedes it.

Discogs personal token environment renamed **`OSCAR_DISCOGS_PAK` → `OSCAR_DISCOGS_PAT`** in code, UI, README and tests; operator must update Portainer variable name when deploying. Token value is never copied to GitHub or logged. OSCAR already stores the MusicBrainz physical release UUID in FLAC tag `MUSICBRAINZ_ALBUMID`, the archive manifest `release_id`, and Collection `musicbrainz_release_id`; this does not prove pressing identity.

**Important:** PR #94 implements archive-wide read-only scans, not metadata application. The separate opt-in archive revision implementation is now tracked above; its Unraid acceptance remains pending. Separate operator-approved, rollback-capable migration remains required. GitHub CI / Docker and live Unraid test pending. See [ARCHIVE_METADATA_LIFECYCLE.md](ARCHIVE_METADATA_LIFECYCLE.md).

---

## Unraid acceptance — archive metadata decisions and history (2026-11-20)

The operator provided five persisted decision events on real Unraid:
- Carmen Gomes Inc. *Desire*, `CATALOGNUMBER=CGi2010`: accepted at 20:46:53 UTC.
- Carmen Gomes Inc. *Desire*, `LABEL=CFMusic`: ignored at 20:49:27 UTC, reopened at 20:54:43 UTC, accepted at 20:55:13 UTC.
- Anastacia *Freak of Nature*, `LABEL=Daylight; Epic`: accepted at 20:55:19 UTC.

This confirms real-world **Ignore → Reopen → Accept audit history** and cross-album decisions, without any archive apply operation. Persistence across a **container restart** and same-proposal suppression on a repeated scan are still separate acceptance tests. The history UI displayed a misleading **Reopen decision** button next to the superseded historical `ignored` event (and each accepted event). A targeted UI/backend fix now exposes `current_status` and `latest_event`, allowing the action **only** on the latest event when it represents the actual current accepted/ignored state. All historical events remain visible. No metadata or filesystem writes. **Fix CI and Unraid validation pending**; archive revisions remain future work.

---

## Reopen archive metadata decisions + catalog folder migration requirement (2026-11-20; PR pending)

Operator test: Carmen Gomes Inc. *Desire* has two durable decisions: `accepted CATALOGNUMBER=CGi2010` at `2026-11-20T20:46:53.576873+00:00` and `ignored LABEL=CFMusic` at `2026-11-20T20:49:27.220609+00:00`. The second Ignore was accidental and must be reversible. Feature branch adds **Reopen decision** in Collection decision history with authenticated API, rechecks the published archive revision and latest MusicBrainz value, restores a pending proposal and appends a `reopened` event without erasing the original decision. The operator can then Accept the reopened CFMusic label proposal. No FLAC or archive operation is performed.

**Future archive migration MUST incorporate directory naming for an approved catalog number**: `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]` → `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`. Require collision-free, verified, rollback-capable archive version creation and Collection path/index transaction; do not rename existing folders during proposal approval. Actual migration not implemented in this PR.

**Acceptance pending:** GitHub Tests and Docker build, then real Unraid Reopen → Accept → scan suppression/history. See [ARCHIVE_METADATA_LIFECYCLE.md](ARCHIVE_METADATA_LIFECYCLE.md).

---

## Archive Metadata Scanner — first real Unraid observation (2026-11-20)

**User-reported OSCAR Collection output for PR #89:** the published archive selection lists Anastacia *Freak of Nature* (disc 1/1), Carmen Gomes Inc. *Desire* (disc 1/1), and Boulez/Stravinsky boxset discs 4/6 and 6/6. A scan reported **2 value differences, 0 already accepted/ignored** for the selected Carmen Gomes archive, and the global pending queue displayed **3 proposals** in total:
- Carmen Gomes Inc. *Desire* (archived path `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]`): missing FLAC `CATALOGNUMBER` → MusicBrainz `CGi2010`; missing FLAC `LABEL` → `CFMusic`.
- Anastacia *Freak of Nature* (archived path `/archive/Anastacia/[504757 2] Freak of Nature (2001) [4b370e6c]`): missing FLAC `LABEL` → MusicBrainz multi-label values `Daylight`, `Epic`.

**Accepted evidence:** first real archive-backed detection and pending-proposal UI work on the operator's Unraid installation, including cross-album persistent queue display. Original archive bytes were reported unchanged. **Still pending:** real Unraid Accept/Ignore persistence/repeated-scan suppression/restart verification, full field coverage, and archive application/migration. Do not mistake the scanner's FLAC `LABEL` comparison for the separately curated/enriched SQLite Collection label field; multiple MusicBrainz labels must remain distinct, and manual curator values must not be silently overwritten. Label identity is valuable for edition review but does not alone prove mastering or physical pressing. No maturity percent increase for this bounded test.

---

## Archive metadata scanner and durable decisions — 2026-11-20 (PR #89 merged; Unraid test pending)

Implemented in a new feature branch: staging-independent **Scan archive for metadata additions**, **Scan archive for metadata changes**, permanent per-value **Accept/Ignore** proposal decisions and decision history in Collection. Each scan validates the existing published manifest and per-file FLAC SHA-256 and uses saved archive release, Disc ID and recording identities to query MusicBrainz via the shared rate limiter. Changes are only proposed when external values are nonempty and verified against the exact CD medium. The current supported comparisons are release catalog number/label/barcode and track title/artist; complex changed release/recording identities are blocked pending explicit higher-risk design.

Acceptance of a proposal currently means **approved for a later migration only**; it does not retag, rename, delete or publish an archive. Ignored proposals with the same semantic fingerprint are suppressed across scans and restarts, while a changed provider value becomes a distinct proposal. Fingerprints include archive manifest revision; historical decisions remain recorded in persistent SQLite. More nuanced re-proposals on reverted provider values, and an actual versioned archive migration, are follow-up tasks.

**Acceptance status:** PR #89 merged to main (commit `f25e374`) after successful GitHub Python Tests and Docker build. The feature still needs real Unraid smoke testing. A simulated absent staging directory is included in the automated tests. Carmen Gomes *Desire* (published ID `3908eef79f114450b0a7eb76bec44926`) is the first real planned test case. Import its published manifest into Collection first if needed. Never claim this feature applied new metadata to existing FLACs.

Architecture and deliberate v1 limitations: [ARCHIVE_METADATA_LIFECYCLE.md](ARCHIVE_METADATA_LIFECYCLE.md).

---

## Archive-first metadata maintenance — agreed design (2026-11-20; not implemented)

The operator established a non-negotiable lifecycle requirement: **staging files will eventually be removed, so archive metadata maintenance MUST work independently of staging.** Add two future Collection controls: **Scan archive for metadata additions** and **Scan archive for metadata changes**, returning human-reviewed proposals for metadata found or changed in sources such as MusicBrainz. Operators must be able to **Accept** or **Ignore** each concrete semantic change. Persistent source-aware, per-field decision fingerprints suppress repeated identical suggestions; a subsequently changed external value or materially different archive revision must be eligible for review again. Keep decision history and recoverable archive-version lineage.

This is **only a design commitment**. No scan endpoints, decision ledger, retention/cleanup action, or archive mutation has been implemented in this PR. Archive-backed revision publication must be an independently tested, non-destructive, explicitly approved operation preserving original extraction/TOC/CUE evidence and historical FLAC hash provenance; changing FLAC tags legitimately changes file SHA-256 and requires fresh verification, not silent manifest edits. The full architecture, implementation sequence and staging-absent acceptance tests are specified in [ARCHIVE_METADATA_LIFECYCLE.md](ARCHIVE_METADATA_LIFECYCLE.md).

The previously verified Carmen Gomes corrected catalog metadata and staging-only restaging remain intact. Do not infer a complete archive migration or readiness for staging cleanup until archive-first maintenance is operational and tested on real Unraid.

---

## Unraid acceptance — independent MusicBrainz metadata restaging (2026-11-20)

**Operator-observed result:** for the previously published Carmen Gomes Inc. *Desire* job `b68488f667cc492d8dd94f90717cdb28`, newly created staging copy `cd2959e6cc2b4c4ab6fafb590808b2db` reported **`tagged_copy_ready_for_review`**, followed by **`tags_match_preview`** for all **12 tracks** after actual FLAC tag/hash inspection. The application explicitly reported **no archive publication performed** and **historical archive remains untouched**.

This completes the real Unraid test for the **new isolated staging copy and its integrity/read-back workflow**, following the previously verified read-only 14-change MusicBrainz catalog comparison (`CGi2010`, `CFMusic`, 12 proposed track CATALOGNUMBER tags). It does not prove an independent filesystem audit, physical pressing identity, successful catalog migration, or replacement of the already published archive. The old archive's durable publication ID remains `3908eef79f114450b0a7eb76bec44926`. Preserve both copies and the original rip.

**Next development:** separate explicitly approved, audited archiving migration with preview of old/new paths, manifest and FLAC hash verification, rollback, and Collection SQLite reconciliation. No automatic deletion, overwrite or reset of the historical Go ledger.

---

## Real Unraid test — MusicBrainz metadata refresh returns corrected catalog number (2026-11-20)

**Observed operator GUI evidence for PR #84:** existing Carmen Gomes Inc. *Desire* (2010) job `b68488f667cc492d8dd94f90717cdb28` now reports **14 metadata changes** during the authenticated read-only comparison: album `catalog_numbers: [] → ["CGi2010"]`, release label `CFMusic` catalog-number `null → "CGi2010"`, plus `CATALOGNUMBER` added to the *proposed* tags of all twelve tracks. This confirms that MusicBrainz's updated catalog field has become available to OSCAR and that old/new metadata comparison behaves as designed.

**Boundary of validation:** user has not yet reported creating or inspecting the new independent staging copy. The comparison does not retag the previously published archive, rename its folder, adjust the Collection SQLite record, or alter the historical `ARCHIVE_PUBLISHED` job. The catalog number should be corroborated against the actual physical disc/booklet; the Disc ID association alone does not prove the edition.

**Next acceptance test:** with the physical catalog verified, explicitly create a new reviewed staging copy; confirm `tagged_copy_ready_for_review` and `tags_match_preview` (all 12 FLACs); only then design a separate opt-in, audited archive migration with safe catalog reconciliation, never deletion or manual workflow reset.

---

## Fresh MusicBrainz metadata comparison and independent restaging — 20 November 2026 (PR #84 merged; Unraid acceptance pending)

New isolated implementation on `feature/metadata-refresh-reprocess-preview` lets an operator reload current MusicBrainz data **for an already accepted Semi Automatic Go! release**, compare it against the previous integrity-checked tagged staging copy, then optionally create a **new independently identified metadata staging copy** with an explicit confirmation and a freshly rechecked preview fingerprint. The old staging files, old tagged copy, durable `ARCHIVE_PUBLISHED` ledger, existing archive directory and Collection SQLite are never rewritten by this flow. Its public API/GUI does not offer archive replacement.

**Carmen Gomes Inc. — Desire:** user reports adding the physical catalog number to MusicBrainz after the old publication, which was previously named without catalog number. Whether MusicBrainz currently returns that number remains **unverified until real Unraid UI lookup**. User expects the new comparison to surface the exact number, if present. Read-back checks of both old tagged metadata copy and the optional newly created copy are essential. Never guess the physical catalog number from another edition; only print what current MusicBrainz returns, and request user confirmation against CD packaging.

**Acceptance state:** source code, regression tests and [METADATA_REPROCESS.md](METADATA_REPROCESS.md) merged via PR #84 (commit `c5625a7`) after passing GitHub Tests and Docker build. Live Unraid comparison and optional staging-copy validation remain pending. Do not mark reprocessing or physical pressing verification completed from simulated tests. Design of any archive replacement, rename, and catalog migration remains a separate future task.

---

## Collection indexing correction — Carmen Gomes Inc. *Desire* (2026-11-20)

**Operator-observed discrepancy:** Go! reported publication `3908eef79f114450b0a7eb76bec44926` as `ARCHIVE_PUBLISHED · catalog: indexed`, but Collection's manual import returned `Imported 0 new archive record(s)` and the collection remained at three local records (Anastacia and two Boulez boxset discs). Thus the earlier `indexed` report was a false-positive claim for this release, not proof that the SQLite catalog contains it. The already-published FLACs, manifest and staging evidence must not be touched.

**Root cause found in code:** archive publishing legally names an edition without a catalog number `Carmen Gomes Inc/Desire (2010) [fa89edc1]`, but `collection_catalog._ALBUM_DIR` previously required a `[CATALOG] ` prefix. The importer silently skipped that valid published folder. Separately, the publisher/reconciler reported `indexed` whenever import returned normally, without confirming the row was present.

**Fix:** accept the publisher's existing catalogless naming form while still checking the MusicBrainz release prefix, year, disc layout and publication manifest. Return `indexed` for a specific import only if a matching SQLite `archive_path` row exists. Publisher and Go! reconciliation use this result before reporting `indexed`. No archive renaming, metadata rewriting, reripping, destructive changes or automatic re-publication.

**Physical release catalog metadata warning:** the operator confirmed that *Desire* was supposed to have a catalog number, but its selected MusicBrainz release did not supply one. Before archiving future physical CDs, the standard read-only archive review now raises `missing_release_catalog_number` when its saved MusicBrainz metadata has no nonblank catalog number. The warning requires explicit acknowledgment under the existing approval gate; OSCAR never invents a printed number. The reported `CGi2010` from prior release review still needs verification against the physical CD/booklet before any MusicBrainz edit. Existing published folders, manifests, FLAC tags and prior approvals remain untouched. Adding a number to MusicBrainz later does not retroactively rename a published archive: any such repair must be separately reviewed and non-destructive.

**Acceptance:** GitHub tests and Docker build must pass before merge. After deploying, explicitly click **Import published archive records** in Collection, then **Refresh collection**. The expected result is one additional Carmen Gomes Inc. *Desire* record, 12 tracks, `catalog_number` empty (not fabricated), `INFERRED_OPERATOR_ACCEPTED`. If not visible, inspect the importer result and configuration/mount paths; do not re-publish the same audio. The pre-fix durable ledger `indexed` value is historical and cannot itself be taken as current catalog evidence.

**Follow-on:** improve Collection UI diagnostics for skipped manifests if necessary, then resume MusicBrainz edit-note UX and OAuth collection read access.

---

## Unraid acceptance result — MusicBrainz Match Refresh (2026-11-20)

**Observed directly in the operator's OSCAR UI:** PR #79's read-only refresh succeeded on historical staging job `b68488f667cc492d8dd94f90717cdb28` for Carmen Gomes Inc. *Desire* (2010), accepted MusicBrainz release `fa89edc1-32f9-4290-8788-bbac2e366a46`, Disc ID `VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-`. OSCAR reported **"Saved Disc ID is now attached to the accepted release · medium 1"** while preserving `INFERRED_OPERATOR_ACCEPTED`. The workflow was `METADATA_READY`, `semi_automatic`, with tagged staging copy `9af8f01c736843ff8f53a1d7e8af2b56`; archive preview listed 12 tracks and proposed `Carmen Gomes Inc/Desire (2010) [fa89edc1]`.

**Interpretation:** operator-observed functional acceptance for the match refresh is complete, beyond passing CI. The UI explicitly confirms no metadata or archive changes caused by the refresh. A fresh external Disc ID association is not independently verified physical pressing identity, and this test does not demonstrate new archive publication or independent file-system hash comparison. The preview showed no automatic metadata consistency warnings, which is not proof of metadata correctness.

**Next features:** deterministic, evidence-bound MusicBrainz edit-note preview/copy UI; thereafter MusicBrainz OAuth read-only collections and comparison with Discogs and OSCAR. These remain unimplemented. The separate branding artwork upload and Unraid visual acceptance also remain outstanding.

---

## MusicBrainz accepted-match refresh — 20 November 2026 (PR #79 merged; Unraid test accepted)

The next OSCAR change adds an authenticated, read-only **Refresh MusicBrainz match** button for explicitly accepted Semi Automatic Go! jobs. It reuses the original saved physical TOC, Disc ID, completed per-track verification and accepted release UUID to fetch fresh MusicBrainz medium information. A newly attached Disc ID is displayed as fresh external evidence; original `INFERRED_OPERATOR_ACCEPTED` history, tags, archive and audio remain untouched. No physical-edition verification is inferred from a database association.

**Release acceptance case:** Carmen Gomes Inc. *Desire*, job `b68488f667cc492d8dd94f90717cdb28`, release `fa89edc1-32f9-4290-8788-bbac2e366a46`, original Disc ID `VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-`. This was subsequently confirmed in the operator's real Unraid OSCAR UI, as documented above. Implementation, test cases and operator acceptance checklist: [MUSICBRAINZ_MATCH_REFRESH.md](MUSICBRAINZ_MATCH_REFRESH.md).

**Outstanding next phases (not in this change):** locally generated factual MusicBrainz edit-note templates, MusicBrainz OAuth read-only collection access, local/Discogs/MusicBrainz collection comparison and separately approved sync. Keep `OSCAR_MUSICBRAINZ_ID` and `OSCAR_MUSICBRAINZ_CS` exclusively server-side.

**Branding status correction:** PR #78 was merged into main as presentation-only integration; the operator's binary PNG files and a successful Unraid appearance test remain separate outstanding tasks. Its earlier draft-only note below is historical context, not current status.

---

## GUI branding integration — 20 November 2026 (draft PR; assets pending)

A dedicated `feature/oscar-branding-assets` branch adds a responsive OSCAR header, 16×16/32×32 favicons, mobile touch icon declarations, safe allowlisted image-serving route, source package-data declaration and branding regression tests. The existing Go! / Review / Collection / Settings navigation and all ripping, archive and collection workflows are unchanged.

**Not complete or deployed:** the original operator-supplied binary artwork cannot yet be committed through this text-only GitHub changeset. The exact original header and derived favicon exports are available in the separate `OSCAR-branding-assets.zip` handoff. Keep the PR as **draft**, copy the PNG files to `src/oscar/assets/`, run CI and desktop/mobile Unraid smoke tests, and only then approve merge. Missing artwork falls back to the old OSCAR text heading; no existing archive data changes.

See [BRANDING.md](BRANDING.md).

---

## Status reconciliation — 2026-11-20: hardware, Disc ID, Collection, OAuth next phase

**Verified user reports (not just CI):** OSCAR Collection shows three `published_verified` disc records: Anastacia *Freak of Nature* (12 tracks), and *Boulez Conducts Stravinsky* CDs **4/6** (7 tracks) and **6/6** (32 tracks). The latter were confirmed in Unraid file manager as separate `Disc 04` and `Disc 06` folders inside the **same** `[6CD 477 8730 GB6] Boulez Conducts Stravinsky (2010) [423f636d]` boxset directory. This proves distinct boxset discs were published and indexed without overwriting one another; it does not prove the entire 6-CD set is archived or pressing identity.

**Carmen Gomes Inc. — Desire:** historical job `b68488f667cc492d8dd94f90717cdb28`, accepted release `fa89edc1-32f9-4290-8788-bbac2e366a46`, catalog reported `CGi2010`, 12-track original CD. PR #74 allows a narrow operator-accepted, single-medium CD staging metadata path when MB has no attached matching Disc ID, without claiming edition verification. PR #75 adds a user-confirmed TOC attach-page handoff, and PR #76 provides an accepted-release prefilter. The user successfully attached real Disc ID **`VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-`**, full TOC `1 12 251219 150 24080 45782 68279 94060 110749 132469 152116 171031 192808 211313 231287`, 55:50, to MusicBrainz medium 1/1 on the selected release. The previously displayed printed-booklet lengths differ from CD TOC lengths; the user established their origin. Do **not** assume the job's persisted `INFERRED_OPERATOR_ACCEPTED` status or any cached MB lookup has automatically refreshed. A fresh matching-Disc ID reconciliation is needed, keeping historical approval provenance.

**Implemented vs proposed:** libdiscid TOC reading; saved rip TOC; explicit MusicBrainz URL submission handoff; semi-automatic Go! → independent source verification → acceptance → isolated metadata copy → explicitly approved archive; local published-record Collection and Discogs read-only PAK operations **implemented**. Live MusicBrainz collection OAuth, multi-platform collection comparison or remote collection writes, and in-OSCAR edit-note templates are **not implemented** as of this update.

**MusicBrainz OAuth and multi-platform Collection design decision:** register OSCAR as a MusicBrainz OAuth application. Use exactly `OSCAR_MUSICBRAINZ_ID` (OAuth client ID) and `OSCAR_MUSICBRAINZ_CS` (OAuth client secret) in Unraid/Portainer server-side environment, alongside existing `OSCAR_DISCOGS_PAK`. User already reports creating the MusicBrainz application and setting secret environment variable; **never** publish actual credentials or user OAuth tokens. Decide configured public redirect URL and suitable client type before implementation. Secure authorization-code OAuth with state/PKCE as supported, server-side token storage, refresh/revocation, explicit minimum collection permissions and read-only listing first. A server-side OAuth integration should not expose the secret to the browser or GitHub. Collection membership is at **release level** in MusicBrainz; OSCAR's real-world owned copies and individually archived boxset discs must remain independent.

**MusicBrainz edit note UX (planned):** generate an English factual template locally using the release UUID, physical source evidence, saved libdiscid TOC, actual track count, known catalog number and optional user-confirmed printed-booklet/TOC differences. Show preview and copy/paste; no paid/free remote AI required, no invented physical evidence or automatic submission.

**Planned GUI branding (new request, not yet deployed):** use the operator-supplied `OSCAR-header.png` as the main GUI header artwork and `OSCAR-favicon.png` as the browser favicon. Preserve image aspect ratio and readability on narrow/mobile screens; define sensible favicon PNG sizes and favicon HTML links; avoid altering existing Go! / Review / Collection / Settings functionality. The actual binary artwork must be sourced from verified supplied files and added separately to the GitHub repository before claiming the change implemented. This is **not part of the current documentation-only PR**.

**Development priority order:** (1) fresh MusicBrainz Disc ID refresh for accepted Carmen Gomes job; (2) deterministic edit-note UX; (3) MusicBrainz OAuth read-only collections; (4) joined local / Discogs / MusicBrainz collection comparison; (5) preview-only, explicitly approved idempotent collection synchronization. See [PROGRESS.md](PROGRESS.md), [AUTOMATION_ROADMAP.md](AUTOMATION_ROADMAP.md), [DISCOGS_COLLECTION_CATALOG.md](DISCOGS_COLLECTION_CATALOG.md). PR #76's source link prefilter should be tested in the next deployed build, even though initial PR #75 handoff was tested by the user.

---

## MusicBrainz missing Disc ID — operator-controlled GUI submission handoff

**Implemented in this PR: GUI link preparation, NOT MusicBrainz editing.** Go! displays **Add missing Disc ID to MusicBrainz (manual review)** after an expressly accepted Semi Automatic release. The API `GET /api/go/jobs/{job_id}/musicbrainz/discid-attach` uses the *persisted original physical CD TOC* from `plan.json`; no disc has to be reinserted and OSCAR does not use hashes/track names to synthesize a TOC.

The authenticated API checks: the saved job is Semi Automatic with `INFERRED_OPERATOR_ACCEPTED` and a matching accepted release; complete, successful source verification and per-track passes; strictly structured physical TOC offsets and lead-out; track count and Disc ID agreement with saved plan/state; a live MusicBrainz release lookup that finds a **single compatible CD medium** with the right track count and no matching attached Disc ID. Multi-disc ambiguity, bad/stale TOCs, an unresolved release, and unverified audio are blocked.

On success the interface displays the Disc ID and selected release and offers `https://musicbrainz.org/cdtoc/attach?toc=...` as a clickable link. **MusicBrainz, not OSCAR**, handles login, selection of the correct release/medium and explicit edit confirmation. OSCAR does not send a submission, store MusicBrainz credentials, or claim the association succeeded. This avoids silently mutating a shared database and allows users to inspect physical catalog and full track listing first. After any external edit, a later fresh lookup may see the Disc ID; existing inferred provenance is **not retroactively reclassified** as physical-edition verified.

**Hardware follow-up:** Carmen Gomes Inc. `Desire`, job `b68488f667cc492d8dd94f90717cdb28`, release `fa89edc1-32f9-4290-8788-bbac2e366a46` (12 tracks). Test only after deploying this update. Review the MusicBrainz attach page manually and check catalog `CGi2010` and complete tracklist. Never attach a TOC to a different physical edition or rely on track count alone as conclusive proof.

**Future only (not part of this feature):** full authenticated MusicBrainz account integration and in-app edit submission, if desirable, must use a supported MusicBrainz edit API, OAuth, explicit approval, durable auditable status and no automatic edits.

---

## Semi Automatic — operator-accepted single-CD metadata without attached Disc ID

**Implementation in this PR; hardware acceptance still pending.** Real-world driver: Carmen Gomes Inc., *Desire* (2010), catalog `CGi2010`, 12 tracks, job `b68488f667cc492d8dd94f90717cdb28`, accepted MusicBrainz release `fa89edc1-32f9-4290-8788-bbac2e366a46`. Its `RELEASE_ACCEPTED` job previously stopped with `Release does not have one exact Disc ID + track-count medium` despite successful audio verification and saved operator acceptance.

A narrowly scoped alternate metadata path is now available **only** if all of these are true:

1. Workflow is **Semi Automatic** and the stored `accepted_release_id` exactly equals the selected release, with `INFERRED_OPERATOR_ACCEPTED` status. Best Guess or Secure may not use the bypass.
2. MusicBrainz has **no matching Disc ID medium** for this CD, and the release consists of **exactly one medium**, explicitly marked `CD` and positioned as disc 1.
3. The CD medium has the **same track count**, a complete ordered list of track titles and valid medium position. Existing staging FLAC manifest, SHA-256, decode and AccurateRip gates remain mandatory.
4. Metadata preview marks `medium_match_method=single_cd_operator_accepted_track_count_only`, explicitly says **NO attached matching Disc ID**, and warns that neither physical edition nor Disc ID match has been verified. It still needs metadata, physical-packaging and final publication review.
5. No source FLAC, CUE, rip log, verification record or existing archive is modified. The tagged copy is isolated and retains this inference provenance.

**Not allowed:** guessing a disc in a multi-disc boxset by track count, using a Digital Media edition as a CD medium, accepting multiple or conflicting matching media, silently adding a Disc ID to MusicBrainz, or treating the user's earlier release acceptance as proof of physical-edition identity.

**To test on Unraid:** after update, open the saved Carmen Gomes job in **Go! → Check next safe step**, inspect the separate tagged-copy review and only then approve archive if the real cover, catalog `CGi2010`, complete 12-track listing and music metadata match. If MB's release is not a unique, single CD or metadata is missing, OSCAR must remain in review. A separate **opt-in MusicBrainz Disc ID submission** remains a future task and is not performed by this change.

---

## Review UI — explicit Reverify saved rip button

The Review tab offers an explicitly confirmed **Reverify saved rip** action for tracked jobs in `VERIFICATION_PENDING`. It reuses OSCAR's authenticated `POST /api/rip/jobs/{job_id}/verification` endpoint and polls the existing report endpoint, displaying outcomes in the relevant job row. The user need not manually copy the job ID or use the terminal.

The action rereads saved FLACs, the manifest, cyanrip log, CUE and AccurateRip evidence; it does **not** rip again, overwrite FLAC/CUE/log, change metadata or publish an archive. Existing `verification.start()` behavior preserves previous unsuccessful reports as timestamped backup files before replacing the report. A successful reverify still requires the standard Go! advancement action and all remaining release and archive approvals. No automatic reverify on restart or repeat loops.

**Known UX caveat:** the already-saved report can remain visible until a fresh background verification finishes. During reverify the UI explicitly shows the running state; it is not evidence of a code regression to see the old report before the new check completes. Inspect the report's modification timestamp if a stale result appears. The Anne-Sophie Mutter job `940a5de1542d4a54ab4a4020efef283c` had a known previous `Unexpected FLAC path in manifest` report. After the PR #72 filename fix, the operator reported a successful reverify of the seven-track disc, including saved CUE, AccurateRip v1/v2, SHA-256 and FLAC decode checks.

---
## Proposed future feature — RipRepair (damaged-CD recovery)

**Scope:** the broader repeat-rip scheduling and comparison design below came from the Roxy Music trial. The narrower Track Recovery v1 now supports explicitly selected local diagnostic replacements in a new staging job, independently verified before entering Semi Automatic Go! ([#134](https://github.com/sin7ek/OSCAR/pull/134), [#136](https://github.com/sin7ek/OSCAR/pull/136)). Automatic bounded retries and external replacements remain design work.

### Goal and trigger

When a complete rip ends in `verification.review_required` because some tracks cannot be positively confirmed by AccurateRip, offer an **opt-in RipRepair** workflow. Never silently mark a damaged disc as verified. A completed rip with a decodable FLAC and matching saved SHA-256 can still contain incorrectly read audio.

### Suggested acquisition strategies

- **One available drive:** make **two or three independent complete extraction attempts** with the same calibrated drive, each in a new immutable staging job. Allow a third attempt after comparing the first two; impose a bounded attempt limit rather than retrying indefinitely.
- **Multiple available drives:** preferentially rip **once with each distinct calibrated drive** (up to three for the initial design). Different transports can recover different damaged regions. If necessary, offer extra passes explicitly rather than automatic unlimited re-rips.
- **Same-disc evidence:** check the disc TOC and exact per-track boundaries, sector counts, count/order, drive read offsets and sample alignment before comparing data across attempts. Matching album titles or MusicBrainz release IDs alone is not sufficient; do not cross-match different editions/pressings, pre-emphasis layouts, hidden audio, or incompatible read offsets.
- **Never interfere with other running jobs:** coordinate available drive slots and avoid reripping a busy drive. Preserve each original FLAC, CUE, cyanrip log, verification report, hashes, and original Go! job record.

### Track-by-track comparison and recovery decision

1. Generate a **read-only comparison matrix** for all attempts: track number, TOC/sector boundaries, EAC CRC32, per-track AccurateRip v1/v2 status/confidence, cyanrip `Accurip 450` partial confirmation if present, SHA-256 and `flac -t`, drive and attempt provenance.
2. **Prefer a fully AccurateRip-confirmed track** from an attempt with correct TOC, valid encoding and integrity checks. If multiple attempts have positive matches, preserve their sources and show consistency; do not conflate a confidence number with physical pressing identity.
3. If there is **no full AccurateRip match**, report exact repeatability (matching checksums/audio after correct offset alignment) separately from independent database confirmation. Multiple identical reads — especially on the same drive — are supporting evidence, **not proof** of an error-free extraction.
4. `Accurip 450` / partially accurately ripped means **partial evidence only**; it must not automatically upgrade a track to fully verified.
5. Never silently manufacture audio by splicing mismatching sectors or recombining arbitrary partial reads. Any future sector-level repair requires a separately designed, audited and tested algorithm and strict sample alignment.
6. If and only if every selected track individually satisfies the existing rigorous verification gates, an **explicitly approved new derived assembly** may be considered for archive review, with an immutable manifest mapping each track to its exact originating attempt, filename, hash, verification method and drive. No original staging data is rewritten.
7. **If any track remains uncertain, the whole assembled album remains `review_required`**; the UI may show recovered/partially confirmed/unresolved track counts and offer manual follow-up, but cannot label the archive `published_verified` or invoke the current automatic publisher.

### Real-world motivating evidence — Roxy Music

- First Optiarc attempt `4d800edef9a24f16b50aff9085b82c5f`: **4/10** tracks fully AccurateRip-confirmed (1, 4, 5, 6); partial Accurip 450 reported for tracks 2, 7 and 9, but not full verification.
- Second Optiarc attempt `0725bffd859d4208814526f2cbc7fed9`: **5/10** fully confirmed (1, 2, 4, 5, 6). Track 2 CRC changed from `9DE54BC6` to `3F94EC30` and now has full v1/v2 confirmation. Tracks 3, 7, 8, 9 and 10 remained unconfirmed; their EAC CRC32 values differed between attempts. Both attempts reported zero ripping errors and passed FLAC decoding and saved-file SHA-256 checks, which alone do not establish audio accuracy.
- Thus the second attempt recovered at least **one additional fully verified track**, while the album must remain under review.

### RipRepair provenance and experimental opt-in — inspired by The Ruffneck Anthology

**Scope:** [#138](https://github.com/sin7ek/OSCAR/pull/138) ships provenance for new regular and locally recovered publications; open [#139](https://github.com/sin7ek/OSCAR/pull/139) adds both attempted sources on new recoveries. External digital acquisition remains a design. Treat audio verification and source provenance as **two independent dimensions** throughout the UI, review decisions, archival manifests and Collection. A collection can have every track positively verified, while still being an explicitly **HYBRID / REPAIRED CD RIP** rather than a pristine all-original physical CD extraction. Never silently rewrite this distinction after AR or CTDB verification.

**Reference case — The Ruffneck Anthology, part VI:** a physically damaged original CD rip contained a problematic track 16. An externally obtained Soulseek track was used as the verified replacement, the original failed FLAC retained under `Verification/FailedAttempts/`, CUETools validation log retained, and `SOURCES.txt` updated with original and replacement SHA-256 hashes and precise track provenance. The final assembled result reportedly passed AccurateRip **17/17** and CTDB **17/17**, yet remained a **hybrid/repaired CD rip**. The other 16 tracks were left untouched. It is crucial not to represent the replacement as audio actually extracted from the owner's original physical disc. This provenance case is an operator-provided prior workflow; it does not confer physical-edition proof on unrelated downloads.

**Mandatory origin labels, independently of verification state:**

- `PHYSICAL_CD_RIP` — every selected audio track originates from the user's own physical CD extraction; repeated attempts/multiple drives must still be recorded.
- `DIGITAL_ACQUISITION` — a digitally obtained album/track without a claim of physical extraction by OSCAR. Never invent a source EAC/CUE log or claim a known ripper/pressing if it is not established.
- `HYBRID_REPAIRED_CD_RIP` — a selected album assembled from a physical rip and one or more replacement tracks, whether from another local rip, other drives, backup or external sources. Show the **hybrid/repaired** status even if every selected track has independently passed AR/CTDB verification.

**Suggested archived manifest and human-readable provenance (design):**

- Immutable album-level `SOURCE_TYPE`, `REPAIR_STATUS`, `REPAIR_METHODS`, `REPAIR_AUDIT_ID`, `SOURCE_JOB_IDS` and a visible review banner in **Go!**, **Review**, **Collection** and export reports.
- Per-track record: original disc job/drive/offset, candidate and attempt ID, physical or external origin, original path, selected path, cryptographic hashes before/after, relevant EAC CRC and independently obtained AR/CTDB proof, whether selected or excluded, time and explicit operator approval. A replacement track must never inherit the original rip's EAC log or pretend it was ripped by that drive.
- Retain original defective FLAC under its immutable staging job (optionally surface an archival `Verification/FailedAttempts/` reference copy), store all relevant validation logs and emit a transparent, human-readable `SOURCES.txt` or `REPAIR_REPORT.md` alongside a machine-readable provenance manifest.
- A repaired album must remain searchable/filterable as repaired/hybrid. `published_verified` describes the audio verification decision **only**; it does **not** overwrite the origin label or mean that every track comes from the owner's CD. Do not automatically create a fabricated single-drive CUE/EAC extraction log for a derived hybrid assembly.

**Experimental Zone (external-download adapters only):**

1. Default **OFF**; expose behind an unmistakable **Experimental / External Sources** section under Settings and a corresponding gated action in Review → RipRepair. Keep multi-pass physical ripping and local backup verification available outside this opt-in.
2. Require affirmative, persisted operator opt-in acknowledging technical, metadata/pressing, privacy/security and copyright/licensing risks; an explanation alone or unchecked box must not grant permission. Enable via a dedicated server-side setting/flag, not a client-side visual toggle alone. Disabling it immediately blocks *new* searches/transfers, while retaining audit history and existing candidate files for review.
3. Independently gate **search**, **download/import**, and **use in a repair assembly**. An opted-in search is not a blanket authorization for future downloading, merging or publishing. Each retrieval and each repair assembly requires an explicit selected candidate and operator confirmation; archive publication remains a separate approval.
4. Limit connectors to operator-configured, authenticated instances and lawful/authorized sources. Use server-side secrets, least-privilege permissions, request timeouts, bounded result/transfer limits, quarantine staging and no direct access to the final archive. Log only safe, necessary provenance; do not expose connection tokens, private peer details or raw download URLs in public reports.
5. Display an unambiguous warning that remote FLAC metadata, file hashes, alleged AccurateRip/CTDB logs and source filenames do not prove physical pressing identity or accurate audio. Only a separate independently confirmed whole-track result can satisfy existing verification gates, and no opt-in can turn an unverified candidate into `published_verified`.
6. In the UI, use a permanent **HYBRID / REPAIRED** provenance indicator for the resulting album plus a per-track sources comparison, without relying on a single decorative label. These must survive restarts, catalog indexing, export and archive restore.

**Acceptance tests to add before implementing:** opt-in default OFF; server rejects searches without opt-in; search vs transfer vs assembly approvals are independent; opt-out disables subsequent remote actions; unverified remote FLAC cannot pass publishing; persistent hybrid flag survives full verification, restart, publication and catalog export; full track-level provenance and original rip files remain immutable; no fabricated EAC/CUE provenance; physical-only repair path unaffected.

### Proposed external-source recovery — RipRepair Source Finder

**Design only; not implemented.** Add a third opt-in recovery lane alongside second/third physical reads and alternate drives: **search for a suitable externally acquired track or album, then independently validate it**. Never treat source filename, user description, shared log, FLAC format, checksum of transfer, or "AccurateRip" wording as proof of an accurate CD extraction.

**Potential adapters (optional, provider-independent):**

- **slskd / Soulseek**: use authenticated slskd search and transfer-status APIs to discover candidates and show them to the operator. Initial implementation should be **read-only discovery / candidate preview**, with an explicit authorized acquisition step later; never silently fetch material or alter another app's queue. Keep the user's existing slskd installation isolated from OSCAR's staging, use least-privilege credentials and no token exposure in the browser/logs.
- **Lidarr**: optional discovery and acquisition routing through the user's configured Lidarr, whose download clients can include Usenet (SABnzbd, NZBGet), BitTorrent (qBittorrent, Transmission, Deluge) and optional slskd plugins. Lidarr's match is *album metadata*, not independently verified audio. Avoid coupling RipRepair to Lidarr as a required dependency.
- **Local archive / personal backup import**: first-class candidate discovery against separately stored, operator-owned verified FLAC/CUE/logs. Prefer this source before remote retrieval, with read-only import and evidence preservation.
- **Authorized lossless download sources**: Qobuz download store, Bandcamp, labels and other sellers where usable downloads can be acquired legitimately. A digital master may differ from the pressed CD even when title, ISRC, duration and bit depth look similar; label/store authenticity does not prove CD-accurate sector identity.
- **qBittorrent / SABnzbd**: generic transfer engines rather than proof-of-audio systems; treat as optional retrieval adapters only when users have a lawful source. No direct unreviewed import into published OSCAR archives.

**Candidate matching and integrity gates:**

1. Search with release/track metadata and optionally catalog/ISRC/duration, but identify candidates as *unverified*. Avoid claiming a particular pressing from tags or a MusicBrainz Disc ID alone.
2. Download/import only after explicit operator approval and appropriate access rights. Store as `riprepair-candidates/<candidate_id>` or equivalent separate non-archive staging with provenance: source type, timestamp, track, transfer hash, original filename, codec/sample rate/channels, linked rip job and immutable candidate ID. Do not write into the original rip folder.
3. Decode and validate lossless audio; ensure 44.1 kHz/16-bit stereo CD PCM compatibility when comparing to CD audio. Handle any resampling, lossy transcodes, different masters, hidden-track/index/pregap boundaries, offsets and track-length differences as review conditions rather than silent normalization.
4. If a trustworthy, complete CD TOC/CUE/track-boundary reconstruction exists, attempt **independent** AccurateRip or CTDB verification of the candidate using tools such as CUETools. CTDB verification requires compatible CD layout. Log-provided AR/CTDB claims from a remote peer are not a substitute for OSCAR's own check. A transferred file's SHA-256 validates transport stability, not original CD accuracy.
5. Compare exact decoded samples (with rigorously established boundaries/offset alignment) against the user's rip attempts. Audio fingerprint, track title or duration alone establishes likely musical identity, **not byte-perfect or pressing-equivalent accuracy**.
6. Only a whole track with independent positive evidence satisfying the existing archive verification policy may be selected into a proposed *derived* repair assembly. Track provenance records which physical drive/rip or external candidate supplied the audio, whether it was independently AccurateRip/CTDB-confirmed, and exactly how. Never splice sectors automatically.
7. If independent validation is inconclusive, preserve the candidate separately as `external_unverified` and keep the original album `review_required`. Do not promote an official digital download or peer-provided track to `published_verified` merely because it sounds identical. Respect source rights/terms and never automatically distribute uploaded/downloaded files.

**UI and delivery milestones:**

- **RipRepair Source Finder** in the Review tab, initially searching *local backup sources* and offering optional read-only slskd result discovery; show exact match confidence vs audio-verification status as distinct fields.
- Later explicit user-authorized acquisition and a sandboxed third-party file inspector (FLAC/PCM, metadata, candidate CUE, track duration/TOC, waveform-aligned checks, optional CUETools verification).
- Finally a separate, operator-approved track selection/derived-copy flow with testable manifest provenance; no automatic publisher bypass. Credentials only via protected server-side settings/Portainer, never checked into the repository.
- The source finder must preserve the original Go! job and avoid automatic retries, downloading, queue manipulation and archive publication unless those specific capabilities are built and gated.

**Integration research (2026-11-20):** [slskd](https://github.com/slskd/slskd), [slskd API client](https://slskd-api.readthedocs.io/en/latest/api.html), [Lidarr](https://github.com/Lidarr/Lidarr), [Lidarr.Plugin.Slskd](https://github.com/allquiet-hub/Lidarr.Plugin.Slskd), [CUETools verification](https://cue.tools/wiki/CUETools_Settings), [CTDB](https://cue.tools/wiki/CTDB), [Qobuz downloads](https://help.qobuz.com/en/articles/10168-how-to-download-albums-tracks-collections-or-complete-works). Recheck compatibility/licensing and provider APIs when implemented.

### Product / UI considerations

- In **Review**, offer an opt-in `RipRepair` action for eligible verification failures, with a clear explanation of what is and is not confirmed.
- Under **Go!**, show selected drives, bounded attempt plan, current status and per-track comparison; **Settings** may offer conservative defaults for maximum attempts and allowed drives, but never bypass proof requirements.
- Record all attempts and proposed selected tracks in persistent, restart-safe state. Require explicit approval before building any new derived copy and before publication; a restart must not silently launch extra ripping or publishing.
- First implementation milestone: **read-only comparator + provenance report** for separately staged attempts, with strict TOC/offset checks and test fixtures. Second milestone: operator-controlled repair/selection only for independently confirmed whole tracks, with full integration tests. Only after hardware validation consider bounded automatic acquisition.

**Non-goals:** declaring physical release identity based on Disc ID; turning partial AR evidence into full verification; altering the original FLACs/CUE/logs; overwriting an existing archive; enabling automatic publication of an ambiguous album.

---

## Unpadded cyanrip FLAC filenames — staging verification compatibility

Cyanrip 0.9.3 may output `audio/1 - Unknown track.flac` through
`audio/7 - Unknown track.flac` instead of zero-padded filenames.
An operator reproduced this in Go! job
`940a5de1542d4a54ab4a4020efef283c` (LG GH24NS95).
The old verification regex only accepted 2–3 digit prefixes, yielding
`RipError: Unexpected FLAC path in manifest` even though the rip
state reported `needs_verification` with seven FLAC hashes.

The strict verification *and* metadata staging path validations now
accept canonical 1–3 digit **nonzero** track numbers. Cyanrip log
evidence filtering and per-track parsing also accept non-padded numbers,
and metadata preview maps the original manifest path for each track.
Nested paths, traversals, duplicate numeric track IDs and unsafe names
remain disallowed. No source FLAC, CUE, saved hash manifest or rip
log is renamed, rewritten or deleted. SHA-256, FLAC decoding, exact
CUE filename references, AccurateRip confidence and rip error checks
remain mandatory. Track 1 and track 01 are not allowed simultaneously
for the same track.

Regression fixtures cover unpadded verification, log parsing and metadata
preview and rejection of unsafe paths. The old `review_required`
verification report can be regenerated by invoking the explicit
verification action after installing this fix; keep all staged files
and previous verification reports for audit. A passing filename check
**does not** mean AccurateRip necessarily passed or authorize archiving.
The existing pending jobs should not be automatically retried or
re-published.

---

## PR #71 — Four-tab daily OSCAR UI

The existing one-page technical UI is reorganized into four keyboard-accessible tabs without deleting its tools or changing the secured API contracts:

1. **Go!**: landing tab, all enabled/detected/calibrated optical drives displayed in independent cards with Go! buttons, active ripping status, latest rip, and selectable persistent Go! job list. Starting a rip still requires the existing authenticated and user-confirmed `/api/go/start` call; disabled/busy/uncalibrated drives cannot start a new rip. `Check next safe step` is still available for any tracked job.
2. **Review**: visible ledger-derived jobs requiring attention with a link to each exact job's Go! review; historical/technical verification, metadata, physical-edition comparisons, classical work review, archive preview/publish, recovery forms and the parallel-drive diagnostics are still available in collapsible **Advanced tools**.
3. **Collection**: the existing catalog, archived track search/index, exports, and read-only Discogs connection. No Discogs modifications.
4. **Settings**: profiles, release-identification policy, language/names, optical drive enable/offset tools, and the existing Save settings action.

Navigation is hash-addressable (`#go`, `#review`, `#collection`, `#settings`) and keyboard-operable. Existing element IDs/event handlers remain intact. These are UI improvements only: **no standalone multi-job scheduler is introduced**, and the server still requires an authenticated Go advancement request for each job. Semi Automatic release and publication review remains mandatory. No changes to archives, original ripping files, or persistent workflow semantics.

Unraid smoke-test: pull the latest main image, confirm individual Go! buttons for all enabled calibrated drives, inspect the three current job IDs under Go!, select a job to advance, visit Review/Advanced, verify Collection and Settings/offset/save. Running jobs continue with their existing IDs and source staging. Test browser screen sizes and keyboard tab navigation.

## PR #70 — Durable Go archive state and opt-in Best Guess publication

Go archive publication is now reserved once in `/config/workflow.sqlite3` before the worker is launched. The persisted workflow phases `ARCHIVE_PUBLISH_RUNNING`, `ARCHIVE_PUBLISHED` and `ARCHIVE_REVIEW_REQUIRED` remain visible across refresh/restart. On a restart, OSCAR **never re-launches** the reserved publisher. Instead it validates the exact archived manifest against the reserved job, metadata copy, release ID, fingerprint and publication ID, and verifies each published FLAC SHA-256 before declaring success. No matching complete archive means manual review; unpublished hidden directories remain for forensic inspection. Archive catalog indexing is recorded independently, with an idempotent single-leaf import if recovery is necessary.

**Best Guess automatic archiving is opt-in and restrictive.** Set both `OSCAR_ENABLE_ARCHIVE_PUBLISH=1` with a safe dedicated `OSCAR_ARCHIVE_ROOT=/archive`, and additionally `OSCAR_ENABLE_BEST_GUESS_AUTO_PUBLISH=1`. This flag is deliberately off by default. Only an exact Disc ID with a **unique** saved candidate (`inferred_disc_id_unique`), previously verified original rip, exact verified tagged staging copy, identical snapshotted release identity, complete reviewed archive proposal, **zero** metadata consistency warnings, no existing destination and no cover art may publish automatically. Several releases, absent or inconsistent metadata, unknown/no archive mount, warnings or previously occupied target require manual review, not automatic override. The inference remains `INFERRED_NOT_PHYSICALLY_VERIFIED` in catalog/archive evidence.

**Semi Automatic:** operator must still accept the MusicBrainz release and explicitly approve the fingerprinted archive plan. **Secure:** cannot publish via inferred Go route. The original rip and tagged staging copy are never removed or modified. No auto-retry is attempted after worker interruption; archive status is reconciled from evidence. Go advancement is still initiated through the authenticated browser/API poll: there is **no persistent independent background scheduler** when OSCAR is idle. PR #70 does not assert complete CD physical pressing verification or silently change MusicBrainz records.

Acceptance criteria: GitHub Python Tests + Docker build and publish green, then real Unraid optical hardware smoke test of the archived state and restart recovery. Avoid testing automatic publication against your final production library until you have reviewed the safe dedicated mount.

## PR #69 — multidisc catalog correction and archive auto-indexing

Catalog import now supports both `/archive/Artist/[catalog] Album (year) [release]/` and `/archive/Artist/[catalog] Album (year) [release]/Disc NN/` for OSCAR-generated, `published_verified` manifests. Disc position `disc_number`/`disc_total` is stored and shown in the local catalog/export. Folder and manifest disc positions must agree. Previously imported multidisc entries created by the old parser are **selectively repaired when re-imported**, only if the old unedited misparse signature is still present. Custom catalog fields, notes, composer/conductor credits and manually renamed records remain untouched. The migration does not move/rename the archive or original staging files.

For newly published archives, the publisher attempts a single-leaf catalog import **after** successful verified atomic publication; success is reported as `catalog.status=indexed`. Failure is nonfatal for the already verified archive and reported `catalog.status=index_required`; manual Collection `Import archives` remains an idempotent fallback. New Go archive publication conveys the ledger's inference status into the published manifest. Existing manifests without release status import as `EDITION_NOT_VERIFIED`, not as physical-pressing proof; previously curated nonlegacy entries preserve their existing status. This is local SQLite only; no Discogs write.

Unraid validation: after deployment, open Collection, click **Import archives** once to repair existing multidisc catalog rows, and check correct Artist/Album/Year/Catalog/Disc values. Do not delete/re-import the underlying FLACs or manually edit database rows. Real hardware acceptance still pending after CI.

## Go Phase 3 — archive review and explicit publication handoff (PR #68, 2026-11-20)

Go jobs at `METADATA_READY` can now request an authenticated read-only archive preview. OSCAR reads back the actual staging-copy FLAC tags and displays track-level classical composer/conductor/Work/Recording-ID evidence, metadata consistency flags, archive CUE proposal, destination and plan fingerprint in the Go UI. No automatic editorial claim is made; the operator must check against the physical CD. An inferred release remains `INFERRED_OPERATOR_ACCEPTED` (Semi Automatic) or `INFERRED_NOT_PHYSICALLY_VERIFIED` (Best Guess).

The publication handoff is **explicitly operator-confirmed for BOTH Semi Automatic and Best Guess at this milestone**. The server derives the release/copy ID exclusively from the persistent Go workflow, re-inspects the tagged FLAC copy, checks the latest publisher plan fingerprint and destination, requires acknowledgement of metadata consistency warnings, and delegates to the existing opt-in, safe, non-destructive archive publisher. Cover art is disabled for Go handoff because inference does not prove that artwork matches the physical edition. Dedicated `OSCAR_ENABLE_ARCHIVE_PUBLISH=1` and `OSCAR_ARCHIVE_ROOT` configuration is still required. Secure cannot use inferred Go publication.

**Deferred:** fully unattended Best Guess publication, post-publication automatic catalog indexing, persistent archive publication state reconciliation, and a completed physical-release evidence approval path for Secure. The existing publisher is asynchronous; a running job's state may need manual archive-manifest inspection after a service restart. Never infer a successful publication from a started thread. The local collection import remains an explicit separate action; it is not proof of physical pressing verification.

Hardware acceptance: PR #67 isolated metadata copy reached `METADATA_READY` in a real Unraid test. The actual classical tag contents and booklet match have **not yet** been independently inspected or verified. Use the Go archive preview to inspect them; do not publish on the basis of technical readiness alone.

## Project baseline — November 2026

**Last reviewed:** 2026-11-19  
**Repository:** https://github.com/sin7ek/OSCAR  
**Purpose:** Open Source CD Archiving & Ripping — archival-grade, verification-first CD digitization for Unraid/Linux, with classical-music metadata and an eventual **insert CD → Go** workflow. Dedicated to Oscar.

> **How to resume after a chat ends:** Read this document first, then `docs/ARCHITECTURE.md`, `README.md`, recent merged PRs and open PRs, and GitHub Actions for the branch under development. Do not infer that a successful CI run establishes real optical hardware functionality.

## Go Phase 2 — verified metadata copy handoff (PR #67, 2026-11-20)

**Implemented in the PR (pending CI / Unraid hardware acceptance):** Go advances an operator-accepted Semi Automatic release or a snapshotted Best Guess inferred release through a verified **metadata preview → durable single-copy reservation → isolated tagged FLAC staging copy → read-back Vorbis tag, SHA-256 and audio-MD5 inspection**. `METADATA_COPY_RUNNING`, `METADATA_READY` and `METADATA_REVIEW_REQUIRED` statuses are journaled; all outputs identify the saved release UUID and copy ID. No automatic tagging for Secure based only on Disc ID.

Reuses `metadata_staging.preview`, `start_copy` and `inspect_copy`, which require exact Disc ID plus medium/track-count match and existing verified FLAC sources; if metadata is incomplete/ambiguous, Go preserves the verified rip and requires review without inventing Work IDs. The existing metadata tagger copies from original FLACs into a new `metadata-copy-<id>`, verifies source SHA-256 and FLAC decoding, never edits original rip/CUE/log and does not publish to `/archive`. The metadata-copy manifest preserves inferred identity provenance (`INFERRED_NOT_PHYSICALLY_VERIFIED` or `INFERRED_OPERATOR_ACCEPTED`); no claim of physical pressing verification.

**Important failure/recovery contract:** Reserve one immutable copy UUID and fingerprint in persistent `workflow.sqlite3` before asynchronous tagging. Repeated polls and browser refreshes do not create duplicate copies. On ambiguous tags, validation failure or interrupted worker after container restart, do **not** automatically rerun against incomplete files: mark `METADATA_REVIEW_REQUIRED`, retain all evidence for operator inspection. Metadata provider errors before reservation can be retried by re-advancing. This is still browser/API-driven workflow progression, not a permanent autonomous server scheduler.

**Still not implemented:** unattended final archive publication, human-approved archive preview/publish for Semi Automatic, fully automatic Best Guess publishing, post-publication catalog indexing, secure physical-edition approval, persistent restart-safe worker continuation or automatic manual recovery of partial metadata copies. Release acceptance does not approve final publication.

## Go Semi Automatic — phase-one release approval (PR #66, 2026-11-19)

- Separate top-level `identification_mode=semi_automatic` is now selectable and persisted, without modifying existing `best_guess` or `secure` settings/jobs.
- After mandatory saved rip verification, Go freezes the server-discovered MusicBrainz candidate UUID list in the workflow database (first snapshot wins). The user can **choose a candidate, explicitly accept inferred identification, or defer/resume**. Only UUIDs in that saved list are accepted; acceptance is authenticated, idempotent for the same UUID, fails closed on a different later choice, and is journaled with a timestamp. Accepted release remains **INFERRED_OPERATOR_ACCEPTED**; never physically verified.
- Go's new terminal `RELEASE_ACCEPTED` phase **does not tag, copy metadata, preview, publish, catalog-index or write to Discogs**. The separate final publication confirmation is a follow-on milestone, not silently implemented. The existing manual archive publisher retains its own independent physical-edition review; approving a Semi Automatic candidate is not equivalent to approving final publication.
- Real Unraid acceptance and Docker deploy still needed; tests use mocked cyanrip and MusicBrainz data.
- The original optical rip, verification evidence and other jobs are unchanged. Existing Secure submode `on_ambiguity` is renamed in the UI to **Review on ambiguity**, avoiding collision with new Semi Automatic terminology.

## Three Go operating modes — design request (2026-11-19)

**Desired policy hierarchy: Best Guess (Full Automatic) → Semi Secure (Semi Automatic) → Secure.** The middle mode must be a *separate top-level* operator policy, not silently identified with the existing Secure review-level names. Semi Automatic automatically rips, verifies and proposes MusicBrainz candidates, but the operator must approve/replace the proposed release before tagged copy creation, then separately approve publication. If the operator accepts an edition without proof, the resulting release identity remains **INFERRED, OPERATOR_ACCEPTED** rather than PHYSICALLY_VERIFIED. The verified original rip remains untouched and can be deferred at either review gate. Best Guess explicitly allows automated use of a credible inferred candidate; Secure demands physical edition corroboration and policy-required review. Audio checks are identical in all modes, and no credible candidate means preserve and defer.

**Implementation update (PR #66):** the third setting, release-review UI, guarded acceptance and persisted accepted state are implemented on the feature branch. **Not implemented:** the automatic tagging/metadata-copy handoff, post-approval preview and separate final publication acceptance; production availability awaits merge, container deployment and real Unraid acceptance. Full specification and Essential Dance Traxx / inferred Ibiza Party case: [docs/AUTOMATION_ROADMAP.md](AUTOMATION_ROADMAP.md).

## Drive read-offset reliability and unsaved-mode UX — follow-up (2026-11-19)

**Status: documented for investigation; not fixed.** Real Unraid observations: AccurateRip database offset lookup produced HTTP **503 Service Unavailable**, with UI detail `Offset database response too large`, on LG GH24NS95 and HP DH16AAL; Optiarc AD-7200S returned an ambiguous/no unambiguous offset suggestion. Disc-based `cyanrip -f` returned HTTP 200 from OSCAR but no unambiguous reported offset for at least one drive. Existing manually entered offsets (+6 LG, +48 Optiarc, +6 HP in the shown UI) are **user settings, not proven database lookup results**; do not overwrite or assume their calibration is independently confirmed.

**Required work:** inspect response format/size and parsing of https://www.accuraterip.com/driveoffsets.htm; handle oversized pages without silently falling back to an unverified offset; consider a bounded, streaming extractor or a cached/maintained authoritative fallback with URL, fetch date, exact model and confidence. Show all conflicting entries for the same drive model (GH24NS95 may have distinct +6/+667 records), require human choice; no majority-guess auto-save. Review `cyanrip -f` output formats per deployed cyanrip version, exit codes, supported flags, known AccurateRip reference disc and error messages. Add sanitized fixture-based tests covering normal, oversized, changed HTML, conflict, no match, ambiguous disc calibration, and no auto-persist. Never loosen the mandatory saved read-offset gate for ripping.

**Related UX:** Best Guess selection in Settings is *not* applied until **Save settings** is clicked. During a real Go test of Anastacia, job `f19f340289b64ba485a05495aaf68f83` correctly snapshotted `secure` because a changed Best Guess dropdown had not been saved; do **not** treat as workflow snapshot defect. Add unsaved-settings indication/dirty-state warning at Go start, show the active *saved* identification policy adjacent to Go button, and optionally show a save-and-start path. Existing jobs must remain on their original snapshotted policy.

## Feature idea / backlog — per-drive progress and ETA in the UI (2026-11-19)

**Original design request.** [#127](https://github.com/sin7ek/OSCAR/pull/127) shipped a track-count-based progress bar and approximate ETA with green PR CI. Tower progress and ETA acceptance remains open.

- Show one progress panel per enabled optical drive in the Go! / Parallel Drives UI, with drive name/stable ID, active job, disc title when verified, current track/total tracks, extraction phase, completion percentage where supported, throughput if available, and verification progress shown as a **separate phase**. The UI should continue to work with multiple simultaneous drives.
- Display an **estimated time remaining (ETA)** only when supported by sufficient actual observations (e.g. processed sectors/tracks and rolling speed). Recalculate as the rip progresses, and label it explicitly as an estimate. Optical drives may slow down or retry damaged tracks, so ETA can jump or become unavailable; use “Calculating…” / “Unknown” rather than inventing precise times.
- Do not treat file count alone as accurate time-weighted rip progress. Ideally derive position from cyanrip's actual bounded progress events or a safe read-only progress stream, not the saved verification-result log alone. Ensure parsing excludes accidental leaks, excessive logs, CPU polling and writes to original audio.
- Use server-side per-job progress snapshots (and optionally an event stream), so browser closure does not interrupt rip/verification; reconnection should show the most recently known progress. If OSCAR restarts mid-rip, mark the extraction **interrupted** and do not display a fake ongoing percentage/ETA.
- Accessibility: text alongside the bar, per-phase state labels, mobile-friendly panel and no rapidly oscillating UI announcements. Never confuse the extraction progress bar with successfully **verified** tracks or final archive publication.
- **Acceptance tests to add later:** two simultaneous drives, a scratched CD with long retries, unequal track lengths, completed extraction awaiting verification, browser close/reopen, and interrupted jobs after container restart.

## Catalog soloist classification correction — PR #65 (2026-11-19)

- **Bug discovered in real Unraid acceptance:** Anastacia — Freak of Nature (2001) erroneously listed session and backing vocal performers such as `Anastacia (vocal)`, `Billy Mann (vocal)` as **Soloists** in the album Collection Library. The original PR #61 heuristic interpreted `(vocal)`, `(violin)`, `(soprano)` etc. as proof of soloist, which is factually wrong. Actual `PERFORMER` metadata is retained in the archive and `performers` column; nothing is dropped from track-level credits.
- New read-only archive import classifies the album as classical **only** if reviewed archive `profile=classical` or archived `GENRE=Classical` / `Classical Music` explicitly states it. It does **not** guess genre from an artist, singer name or instrument. For classical albums, `soloists` is populated only from `PERFORMER` role annotations that explicitly contain `solo` or `soloist`. Generic soprano/piano/violin credits remain searchable under Performers, not fabricated as soloists.
- Re-running **Import published archive records** corrects older, automatically generated soloist strings (including Anastacia's) only when they match the exact obsolete heuristic reconstructed from the archived FLAC tags; local/manual different values are preserved. The original FLAC archive, CUE, manifest, SHA-256 and other recorded credits are untouched. Explicit (solo voice) credits on pop are preserved as performers but not shown as *classical album soloists*. The separate track credits index already required explicit soloist indications.
- Future consideration: richer verified MusicBrainz role identifiers and configurable display presets for pop/classical, without deleting composer/producer/session credits or conflating a genre tag with unverified release identity.

## Go controller — first executable safe phase, PR #64 (2026-11-19)

- A new **Go! — rip to verified staging** UI and authenticated `POST /api/go/start` reuse the existing cyanrip rip pipeline, **snapshot the saved identification policy into persistent SQLite BEFORE the ripping worker starts**, and automatically initiate the existing audio verification after a successful rip. If durable registration fails, the rip does not start. Original FLACs/CUE/logs are preserved; no automatic delete.
- `POST /api/go/jobs/{job_id}/advance` advances only safe stages: observe rip state, trigger verification when not yet started, read saved verified report, and discover MusicBrainz candidates using **the TOC stored at extraction time**, not the current drive. A provider or verification failure stops before tagging.
- **Best Guess:** deterministic candidate *suggestion* from linked Disc ID releases using a metadata-completeness rank (NOT physical edition proof), persisted with `release_evidence=inferred_disc_id_unique|inferred_disc_id_ranked`. Does not tag/archive or claim a physically verified release. **Secure:** returns candidate list requiring physical catalog/barcode review; never persists inferred release or silently approves edition.
- Existing `/api/rip/start` behavior is retained. The Go button tracks its new job in the UI and polls the server; extraction and verification are server-side tasks. On restart during an extraction, its staging evidence is retained and phase becomes `RIP_INTERRUPTED`—never silently rerips. Restart of an interrupted cyanrip, permanent background scheduler, fully automated tagging/archive and post-publication catalog insert remain **unimplemented**.
- Existing verification uses saved cyanrip AccurateRip v1/v2 evidence, FLAC decode, SHA-256/CUE; independent CTDB/AccurateRip is not newly implemented. GitHub checks must pass and physical Unraid acceptance must be recorded separately.
- Next milestone is a **server-side policy-enforced exact-release resolver and safe tagged-copy/archive handoff**, including recovery, concurrency, user-reviewed Secure evidence and explicit opt-in Best Guess publication. No shortcut around Physical Edition Identification Gate.

## Persistent workflow ledger — PR #63 (2026-11-19)

- Adds SQLite `/config/workflow.sqlite3` (configurable `OSCAR_WORKFLOW_DB`) storing an existing staging job's saved status, persisted event log, and immutable snapshot of `identification_mode` and `secure_review_level` **when that job is manually registered**.
- UI section **Persistent workflow ledger** and authenticated endpoints: register an existing rip, refresh status from staging verification, defer/resume physical edition review, list tracked jobs. Entries persist across container restart and operations are idempotent. Never tag, publish, delete, create MusicBrainz edits, or assume physical edition approval.
- This is the **first persistence layer**, not a real background orchestration engine. Registration is currently an explicit user action and the snapshot occurs then (not automatically at physical disc insertion); no automatic CD detection, publishing, resume of an interrupted extraction, or pipeline chaining yet. Future Go controller will attach ledger records at rip start and enforce a complete evidence-scored transition policy.
- CI and real Unraid workflow registration/restart acceptance are separate; preserve all existing staging files and archives. Next engineering feature: persistent job registration at rip start + evidence resolver.

## Indexed per-track classical credits and safe label backfill — PR #62 (2026-11-19)

- New `archive_tracks`, `track_credits`, and `track_works` indexed tables in existing OSCAR local SQLite catalog, with **explicit per-track FLAC Vorbis comment provenance**, source file/track, recording ID, release track ID, Work IDs/names, conductor, composer, orchestra, performers and explicitly identified soloists. The index only imports albums already in the local catalog with published OSCAR manifests; every indexed archived FLAC must match its recorded SHA-256 first. No archive file is modified.
- The UI provides **Index verified published tracks** and per-track search for artist, performer, composer, conductor, explicit soloist, recording and Work. It **does not** infer that soprano/piano/violin roles are soloists. A matching Work title/ID pair is recorded only when the same-length aligned tags support it; mismatched title and ID arrays are **not** joined.
- `Fill missing labels from exact MusicBrainz release` is an explicit optional read-only lookup. The local missing label is updated only if the MusicBrainz release UUID equals the stored exact release and its label-info includes the **same physical printed catalog number**. The local value records provenance `musicbrainz_exact_release_catalog_match`; never overwrite a known label or modify historical archive evidence. In particular, the earlier Anastacia archive cannot safely infer a label from an unrelated pressing.
- Limitations: text-level role tags are not a substitute for normalized MusicBrainz artist/role IDs; explicit Work ID alignment remains the only permitted relation; no remote revision of archive tags, no Discogs writes, no per-owned-copy catalog, no independent AR/CTDB. Operator must still explicitly import archived albums, index tracks, and initiate optional label backfill. CI results and Unraid acceptance tracked separately.
- **Roadmap priority has shifted back to automation after this metadata foundation**: [AUTOMATION_ROADMAP.md](AUTOMATION_ROADMAP.md) specifies persistent per-disc state machine, evidence-scored resolver, and crash-safe CD inserted → Go controller as next milestones. Best Guess/Secure settings alone are not the workflow engine.

## Collection spreadsheet interoperability and classical search — PR #61 (2026-11-19)

- Adds standards-based **XLSX** export in addition to ODS/CSV; XLSX uses inline text, an AutoFilter row and frozen header, and never creates formulas or macros. Intended for Nextcloud + Collabora and ONLYOFFICE. No Microsoft software or proprietary binary writer is required.
- Extends local collection SQLite schema with **label, composer, conductor, orchestra, soloists, performers, works**. Migration adds the fields to existing `/config/catalog.sqlite3` without removing prior local data. The **explicit** Import published archive records action reads only the archived FLAC Vorbis Comments and sourced `label_info` in *new* OSCAR publication manifests, and fills missing fields without overwriting existing user data.
- New archive manifests preserve `label_info` from their reviewed, selected MusicBrainz release. Older releases such as Anastacia were published without `label_info`; missing label stays blank, **do not invent Epic or others from artist/title**. This change does not retroactively edit existing archives or query MusicBrainz to enrich them.
- SOLOISTS field is derived only from explicit recognized performer role annotations; **not** an authoritative work/soloist relationship database. Future next step: durable *per-track* MusicBrainz recording/work/contributor relations, role/instrument IDs, multiple discs and indexed multi-valued relationships; display unknown source data as empty, not fabricated. Search/sort currently works on album-wide aggregated values.
- UI supports sorting by label, composer, conductor, orchestra and soloists; search across all those fields. Existing verified audio integrity and physical-release confirmation policies unchanged. CI not a substitute for Unraid, and XLSX needs real Nextcloud editors acceptance.
- Official compatibility documentation: https://nextcloud.com/collabora/ and https://api.onlyoffice.com/docs/docs-api/get-started/ready-to-use-connectors/nextcloud-integration .

## Local collection catalog and read-only Discogs PAK integration — PR #60 (2026-11-19)

- New local SQLite database of **OSCAR published archive items** (not yet a complete physical ownership inventory), in persistent `/config/catalog.sqlite3` by default; explicit import of `published_verified` archive manifests, skip previously imported paths, preserve local records, never modify `/archive`. Searchable/sortable web inventory and CSV/ODS export.
- The `OSCAR_DISCOGS_PAK` Portainer environment variable is a **Discogs personal access token** and can be sent as `Authorization: Discogs token=<value>` to `https://api.discogs.com/oauth/identity`. A read-only button requests identity and the authenticated account's collection-folder list. Token stays in process memory, never returned, exported, logged or committed. Discogs collection writes are **NOT** implemented. Consumer Key/Secret not required for PAK authentication.
- Fixed `RIPPED_WITH=Ripped with OSCAR - Preserve Every Note.` and `RIPPER_URL=https://github.com/sin7ek/OSCAR` Vorbis Comments added in newly generated original-tagged FLAC copies, preserved in Classical v2 copies and byte-for-byte published archive copies. Original ripped FLAC files and old archives do not change. The tag describes the ripper, not independently verified audio.
- This PR is **not** an implementation of Discogs release candidate search, collection write/condition management or two-copy physical ownership records. These remain follow-up milestones. User has not yet carried out actual Unraid acceptance for this feature; GitHub CI must be checked.
- See [DISCOGS_COLLECTION_CATALOG.md](DISCOGS_COLLECTION_CATALOG.md) for scope, privacy rules, milestones and acceptance criteria.

## Discogs and OSCAR-owned collection catalog — design proposal (2026-11-19)

**Design specification:** [DISCOGS_COLLECTION_CATALOG.md](DISCOGS_COLLECTION_CATALOG.md). User requested: Discogs metadata as secondary physical-edition evidence; optional post-archive Discogs collection entry with per-copy Media Condition, Sleeve Condition, Notes and Folder; OSCAR-managed sortable collection database exportable preferably to **ODS**, with CSV and optional XLSX. This is **not yet implemented**: no API auth, writes, persistent local catalog or spreadsheet exporter exists in OSCAR today.

**Architecture decisions:** MusicBrainz remains authoritative for recording/work/classical relationships; Discogs supplements physical release evidence. Separate each physical copy from an album release, rip job, archived item and Discogs instance ID; use idempotent opt-in collection sync. Store OSCAR-owned facts in local SQLite; respect Discogs' distinction between CC0 release metadata and restricted user/marketplace/image data, attribution, caching/export and user privacy constraints. Archive evidence remains immutable and independent of the external sync.

## Historical status after PR #52 (2026-11-19)

**Progress dashboard:** [PROGRESS.md](PROGRESS.md) records eight qualitative completion estimates, a Markdown table and a bar chart. Update it at each meaningful feature PR alongside this handoff; no silent percentage increases. Progress figures are editorial, not objective CI/engineering metrics.

> **This section supersedes outdated historical statements below** that say archive publishing is unimplemented, hardware acceptance is pending, or no audit exists. Earlier incident descriptions remain as a historical record, not current instructions.

### Configurable release identification modes — PR #58, 2026-11-19

- User design decision: **Best Guess Mode = intended Full Automatic** and **Secure Mode = adjustable from Semi Automatic to Full Manual**. These are *two identification policies*, not different audio verification rigor. Default mode is Secure.
- Implemented in this PR: persistent, validated `/config/settings.json` preferences `identification_mode: secure | best_guess` and `secure_review_level: on_ambiguity | before_archive | every_step`; settings UI explains modes, shows three Secure review intensities, and correctly hides the inactive Secure options in Best Guess view. Old settings files load as Secure / on_ambiguity. No change to existing drive settings or filenames.
- Intended future **Best Guess / Full Automatic**: select highest-quality MusicBrainz candidate using Disc ID, TOC, track count and available source evidence; emit explicit `INFERRED` provenance and allow safe unattended transitions only after strict audio checks and explicit opt-in. No candidate/conflicting integrity => preserve for deferred review; NEVER forge or misrepresent physical edition confidence.
- Intended future **Secure / Semi Automatic (`on_ambiguity`)**: proceed without interruptions when identity evidence is strong; pause on ambiguous/conflicting physical edition. **Secure / Review before archive (`before_archive`)**: require final edition and publication preview review. **Secure / Full Manual (`every_step`)**: user approves each critical transition, but same preservation rules.
- **Critical implementation boundary:** this PR saves settings and exposes UI only. **There is NO automated rip→tag→archive orchestration engine here, and no new bypass of the existing exact-medium requirements, manual copy confirmation or publishing safeguards.** Future PR must implement a tested, server-side evidence/approval policy, provenance fields, persistent per-job mode snapshot, correction/re-tag from original staging without rerip, and end-to-end workflow. Avoid interpreting the 'Best Guess' setting as immediately enabling full automation.
- Test scope: default/legacy migration, all mode and Secure-level round trips, invalid values, rendered UI and setting validation. CI and Unraid acceptance must be recorded separately.

### Risk-based physical edition discovery — 2026-11-19 (new feature; CI/hardware status below)

- Inserted-disc MusicBrainz candidate lookup now classifies **one candidate**, **multiple candidates**, **no candidate**, **catalog conflict**, **one catalog candidate** and **multiple catalog matches**. It does **not** equate unique Disc ID match with proof of the physical edition: an unlinked edition (as in Händel E 8512) might be missing.
- With one Disc ID candidate and no conflicting evidence, OSCAR automatically opens its **read-only medium/tracklist inspection** without asking a catalog number up front. With multiple Disc ID candidates, it asks for the **printed catalog number** to narrow them. When that catalog matches none, it offers the existing independent catalog-number search. Where catalog numbers conflict, it disables mismatching candidate inspections, not just display a warning.
- All returned candidates remain `physical_edition_approved=false`: a catalog match is only evidence for selection. **No automatic final tagging, physical-edition approval, MusicBrainz editing, Disc ID linking, or archive publishing is enabled by this feature.**
- **Design decision:** eventual unattended tagging/publishing is appropriate when sufficient *independent physical-release evidence* is available and persisted, ambiguity checks are clean, and the user has explicitly configured automation policy. A single Disc ID candidate **alone** is insufficient to establish that state. The persistent catalog/barcode evidence store and enforcement at the metadata-copy/publisher API boundaries are not implemented yet; do not represent this PR as the complete automatic physical edition gate.
- Test cases cover one candidate, multiple candidates, matching and conflicting catalogs, no candidates, invalid catalogs, UI integration and preservation of raw search results. **GitHub CI is not a substitute for real Unraid acceptance.**

### Händel physical-edition correction — 2026-11-19 (publication blocked)

- The 28-track verified rip job `f41806152a614b1a9006b10456b9bbd4` and existing tagged copy `3ac951bdd5b74ad8b484aaea955eb757` were reviewed as MusicBrainz release `4a8cbc25-21a0-4a24-8bb8-2f388164d544` (Astrée Auvidis **ES 99220**, 1999), with classical publication preview target `[ES 99220] Water Music Music for the Royal Fireworks (1999) [4a8cbc25]`. **DO NOT PUBLISH this proposal:** user found that the actual physical booklet corresponds to **E 8512**, not ES 99220. Original CD/source files stay untouched; no final Händel archive has been confirmed.
- MusicBrainz already lists a distinct physical CD release, **Astrée Auvidis E 8512 (France 1993, 28 tracks, barcode listed as 3298490085127)**: `09fe4a40-7d2b-400e-b3de-b148f55fbcad`. Source: https://musicbrainz.org/artist/e3b43b6a-14b0-4b2a-abd4-a41307cf10a0/releases ; user's Discogs pointer: https://www.discogs.com/release/7720704-Haendel-Le-Concert-Des-Nations-Jordi-Savall-Water-Music-Music-For-The-Royal-Fireworks . Verify printed barcode and edition-specific track/version details against the actual packaging, not just online data.
- User supplied the full proposed 28-track CUE: `REM MUSICBRAINZ_ID "ROkQlooU5tDdgVZOkfXXTy.S4oU-"` is a **MusicBrainz disc ID, not a release UUID**; original `REM DISCID "AB114D1C"`, track 1 `PREGAP 00:00:32`, and 28 `INDEX 01 00:00:00` entries are represented in the preview. `MCN "0000000000000"` is not proof of a real UPC/EAN and must not override physical barcode evidence. Never create/synthesize missing indices or assert confirmed HTOA.
- Five classical review observations remain `same_work_different_titles`: tracks 2/3/6/7, 4/5, 8/9, 18/21, 23/24. User's booklet mentions *Mouvement sans titre dans la partition originale* relating to movement descriptions, but this alone does not validate or invalidate track 18/21 shared Work. **Treat as unresolved; do not auto-edit MusicBrainz Work/Recording identities.**
- **Next:** Select exact E 8512 MB release (confirm medium, catalog, barcode, tracklist, Disc ID applicability). Generate a **new** reviewed original-tagged or Classical-v2 metadata copy as appropriate from the same *verified original rip*, review its CUE and Work relationships, then preview the new E 8512 archive. Never recycle the ES 99220 tagged copy or approve the wrong physical edition. Do not mistake a Disc ID match for proof of edition.

### Confirmed on real Unraid (user-reported, independently inspected where indicated)

- **PR #52 archive audit — first real Unraid acceptance (2026-11-19):** User ran `docker exec oscar python -m oscar.archive_audit /archive`. Actual result: `OSCAR archive audit: PASS_WITH_WARNINGS | 1 releases | 12 FLACs`; album `Anastacia/[504757 2] Freak of Nature (2001) [4b370e6c]` classified `PHYSICAL_CD_RIP`, status `PASS_WITH_WARNINGS`. Sole warning: `EVIDENCE_NOT_EMBEDDED` because this album was published before PR #51. Auditor correctly states `AccurateRip/CTDB: not independently checked by this auditor.` No audio errors reported. This verifies the CLI runs on actual Unraid with existing archive; it is not a test of future PR #51 embedded evidence, multi-album handling or independent CTDB verification.


- **First successful published archive: Anastacia — Freak of Nature (2001), catalog 504757 2.** Verified original staging rip job `0c81d7d445ce4e29aa95da10c866bcf9`, selected physical MusicBrainz release `4b370e6c-e6d2-36a5-8c47-5337a2d77d69`, 12 FLACs. Publication target: `/archive/Anastacia/[504757 2] Freak of Nature (2001) [4b370e6c]`. OSCAR reported `published_verified`, and the user independently listed all 12 FLACs plus `album.cue`, `SOURCES.txt` and `manifest.json` in the final directory. The resulting manifest SHA-256 `cc1f92ea7b6317d32e5e3fc11f74122d0760b82aa88ad733c5a5f2c38c3f5851` matches OSCAR's publication response.
- **CUE preservation checked:** compared cyanrip's original `Unknown disc (5099).cue` with OSCAR's proposed `album.cue`. All 12 track indices (INDEX 01), all ISRCs, MCN and disc IDs are retained; neither source nor adapted CUE contains INDEX 00/PREGAP. This does *not* prove hardware-level absence of gaps or HTOA.
- **Unraid FUSE fix accepted on actual hardware:** PR [#50](https://github.com/sin7ek/OSCAR/pull/50) fixed `renameat2(RENAME_NOREPLACE)` fallback for shfs/FUSE and separately reports unsupported parent directory fsync. Original rip and tagged staging remain preserved. Old failed publication temporary folder `/archive/Anastacia/.oscar-unpublished-e18c51ec667e42da99dcb598a745e2a8` was identified; **removal/quarantine was proposed but not confirmed**. Never assume it has been deleted.
- Previously confirmed on hardware: 3 simultaneous optical drives with 58/58 subsequently verified staging tracks, original MusicBrainz tagging, Classical v2 review, and physical-edition comparison. See earlier sections for IDs and caveats.

### Changes merged to main and validation scope

| PR | Capability | GitHub checks | Actual Unraid acceptance |
|---|---|---|---|
| [#50](https://github.com/sin7ek/OSCAR/pull/50) | Unraid-safe final archive publication + conditional confirmation UI | Passed | **Confirmed:** Anastacia published, final files and manifest independently checked |
| [#51](https://github.com/sin7ek/OSCAR/pull/51) | Copy original cyanrip CUE and existing logs to `ExtractionEvidence/` at publication, hash in manifest, reject changed evidence | Tests + Docker build passed | **Not yet tested on Unraid**; applies to subsequent publications, does not retroactively change the Anastacia archive |
| [#52](https://github.com/sin7ek/OSCAR/pull/52) | Standalone read-only provenance-aware archive integrity CLI (`python -m oscar.archive_audit /archive [--json]`) | Tests + Docker build passed | **Confirmed on Unraid**: Anastacia 1 album, 12 FLACs, PASS_WITH_WARNINGS, expected EVIDENCE_NOT_EMBEDDED; no UI/scheduler yet |

PR #51 merged at `b307b8248f0c64997ffd79973bfab44a88704003`; PR #52 merged at `b1ad817db3b68d76f07e3b9401d8bb8e54873238`.

### Roadmap vs present state (qualitative, not numeric completion claims)

| Architecture stage | Present state | Outstanding |
|---|---|---|
| DISC_DETECTED / RIPPING | Physical multi-drive cyanrip runs confirmed | Automatic insertion/drive choice, interruption/restart robustness, full TOC/gap/HTOA characterization |
| VERIFYING | Post-rip FLAC decode/hash/CUE and cyanrip-reported AccurateRip v1/v2 evidence confirmed | **Independent AccurateRip/CTDB** verification; separate evidence/confidence interpretation, no match != mismatch |
| IDENTIFYING | MB Disc ID, physical edition review, metadata preview and tagged-copy workflow | Automated safe release discovery, missing/wrong edition workflow integration |
| AWAITING_REVIEW | Working review flows for pop/classical and deferred wrong/missing releases | Reduce manual steps without ever approving ambiguous information automatically |
| READY_TO_ARCHIVE / ARCHIVED | Reviewed copy-only publisher, Unraid success with Anastacia | Real hardware acceptance of source-evidence embedding (PR #51); standalone CLI acceptance (PR #52); longitudinal audit/reporting |
| CLEANUP_ELIGIBLE | **Not implemented** | Safe, explicit, delayed cleanup only after verified archival integrity |
| Persisted workflow / insert CD → Go | Some persistence and queues exist | End-to-end job orchestration, crash recovery, unattended operation, GUI integration |

### Next priorities

1. **PR #52 basic hardware acceptance completed:** the existing Anastacia archive passed with the expected missing-embedded-evidence warning. Next test a future publication containing PR #51 evidence and rerun the same read-only audit; review all genuine errors before acting. Do not alter old archives automatically.
2. **Real publish test for PR #51** using a new, reviewed, verified release; inspect `ExtractionEvidence/`, manifest entries and staged-original byte preservation. No need to rerip or republish Anastacia solely to test this.
3. **Make the audit visible in the UI** with clearly distinct technical integrity, provenance/documentation, AccurateRip and CTDB statuses. No invented independent verification or destructive repair.
4. **Investigate independent CTDB** on Linux, with truthful confidence and provenance (especially 1/1 matches).
5. **Persist orchestrated state and support controlled unattended progression**, while stopping for wrong/ambiguous physical editions. Keep release-review backlog available.
6. **Maintain this workdocument in every major PR**: record implemented capability, CI result, actual on-hardware acceptance (or not), limitations, next step; update active handoff *before* merge when practical. Historical notes may remain but must be clearly superseded.

### Maintenance agreement

`docs/PROJECT_STATUS.md` is the **living OSCAR workdocument and handoff**, not merely a post-hoc summary. Every meaningful implementation PR must update it together with code/tests. The README and older milestone documents must not be interpreted as fresher evidence when contradicted by this verified current-state section. Keep the explicit difference between *merged*, *CI tested*, *Unraid tested* and *fully automatic*.

---

## Earlier developer notes (November 2026)

**Canonical project state:** Earlier notes below record the history of prototype development; statements such as *feature in progress*, *hardware test pending* or *next* from early iterations are **historical, not the current state**. Use this section plus GitHub merged PRs/CI as the authoritative starting point for a new chat. The user actively tests OSCAR on Unraid/Portainer; don't claim deployment or hardware success merely because CI passed.

### What works on real Unraid hardware

1. Three optical drives have ripped concurrently and **all 58 tracks were subsequently verified** by OSCAR's staging verifier (FLAC decoding, SHA-256 hashes, CUE references, cyanrip AccurateRip logs). Original rips, source logs and CUEs are immutable; there is no archive publishing. AccurateRip evidence is *cyanrip-reported*, not independent OSCAR AR/CTDB lookup.
2. **Boulez Conducts Stravinsky**, Deutsche Grammophon 6CD box, disc 6 of 6, catalog `6CD 477 8730 GB6`, 2010-01-04; MusicBrainz release `423f636d-742d-47b0-9ba2-51515a6fdfd2`; original job `699e010ffdda46ea80cc67b07b72a28e`; original metadata copy `331f89f080d747a381dae81c8d01f799`; 32/32 Classical v2 tags inspected `tags_match_preview` with optional physical sections left blank (PR #36). Archive Review shows the sourced performers (Pierre Boulez, Ensemble intercontemporain, actual vocalists) instead of Igor Stravinsky incorrectly being listed as performer; release-specific cover candidate found (minor sticker difference on public image vs user's physical box). Exactly **one review observation**: track 24 *Tilim-bom*, MB recording `608f8f1f-3d08-48c5-80b5-ffb0a3a4fbdb`, has no explicit Work relation; **never infer** it equals track 23's Work. CUE proposals still reference original `Unknown track.flac` names or future proposed names. PR #37 fixes performer attribution and missing-work observation.
3. **Anastacia — Freak of Nature**, original Epic single CD, printed catalog `504757 2`, barcode `5099750475720`, release `4b370e6c-e6d2-36a5-8c47-5337a2d77d69`, 2001-11-26, 12 tracks; verified original job `0c81d7d445ce4e29aa95da10c866bcf9`. Disc ID `fHRjyL_F16yLkOO1ddr2Hedl0A0-` matches multiple editions, so we require the exact physical release. User tested Physical Release Comparison (PR #38): catalog, barcode, Disc ID on medium and track count **all matched**. They reviewed an existing **original MusicBrainz tagged copy** with Archive Review profile `auto`; it selected `standard`, **0 review observations**, CUE PERFORMER = **Anastacia** for all 12 tracks, the original/reprise *Overdue Goodbye* pair is recognized as benign same-Work/different-Recording. Artwork candidate found. This is a **successful real hardware acceptance of PR #41**. Do **not** run this pop album through Classical v2; don't rerip or retag for read-only Archive Review.
4. **Various — Essential Dance Traxx**, Citycat Club, Europe 1997, printed catalog `CCC 97001`, 14 tracks; verified rip job `95dbf0da233d4a3887800a517a149b3c`, Disc ID `UNzDV9I7c4DxDxpasZu014z4sQs-`; 14/14 FLAC verified with cyanrip AccurateRip v2-only evidence (confidence 4). Its Disc ID points to an **unrelated 14-track release (Ibiza Party)**, so DO NOT select it. A proper MusicBrainz physical release ID for Citycat has **not** yet been verified. The next feature is independent release discovery by printed catalog `CCC 97001` and title `Essential Dance Traxx`. If not present, prepare a properly evidenced MusicBrainz release edit, never fabricate recording/work IDs or incorrectly tag against the unrelated release.

### Citycat missing-release checkpoint — 2026-11-19, after PR #42 deployment

- User executed **Search by catalog number** for `CCC 97001` on Unraid: **0 MusicBrainz candidates**. Screenshot shows album-title input populated as `Essential Dance Traxx`, but it is **not established that the separate Search by title button was clicked**. **First next action:** run title search once, not another rip.
- External 2dehands reseller listing explicitly matches **Citycat Club – CCC 97001**, 1997 European 14-track compilation and has a complete track/version list. Preserve these as **secondary hints**, not authoritative tags. See [CITYCAT_RELEASE_RECOVERY.md](CITYCAT_RELEASE_RECOVERY.md) for all 14 candidate tracks, references, unknown barcode/credits, disc/TOC evidence and MusicBrainz editor steps.
- If title search finds no correct release, user should add a **new Various Artists physical release** in MusicBrainz using actual packaging and original Disc ID/TOC, with all 14 track artists and versions individually reviewed. Use MusicBrainz's Add release / Add from CD TOC flow where available; then independently confirm this Disc ID is linked to its new 14-track medium. **Do not** select the unrelated Ibiza Party release and do not automatically create recordings/work relationships.
- Once release is published and its Disc ID attached, perform original MusicBrainz tagged-copy and **standard** Archive Review without reripping; final archive promotion remains a separate unimplemented feature (#39).
- Longer term: build a missing-release evidence/submit helper and optional Discogs/GnuDB fallbacks under #40; preserve human review until proof is strong.

### User decision — handling missing or wrong CDs (2026-11-19)

- The user explicitly **does not want to add Citycat Club to MusicBrainz now**; creating a 14-track compilation release and verifying each version is too much work at the moment. This is a deliberate deferral, **not** a request to re-prompt immediately. No MusicBrainz release was added. Preserve the successfully verified Citycat source job `95dbf0da233d4a3887800a517a149b3c` and do not select unrelated `Ibiza Party`.
- OSCAR now has a guided **"CD not found, wrong edition or incomplete metadata?"** panel with four reason codes: `missing_release`, `wrong_edition`, `ambiguous_edition`, `incomplete_metadata`. It explains evidence-based recovery, not inventing Recording/Work/ISRC, and how to add/fix the actual physical release using MusicBrainz *when convenient*.
- Users can choose **Save for later** on a **verified existing rip job**. This writes only an indexed task to persistent `/config/release_review.sqlite3` keyed by job ID, including optional physical title/catalog number and notes; `View pending CD reviews` lists tasks and can mark them resolved. It neither uploads to MusicBrainz nor modifies FLACs/CUE/audio, tags, or the rip.
- This provides a **review backlog**, not a background automatic cross-provider search, a new MusicBrainz edit, or automatic archive publication. Full automation and fallback provider adapters remain tracked under #40. On Unraid, ensure the normal `/config` volume remains persistent during Docker redeploy.
- **Next action for user after deploying this PR:** optionally enter their already verified Citycat job ID and select `My physical CD is missing from MusicBrainz`, title `Essential Dance Traxx`, catalog `CCC 97001`, then **Save for later**. No need to do the manual MusicBrainz entry today. Once saved, move on to the next CD or toward #39/#40 development; no blocked ripping.

### First Anastacia archive publish — FUSE rename compatibility failure (2026-11-19)

- User successfully generated the first **read-only** Anastacia archive preview: destination `Anastacia/[504757 2] Freak of Nature (2001) [4b370e6c]`, 12 final named FLACs, disc 1/1, standard CUE, **0 metadata observations**. Correct physical release had previously matched printed catalog, barcode, 12-track medium and Disc ID.
- On explicit Publish, real Unraid hardware reported **`PublishError: Atomic publication failed: Invalid argument`**. This is at the Linux `renameat2(RENAME_NOREPLACE)` final directory promotion step; on Unraid's `/mnt/user` user-share FUSE/shfs volume, the special no-replace rename flag is likely unsupported. **Do not claim the archive is published.** Original rip and tagged staging copy remain preserved, and the hidden `.oscar-unpublished-<id>` temporary folder may contain fully copied/verified files. **Do not delete it automatically.**
- Implemented fallback in `_rename_noreplace`: on **only** EINVAL/EOPNOTSUPP/ENOSYS capability errors, under OSCAR's existing exclusive cross-process archive-root lock, re-check target nonexistence and use ordinary same-filesystem directory rename. This remains atomic as a rename but **cannot provide a kernel-level no-replace guarantee against unrelated non-cooperating writers**. For first hardware test, keep archive root a dedicated directory writable only by OSCAR, and do not expose it to other writers. Other errno failures are still fatal. Tests cover unsupported-flag fallback, existing target refusal and content preservation.
- Unraid FUSE also may reject parent directory `fsync` **after** a successful rename. This is now returned as `published_verified` with a `directory_sync: unavailable: ...` durability warning, not a false `failed` response about an archive that has already become visible. The publisher still verifies file-level contents before rename. The hardware result remains unconfirmed until the next test.
- Fixed archive GUI conditional boxes: CSS `label{display:block}` previously overrode the standard `hidden` attribute for metadata-exception and cover-approval labels; explicit `[hidden]{display:none!important}` now hides the irrelevant confirmations. Anastacia should only require the physical-release and CUE review checkboxes.
- **Next real test after new Docker deployment:** leave previous hidden temporary folder alone for now, use the same existing verified Anastacia rip and tagged copy, review preview again, then explicitly publish to the still-empty final destination. If failure remains, obtain exact error and inspect `/archive` listing. No source ripping or metadata work should be repeated.

### Archive preview root-cause fixed in browser template (2026-11-19)

- User confirmed the actual completed Anastacia tagged copy `0716b4d32e0a450d8b9f16528de216e9` exists under the verified job; its `audio/`, `metadata-manifest.json`, and `metadata-preview.json` are present. Container runs as UID/GID 999, and archive mount `/archive` was initially `NOT WRITABLE` (owned by nobody). After changing ownership of **only the test archive folder** to oscar:oscar, `test -w /archive` returned **WRITABLE**.
- The Preview button nevertheless still had no response. User opened Chrome DevTools and found **`Uncaught SyntaxError: Invalid or unexpected token (index):1144`**. **Root cause found:** `src/oscar/web.py` defines browser JavaScript in a Python triple-quoted string, with `join('\\n')` incorrectly represented in the **rendered** JavaScript as a literal newline inside a single-quoted JS string. This prevents the entire inline script from parsing and disables ALL inline button handlers, not just archive preview. Additional Python template escape loss affected classical-section numeric regular expressions (`\\d`/`\\s`).
- Current fix: double-escape JS backslashes in the Python source for the archive preview newline and the section input regex, with a regression test against the **rendered HTML** plus Node syntax check when Node is available. Prior PR #48's improved preview error messages were valid but could not display while browser script parsing failed.
- **Next live hardware test after deploying fixed image:** browser Ctrl+F5, click read-only `Preview proposed archive` for Anastacia. Confirm the output shows 12 tracks, destination and CUE. **DO NOT publish** before reviewing this output. Do not rerip or retag; source copies still intact.
- Unrelated Chrome console messages about favicon 404 or extension messaging are not the cause of the fatal SyntaxError.

### Archive publication UI: first on-hardware preview attempt (2026-11-19)

- User deployed #45 and can see **Publish verified FLAC archive (explicit opt-in)** in the OSCAR web UI. Entered Anastacia original rip job `0c81d7d445ce4e29aa95da10c866bcf9` and completed original MusicBrainz tagged-copy ID **`0716b4d32e0a450d8b9f16528de216e9`**, copy type `original_tags`, profile `auto`, artwork unchecked.
- On clicking **Preview proposed archive (read-only)** user reports **no visible reaction**; **no preview response, error text, request log or server error has yet been established**. Do not infer the backend returned success or failure, and **do not claim any archive publication has taken place**.
- UI defect: `requestAuthHeaders()` can return `null` when a browser rip-token prompt is dismissed or blocked; previous handler returned silently without writing any status. A follow-up UI fix adds an immediate progress label, explicit token-cancelled/blocked status, and HTTP/invalid-response feedback. This improves diagnostics but **the actual root cause is not yet confirmed**.
- After deploying the updated image, click preview once and read the status below the button. If still blank, check Chromium DevTools Console/Network for a script exception/blocked dialog and OSCAR Portainer logs. If token is required, enter the configured OSCAR rip token; if trusted local UI is enabled, the prompt is intentionally skipped.
- The intended next hardware milestone is a **read-only preview** (12 filenames + CUE + destination) before any publishing confirmation, not a new rip or changes to source. `OSCAR_ARCHIVE_ROOT` must reference the intentionally mounted dedicated empty archive-test directory. The user asked about `/mnt/user/ai-workspace/oscar-archive-test`: use with caution when staging and target share an ancestor on the host; never map production music library writable for first acceptance.

### Safe final archive publishing — merged PR #45, hardware acceptance pending (2026-11-19)

- **Merged in PR #45; main-branch tests and Docker publication successful (2026-11-19):** opt-in copy-only archive publisher via `src/oscar/archive_publish.py`, a gated POST preview/start/status API and a separate GUI panel. It requires `OSCAR_ENABLE_ARCHIVE_PUBLISH=1` plus a dedicated, **distinct** writable volume at `OSCAR_ARCHIVE_ROOT`. Without both, publishing stays disabled.
- Publication **requires** an existing `checks_passed` rip verification and a completed tagged copy (`original_tags` or `classical_v2`), the selected exact MusicBrainz physical release and explicit human confirmations for physical edition and CUE/file names. An unresolved metadata observation (such as Boulez track 24's missing Work) requires a separate acknowledgement; it is not auto-corrected.
- Produces a **new separate directory** with readable `NN - Track Title.flac` filenames, source-index-preserving `album.cue`, `manifest.json`, `SOURCES.txt`, optional **separately approved** `cover.jpg`/`cover.png`. Each source FLAC SHA-256 and STREAMINFO audio MD5 must match the saved manifest; every copied FLAC is decoded with `flac -t` and verified with SHA-256 and MD5 before no-replace atomic directory publication. Original rips, logs, CUEs, and all tagged staging FLACs are **never altered or removed**.
- Multidisc box sets use per-disc `Disc NN` leaf folders; existing destinations are refused. Hidden partial folders stay for inspection after a failure; there is no cleanup or overwrite. Tests include immutable originals, no-replace behavior, wrong/mutated tags, explicit confirmations, path/symlink safety and preview API opt-in. **Hardware acceptance is pending**; CI passing must not be confused with a completed user archive.
- Follow-up for user: do NOT map their existing music library writable for the first test. Mount an empty **dedicated archive-test folder** at `/archive`, set `OSCAR_ARCHIVE_ROOT=/archive` and `OSCAR_ENABLE_ARCHIVE_PUBLISH=1` in the existing Portainer stack while preserving other mounts. Preview/publish **Anastacia first**, using original job `0c81d7d445ce4e29aa95da10c866bcf9` and its **completed original tagged-copy ID**, which the user can recover from their earlier Archive Review; exact ID not yet recorded. Boulez original job `699e010ffdda46ea80cc67b07b72a28e` follows with its real completed **Classical v2 copy ID**, and explicit acknowledgement of track 24. Citycat remains **deferred and not publishable** until the correct physical MB edition is sourced.
- Full deployment steps, safety boundaries and hardware checklists: [ARCHIVE_PUBLISHER.md](ARCHIVE_PUBLISHER.md). This is the first **manual, explicit** publisher, **not yet** insert CD→Go unattended automation. Preserve OS permissions and opt-in flags; no automatic publishing or deletion.

### Current shipping features and boundaries

- Merged **#36**: optional, reviewed Classical v2 release sections, general-purpose UI, no Handel-specific demo defaults.
- Merged **#37**: CUE performers based on explicit performer relations for classical; missing classical Work link flagged for review.
- Merged **#38**: read-only Physical Release Comparison using printed catalog, barcode, linked Disc ID and track count; no physical edition *approval* is automated.
- Merged **#41**: Archive Review processing policies: `auto` chooses classical from Classical v2 copy or majority conductor credits, otherwise `standard`; standard CUE uses primary ARTIST and keeps session players in FLAC; normal `(reprise)` shared Work is not flagged. Optional manual read-only `standard`/`classical` override. **This is not a full genre classifier or automatic rip/tag workflow.**
- **New candidate discovery feature (this change):** read-only MusicBrainz search by `catno` or `release` title, no Disc ID/physical edition matching. It helps find the Citycat release even if Disc ID lookup returns only Ibiza Party. Candidate validation still requires the separate Physical Release Comparison and an exact Disc ID-linked medium for tagging. No external fallback such as Discogs/GnuDB has shipped.
- MusicBrainz alias cache and retry queue operate for artist/work **aliases only**. Full release cache, Discogs/GnuDB adapters, AcoustID corroboration and auto-approval are **not yet implemented** (see #40).
- **First manual archive publisher implemented and merged in #45**, but **hardware acceptance remains pending**; opt-in, dedicated separate archive root, FLAC/CUE manifest and optional reviewed front cover. Atomic no-overwrite and FLAC integrity checks are implemented. Automatic publishing, full cover embedding, independent archive audit and cleanup remain unimplemented (see #39). `NN - Unknown track.flac` is an intentional raw/staging filename, *not* the desired final archive name. Existing proposed rename CUE is not yet a usable archive CUE.
- Automation profiles / safe automatic insertion→Go remain future work (issue #32). Never conflate technical audio verification with physical release metadata correctness.

### Resume instructions / immediate next actions

1. After this PR's **successful main-branch CI and Docker publication**, deploy `ghcr.io/sin7ek/oscar:main` in the user's existing Portainer stack; do not change mounts or persistent `/config` without review.
2. In **Find a physical release without a Disc ID match**, search by catalog `CCC 97001`; if none, search title `Essential Dance Traxx`. Return full candidate names, dates, catalog and MusicBrainz release UUIDs; **do not** select Ibiza Party from a shared Disc ID.
3. For a promising candidate, use Citycat's verified job `95dbf0da233d4a3887800a517a149b3c` in **Physical release comparison** with physically printed `CCC 97001`. Compare titles, tracklist and art independently, document unresolved discrepancies. If MusicBrainz doesn't contain the correct release, plan adding it from the physical CD/booklet or reliable secondary sources; no guessed recordings.
4. Next code milestone: candidate resolver/cache in #40 (catalog-first and independent evidence, persistent full MusicBrainz release snapshots); archive publisher with safe naming/CUE and integrity in #39 after physical identity is settled. Test Anastacia and Boulez as regression cases.
5. Update this handoff after **every** merged feature and each hardware result, noting exact job/copy IDs where provided. For later chats ask for `docs/PROJECT_STATUS.md` on `main` and the latest completed GitHub Actions status. No need to redo prior tests.

### Related tracker

- [#32 — Safe automation modes](https://github.com/sin7ek/OSCAR/issues/32)
- [#39 — Safe final FLAC naming and archive publication](https://github.com/sin7ek/OSCAR/issues/39)
- [#40 — Metadata resolver, full-release cache and fallback providers](https://github.com/sin7ek/OSCAR/issues/40)
- [Physical release review](PHYSICAL_RELEASE_REVIEW.md)
- [Archive review and multidrive](ARCHIVE_REVIEW_AND_MULTIDRIVE.md)

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

- **Reviewed metadata + isolated FLAC tagging** (feature in progress): for verified staging jobs only, choose a particular MusicBrainz physical release with exact Disc ID/track-count match, preview album/date/barcode/catalogue, classical composer/work/conductor/orchestra relationships and track IDs, then explicitly confirm a newly created tagged copy under staging. Mutagen writes FLAC Vorbis comments only to copies, with source SHA-256 and copied audio integrity validation. No original changes, no archive publishing, no alias enrichment in tags yet. See [METADATA_STAGING.md](METADATA_STAGING.md). Hardware test against Händel 28-track rip pending.

- **Tagged-copy metadata inspector and optional trusted local UI (feature PR):** read actual per-track Mutagen FLAC Vorbis comments from completed metadata copies and compare them with the saved MusicBrainz preview, file SHA-256 and STREAMINFO MD5. New browser panel provides full tags and mismatches. Optional `OSCAR_TRUSTED_LOCAL_UI=1` removes repeated rip-token prompts after the operator explicitly trusts and isolates the interface; this does not provide authentication or change the need for action confirmations and opt-ins. Default remains token-protected. See [METADATA_STAGING.md](METADATA_STAGING.md). First successful tagged-copy job `3ac951bdd5b74ad8b484aaea955eb757` (28 tracks) awaits metadata inspection on Unraid.

- **Classical Metadata v2 (feature PR):** optional operator-reviewed physical-CD `RELEASE_SECTION` ranges, explicit MusicBrainz `WORK_PARENT`/parent IDs independent of on-disc section names, opt-in reviewer movement labels, and cached English composer/conductor/orchestra/work aliases as supplemental tags. Existing tags and MusicBrainz IDs remain intact, except obsolete overloaded GROUPING is omitted in newly generated v2 copies. Requires previously `tags_match_preview` v1 staging copy; previews are read-only, output is another unique staging subfolder with per-FLAC FLAC -t and unchanged audio MD5 checks. **Not hardware tested yet.** See [CLASSICAL_METADATA_V2.md](CLASSICAL_METADATA_V2.md).

- **Archive review / mobile / multidrive (feature PR):** read-only staging consistency-checker flagging Work-vs-Recording ambiguity and documented duration mismatches without automatic correction; exact-release Cover Art Archive front-cover candidate without embedding; copyable CUE preview preserving original INDEX/PREGAP (never guessing HTOA); responsive card-based inspector for mobile; parallel-drive status dashboard and per-install configurable concurrency cap (default 3; 1–16). Standard pop/house/VA album tagging path remains supported; classical v2 is optional. Separate source files and copy manifests are never modified. Hardware acceptance of simultaneous 3+ drives, artwork and CUE review still pending. See [ARCHIVE_REVIEW_AND_MULTIDRIVE.md](ARCHIVE_REVIEW_AND_MULTIDRIVE.md).

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
- **First tagged-copy regression (2026-11-19):** Verified Händel job `f41806152a614b1a9006b10456b9bbd4` successfully produced a metadata preview, but copy `f33d9944db4b454db5ddc82ea746ef95` failed with `AttributeError: 'int' object has no attribute 'hex'`. Mutagen exposes FLAC STREAMINFO MD5 as a 128-bit integer; OSCAR attempted to serialize it as bytes. Fix normalizes the integer to a zero-padded 32-digit hex string; adds regression tests for real Mutagen representation. Old copy may contain **partial tagged FLACs**: do not treat it as completed or delete original staging. A new reviewed copy attempt creates a fresh UUID subdirectory. Unraid retest pending.
- **First on-hardware tagged FLAC metadata inspection — 2026-11-19:** Completed tagged-copy `3ac951bdd5b74ad8b484aaea955eb757` from Händel reference job `f41806152a614b1a9006b10456b9bbd4`: OSCAR returned `tags_match_preview` for **28/28 actual saved Vorbis-tagged FLAC files**, zero deviations from reviewed MusicBrainz preview, saved-copy SHA-256 matches and preserved FLAC STREAMINFO MD5 matches. Original rip unaffected. **Editorial review remains required**: the release's on-disc *Water Music Suite I* (tracks 1–12) is mapped in MusicBrainz to HWV 349 and HWV 350, while on-disc *Suite II* (tracks 13–22) maps to HWV 348; these are different organizing schemes and should not be conflated in `GROUPING`. Tracks 18 (*Air*) and 21 (*Aria*) are linked to the same HWV 348 *Air. Presto* work; investigate before assuming mistake or rewriting relations. Fireworks tracks 23–28 map to HWV 351. Next: hardware-test the new Classical v2 reviewed release-section/work separation and alias preview, then design complete artist/work/movement relationships, release CUE, artwork and archive publisher without making unverified inferences. `tags_match_preview` means tagging fidelity, **not** metadata editorial correctness.
- **First full three-drive hardware acceptance success — 2026-11-19:** Three CD jobs run concurrently on GH24NS95 `/dev/sr1` (`0c81d7d445ce4e29aa95da10c866bcf9`, 12 tracks), Optiarc AD-7200S `/dev/sr2` (`699e010ffdda46ea80cc67b07b72a28e`, 32 tracks), and hp DH16AAL `/dev/sr3` (`95dbf0da233d4a3887800a517a149b3c`, 14 tracks). All 58/58 FLAC files passed fresh FLAC decoding and SHA-256 rechecks, all CUE file references matched, no ripping errors, and all three verification reports now show `checks_passed`. The 12-track CD has AccurateRip v1/v2 confidence 200 for all tracks; the 32-track CD has v1 confidence 8 and v2 64–65; the 14-track CD has v2-only confidence 4 for every track, no v1 reported, correctly accepted with disclosed single-version coverage after PR #35. This proves three simultaneous extraction jobs and subsequent staged verification on the user's Unraid hardware, **not** metadata correctness, CTDB validation, archive publication or restart recovery. Next: identify each job's exact Boulez/house/pop physical release and test distinct tagging/consistency workflows.
- **Safety note:** these checks concern metadata identification only, not secure ripping or AccurateRip validation.

## Prioritized actions

**Use the CURRENT HANDOFF above for priority and real-world status.** The earlier action list was created before the completed three-drive hardware acceptance and is now superseded.

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
