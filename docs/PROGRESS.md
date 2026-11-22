# OSCAR — Development progress dashboard

**Matrix/runout:** MusicBrainz release-annotation search and optional disc-level operator transcription are available in the [archive publishing workflow](ARCHIVE_PUBLISHER.md). A new tagged copy carries `MATRIX_RUNOUT` through to the publication preview, archived `SOURCES.txt` and manifest. Tower acceptance is pending.

## Current status — 2026-11-22, through PR #140

**Latest feature on `main` and GHCR:** [#140 DriveFit](https://github.com/sin7ek/OSCAR/pull/140) merged as `5368f6489da5755fe7fb53f99c41d0af7d01b17d`. GitHub [Tests](https://github.com/sin7ek/OSCAR/actions/runs/45072660464) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45072660444) passed. The OCI revision of `ghcr.io/sin7ek/oscar:main` for Linux/amd64 matched that commit at registry digest `sha256:ecbd840da41f318446145ce686f73d73baf2a20f9492d5545a75b39878150e56`. Tower pull and DriveFit acceptance remain open.

| Change | GitHub and image | Tower evidence |
| --- | --- | --- |
| [#140 DriveFit](https://github.com/sin7ek/OSCAR/pull/140) | Merged, both checks green, GHCR revision confirmed. Replaces draft #111 as the shipped implementation. | Check samples, normalized GH42 speed and LG diagnostic Track 07. Historical metrics depend on surviving staging; new summaries persist in SQLite. |
| [#139 Both Track Recovery attempts in provenance](https://github.com/sin7ek/OSCAR/pull/139) | Open at `023e06b`; [Tests](https://github.com/sin7ek/OSCAR/actions/runs/45070962329) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45070962389) passed. Outside the #140 image. | Pending. New jobs capture both attempted sources and their available extraction evidence; older jobs can identify unavailable history. Digital acquisition remains a future input. |
| [#138 Per-track archival SOURCES](https://github.com/sin7ek/OSCAR/pull/138) | Merged as `255c4f1`; [Tests](https://github.com/sin7ek/OSCAR/actions/runs/45067284484) and [Docker build](https://github.com/sin7ek/OSCAR/actions/runs/45067284462) passed; included in #140. | Read-only **Proposed SOURCES.txt** and subsequent publication remain open. Track 07 should name the LG diagnostic job, other tracks the Optiarc job, with verification attributed separately to `trackverify`. |
| [#134](https://github.com/sin7ek/OSCAR/pull/134) / [#136](https://github.com/sin7ek/OSCAR/pull/136) Track Recovery | Merged and shipped. #136 fixes the bundled verifier's runtime extraction failure. | Mahler Disc 11 reached Archive Review after 17/17 independent AccurateRip v1/v2 matches. Physical edition approval and publication are open for Disc 11. |
| [#132 Optical controls](https://github.com/sin7ek/OSCAR/pull/132), [#131 Tracked Go jobs](https://github.com/sin7ek/OSCAR/pull/131), [#130 USB drive IDs](https://github.com/sin7ek/OSCAR/pull/130), [#127 ETA](https://github.com/sin7ek/OSCAR/pull/127), [#126 Refreshed-copy adoption](https://github.com/sin7ek/OSCAR/pull/126) | Merged and included in #140; PR checks passed. | LG selected-track extraction worked. Tray/Stop, full four-drive UI regression check, tracked job filtering, ETA and refreshed-copy adoption still need distinct acceptance results. |

**Tower archive maintenance:** Carmen Gomes and Anastacia single-CD Verify passed, including the superseded Anastacia generation after #120. Anastacia showed Pop / Popular in Collection. Boulez's initial 2/6-disc preview progressed to 6/6; CDs 4 and 6 alone were revised (39 FLACs), then read-only Integrity Verify passed. Cleanup, boxset GENRE Apply and controlled failure recovery have separate acceptance gates. See the [work document](PROJECT_STATUS.md) and [handoff](DEVELOPER_HANDOFF.md).

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

**Last assessed:** 2026-11-20  
**Assessment type:** qualitative estimates by the project team / ChatGPT, **not measured engineering KPIs**.  
**Canonical status and evidence:** [PROJECT_STATUS.md](PROJECT_STATUS.md)  
**Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md)

> This dashboard tracks implementation maturity toward the eventual **insert CD → Go** experience. The percentages are subjective progress estimates, not test pass rates, promises or objective milestones. Passing CI does not mean a feature has been accepted on real Unraid hardware. Do not calculate a single overall project completion percentage from these different domains.

**Subsequent operator evidence (same date):** after explicitly clicking Apply, the OSCAR UI reports `1 recorded archive revision operation(s)` with status **`completed`**, source `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]`, destination `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`, and retained-original path `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`. Unraid file-manager screenshots show the renamed album directory, `ExtractionEvidence` and visible newly modified FLACs (first ten of twelve on screen). **This confirms user-visible completion and filesystem promotion, NOT yet independent verification of Vorbis `LABEL=CFMusic`/`CATALOGNUMBER=CGi2010` on all 12 tracks, `flac -t` integrity, retained original file digests, Collection SQLite linkage, restart persistence, or archive rescan.** Request independent `metaflac` / `flac -t` shell results before upgrading acceptance to fully verified.

**Unraid independent FLAC tag acceptance (2026-11-20, after completed archive revision):** operator ran `docker exec oscar python` using Mutagen on all twelve FLACs under `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]` and pasted full per-track results. **All 12/12** contain `CATALOGNUMBER=['CGi2010']`, `LABEL=['CFMusic']`, `MUSICBRAINZ_ALBUMID=['fa89edc1-32f9-4290-8788-bbac2e366a46']`, and `RECORDLABEL=[]`. This independently confirms the new published FLAC tags for all twelve tracks after the UI reported revision `completed`. **Now independently verified:** `flac -t` on all 12 new files (12/12 passed). **Still pending:** original retained-generation SHA-256/byte integrity, final Collection SQLite row/path and rerun-scanner suppression, restart persistence and interrupted-journal recovery. Do not call full end-to-end acceptance complete yet.

---

**Real Unraid post-migration audio acceptance (2026-11-20):** the operator ran `docker exec -i oscar python - <<'PY'` against the twelve new FLAC files in `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`. The script invoked `flac -t --silent` independently on **all 12 files**, and every track returned `OK` (`Resultaat: 12/12 FLAC-bestanden geslaagd`). Combined with the earlier 12/12 Mutagen checks, the revised publication now has independently confirmed catalog `CGi2010`, label `CFMusic`, release ID and successful FLAC decoding for every track. **Not yet confirmed independently:** retained original version hashes/contents, Collection SQLite path and revision linkage, rerun scanner suppression, restart persistence or journal crash recovery. Do not state full end-to-end acceptance until appropriate checks complete.

---

**Real-Unraid retained-original integrity acceptance (2026-11-20):** the operator used a read-only Python SHA-256 check of each FLAC against the original archived `manifest.json` under `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`. **All twelve originals passed (12/12 SHA-256 matches)**. Together with independently confirmed 12/12 migrated FLAC tags and 12/12 successful `flac -t` checks, this verifies the engine's promised retained original audio-file bytes against publication evidence. Still outstanding for full end-to-end Unraid acceptance: Collection SQLite archive path/catalog link and two proposal `applied` statuses, post-migration scanner, restart persistence and recovery from interrupted journal. A retained-manifest self-hash or non-FLAC CUE/evidence reread has not been separately established by this test.

---

## Real-Unraid Carmen Gomes archive migration preview (2026-11-20)

The operator demonstrated a working read-only migration preview on live Unraid for the 12-track Carmen Gomes Inc. *Desire*: 2 approved changes, catalog number `CGi2010`, correct proposed archive folder rename and original publication ID `3908eef79f114450b0a7eb76bec44926`. **No apply or archive mutation occurred**. Actual generation promotion, retained original, `flac -t`, Collection transaction and crash recovery still require separate acceptance with backups and free-space checks. No maturity percentage increase for a preview alone.

---

## Carmen Gomes single-CD archive migration — live Unraid primary happy-path ACCEPTED (2026-11-20)

Operator supplied independent **read-only** SQLite queries against the running OSCAR container *after* the migration finished. Results:

- Exactly **one** `archive_items` row for MusicBrainz release `fa89edc1-32f9-4290-8788-bbac2e366a46`, with `archive_path=/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`, `catalog_number=CGi2010`, `label=CFMusic`, and `track_count=12`.
- Exactly two matched `metadata_proposals` rows: `CATALOGNUMBER` and `LABEL`, both **`status=applied`**, originating from `before_json=[]`, targeting `["CGi2010"]` and `["CFMusic"]`.
- Corresponding `archive_revision_operations` reports **`completed`**, the correct old/new paths and original retained generation `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`.
- From previous independent Unraid checks: all **12/12 new FLACs** contain the approved catalog/label and correct MusicBrainz release ID (Mutagen), **12/12 new FLACs** pass `flac -t`, and **12/12 retained original FLAC SHA-256s** match their original publication manifest.

**Acceptance judgment:** the normal **single-CD archive-revision apply, version retention, metadata write, audio decode, proposal state transition, and Collection SQLite rebind** are now validated on real Unraid. This is **not** proof of complete crash/restart resilience. Still pending: post-apply repeat whole-archive scan (no duplicate or stale proposals), container restart and persistence, interrupted-journal recovery under controlled failure, full non-FLAC CUE/evidence hash verification, and a separate boxset-safe migration (not implemented). No additional archive mutation is authorized or necessary for these read-only checks.

---

## Second real-Unraid archive revision recorded — Anastacia label-only, same destination (2026-11-20)

The operator's live **View archive revision history** now reports **2 completed operations**:

- **Anastacia — *Freak of Nature* (2001)**, MusicBrainz release prefix `4b370e6c`: `completed`, **source and destination intentionally identical**: `/archive/Anastacia/[504757 2] Freak of Nature (2001) [4b370e6c]`. This is a label-only metadata revision; `504757 2` was already the reviewed catalog number, so no album-directory rename is needed. Original generation retained according to journal at `/archive/.oscar-archive-versions/5ff97661e98742afbf5db690f827d0f1/f5e41eef584c44288cc76a2a8477e635`. Previously approved `LABEL` values were `Daylight` and `Epic`. **Evidence is operator-provided revision-history status only.** Independent new FLAC-tag checks, `flac -t`, original manifest SHA-256 checks, and Collection/proposal SQLite checks have **not yet been reported**; do not call Anastacia fully validated.
- **Carmen Gomes Inc. — *Desire* (2010)**: `completed`, original `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]` → revised `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`, retained original at `/archive/.oscar-archive-versions/3908eef79f114450b0a7eb76bec44926/f670468afcbb4c168adfdffae1df69bd`. This operation already passed independently verified 12/12 tags, decoder, original FLAC hash and SQLite/decision checks.

**Next:** collect the operator's read-only independent verification results for Anastacia (new FLAC labels `Daylight` and `Epic`, release UUID, `flac -t`, SHA-256 against retained original manifest, and Collection `label`, archive path, `applied` proposal); separately verify post-revision full-archive scan, restart persistence and failure recovery. Never migrate the Boulez 6CD with the current single-CD engine.

---

## Anastacia live-Unraid label-only archive revision verified; Collection label normalization (2026-11-20)

The operator independently verified the second successful single-CD revision, Anastacia *Freak of Nature* (2001): **12/12 new FLACs** have the reviewed `LABEL` values **Daylight** and **Epic** and the correct MusicBrainz release UUID; **12/12** pass `flac -t`; **12/12** retained originals match the original publication manifest SHA-256 checks. Read-only Collection query confirms the original album path (unchanged catalog `504757 2`), `track_count=12`, proposal `LABEL` status `applied`, but Collection's local `label` shows only `Epic` after UI Refresh: this is a **real catalog projection inconsistency**, not a FLAC retagging failure.

Root cause: `archive_revision._finalize` previously filled local `label` **only when blank**, retaining an older MusicBrainz-enriched source label `Epic` even after approved FLAC revision to `Daylight; Epic`. In PR #106 the finalization updates Collection labels from explicitly approved revisions **only if their existing provenance is known to be OSCAR/MusicBrainz-sourced or blank**, and records `archive_revision_approved_labels`; genuinely manual/unknown values remain untouched. UI wording changes from **Record label** to **Label**. Both refer to the release's record label; `RECORDLABEL` is treated as a legacy FLAC alias of canonical `LABEL`, **not** another distinct label entity. The existing Anastacia row can now be repaired through an explicit **Synchronize applied labels (Collection only)** action: it verifies the completed revision's FLAC hashes and exact approved label tags and changes only OSCAR/MusicBrainz-sourced local labels, preserving manual values. This feature has GitHub regression coverage but needs live Unraid acceptance.

Remaining operator requests: archive **Verify** (actual FLAC/manifest/CUE/source evidence, original-generation and Collection checks), operator-approved **Clean** and **Verify & Clean** to remove only explicitly verified retained generations with clear irreversible-loss warnings and strong journaling/race protection, plus **coordinated multi-disc** support for Boulez (discs 4 and 6 present, others absent). DO NOT silently delete `.oscar-archive-versions` or attempt single-disc apply to a boxset. Media servers may index hidden history; advise exclusions or separate archive mounts until cleanup is safely implemented. These are scoped follow-up engineering milestones, **not delivered in PR #106**.

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

## Initial coordinated LABEL preview for incomplete releases (2026-11-20, PR #108)

The next implementation adds `src/oscar/archive_revision_boxset.py` plus an authenticated Collection **Preview coordinated multidisc labels (read-only)** action. The operator selects any archived disc of the release in the existing Advanced Collection album selector. OSCAR verifies **all indexed/published leaves** under the same physical MusicBrainz release ID, each live FLAC manifest SHA-256 and Disc ID/CD medium/recording identity, exact current MusicBrainz release labels, and corresponding accepted per-disc label decisions. One group summary reports available and missing disc numbers, target label, each disc's tag status and approval fingerprint. Specifically, the operator's *Boulez Conducts Stravinsky* 6CD can show discs **4 and 6 present**, discs **1, 2, 3 and 5 missing**, with approved **Deutsche Grammophon** proposals on available discs if current metadata still agrees.

**No Apply exists in this preview.** `apply_supported: false` explicitly prevents accidentally running the single-CD migration on a boxset. **Next separate milestone**: design and test a durable, coordinated all-or-none multi-leaf apply/reconciliation journal with no invented data for missing media and full physical-CD/manifest provenance. Neither current boxset FLACs nor Collection labels are modified by preview. GitHub tests are not equivalent to a real Unraid boxset preview.

---

## Open-source beginner onboarding — draft only (2026-11-20)

Created an explicitly **unreviewed** commented Unraid/Portainer Compose example: [`compose.unraid.example.yml`](../compose.unraid.example.yml). It is a documentation baseline, **not** a tested/recommended replacement for the operator's existing working stack. Required next steps: review exact Docker/Portainer compatibility, network/access controls, mounting and permissions, drives, token handling, archive revision opt-in and safe defaults. **Planned:** `GETTING_STARTED.md` (planned) (not yet written), a true beginner guide to Docker concepts, prerequisite checks, selecting bridge vs br0 networking, secure secrets, first rip, first archive publish, maintenance, updates and troubleshooting. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the full checklist. No maturity percentage increase for an untested documentation draft.

---

## Developer handoff and exact label handling (2026-11-20)

Added a dedicated [developer handoff](DEVELOPER_HANDOFF.md) for OSCAR chat 5, separate from chronological project status and progress scores: concise source map, verified status vs untested claims, 7 Unraid decision events, blockers, migration safety contracts and explicit next tasks. The latest operator report includes separate accepted Deutsche Grammophon labels on Boulez discs 4 and 6; these are **not applied archive changes**. PR #98 merged after GitHub Tests and Docker CI; its code addresses missing initial `LABEL` tags and `RECORDLABEL` alias detection; a safe coordinated boxset migration still remains future work. GitHub tests and Docker build succeeded; real Unraid verification of the new LABEL/RECORDLABEL behavior is still pending. No maturity percent increase.

---

## Operator-reviewed archive metadata revision (2026-11-20; PR #95 merged, Unraid acceptance pending)

PR #95 was merged into main after successful GitHub Python Tests and Docker build; it implements a separately enabled, **staging-independent** archive migration for one CD leaf at a time: preview all accepted proposals, explicitly confirm, create and verify a new tagged generation, preserve untouched original under hidden `.oscar-archive-versions`, update catalog-based folder naming and Collection SQLite row, and journal the transaction with an explicit recovery pathway. Applies only verified proposed values; `applied` history is distinct from approval. The bulk scanner now discovers published manifest paths directly rather than relying only on an indexed Collection row. Multidisc/boxset migration is blocked and remains a future milestone. Real Unraid validation and integration tests with actual FLACs remain necessary. No maturity percentage increase yet.

---

## Bulk archive scanner and Discogs PAT variable (2026-11-20)

PR #94 (merged after GitHub Tests and Docker CI) implements asynchronous **whole published archive** MusicBrainz scans with per-album progress/error isolation. One-album scans move to Advanced; the legacy Collection label-enrichment tool remains in Advanced because it serves a different read-only-external/write-local-Collection task. Discogs connection renamed to `OSCAR_DISCOGS_PAT`; Unraid Portainer environment must be updated at deployment. The MusicBrainz release UUID was already in FLAC `MUSICBRAINZ_ALBUMID`. No real-Unraid archive metadata migration has yet been performed; PR #95 added the opt-in implementation. Maturity estimates remain unchanged pending real Unraid acceptance.

---

## Unraid archive metadata decision history acceptance (2026-11-20)

The operator demonstrated five SQLite history events on Unraid: Carmen Gomes `CGi2010` accepted, CFMusic ignored → reopened → accepted, and Anastacia Daylight/Epic accepted. The review-decision history now has real-world acceptance evidence; same-value suppression after a rescan and restart persistence remain pending. A small UI fix hides **Reopen decision** on superseded historical entries and requires the actual current accepted/ignored status. No FLAC/manifest/Collection metadata migration is yet implemented. Qualitative progress percentages remain unchanged.

---

## Reversible archive decisions / catalog naming migration (2026-11-20)

Feature branch adds **Reopen decision** for the operator's accidentally ignored CFMusic label on Carmen Gomes Inc. *Desire*; old Ignore is retained as an immutable historical event and the exact proposal can be accepted after reopening. An accepted catalog number `CGi2010` is still **approval only**. Future archive metadata migration is explicitly required to update the album folder from `Desire (2010) [fa89edc1]` to `[CGi2010] Desire (2010) [fa89edc1]`, with verified safety/rollback and catalog path reconciliation. No file rename in this feature. CI + real Unraid acceptance pending; progress percentages unchanged.

---

## First real Unraid archive-scanner result (2026-11-20)

OSCAR's Collection UI displayed four selectable published leaves: Anastacia, Carmen Gomes Inc., and Boulez/Stravinsky discs 4/6 and 6/6. A Carmen Gomes scan found **2 differences** (missing `CGi2010` catalog number and `CFMusic` label); the **global pending queue showed 3 proposals**, including a previously observed Anastacia label addition (`Daylight`, `Epic`). This confirms archive scanning and pending-proposal display on real Unraid. It does **not** yet verify durable Accept/Ignore suppression after rescans or container restart, nor actual archive metadata application. Keep existing qualitative percentages unchanged.

---

## Archive metadata scanner — PR #89 merged, Unraid acceptance pending (2026-11-20)

Collection receives staging-independent read-only **Scan archive for metadata additions** and **Scan archive for metadata changes** plus persistent Accept/Ignore proposals and history. Validates published FLAC hashes, queries exact MusicBrainz CD medium and stores non-destructive proposals in `catalog.sqlite3`. Accept is approval for a separate future migration, **not an applied FLAC update**. GitHub Tests and Docker CI passed before merge (commit `f25e374`). No percentage increase before real Unraid acceptance. See [ARCHIVE_METADATA_LIFECYCLE.md](ARCHIVE_METADATA_LIFECYCLE.md).

---

## Archive-first metadata maintenance — design only (2026-11-20)

Future Collection actions: **Scan archive for metadata additions** and **Scan archive for metadata changes**, independent of temporary staging. Persist specific Accept/Ignore decisions; identical proposals stay suppressed, while genuinely new provider values or archive revisions can produce fresh proposals. Preserve immutable ripping evidence and archive history; only a separate audited, operator-approved archive-version migration may modify released metadata. See [ARCHIVE_METADATA_LIFECYCLE.md](ARCHIVE_METADATA_LIFECYCLE.md).

**No maturity-percentage increase:** implementation and real Unraid acceptance are still pending.

---

## Real Unraid acceptance — newly tagged staging copy (2026-11-20)

**PR #84 reprocessing accepted on operator's Unraid deployment:** newly generated Carmen Gomes Inc. *Desire* copy `cd2959e6cc2b4c4ab6fafb590808b2db` is `tagged_copy_ready_for_review`; inspecting actual FLAC tags and hashes gives `tags_match_preview` for all **12 tracks**. No archive publication occurred, and the original published archive is reported unchanged. This follows the confirmed read-only comparison detecting the corrected MusicBrainz catalog `CGi2010`. **Archival migration and Collection reconciliation are not implemented or verified yet.** Qualitative dashboard percentages remain unchanged until larger-sample validation.

---

## Collection catalog recovery and missing catalog warning (2026-11-20)

The operator observed `ARCHIVE_PUBLISHED · catalog: indexed` for *Carmen Gomes Inc. — Desire*, but Collection still reported three records and zero imports. The code fix accepts valid archive folders without a printed catalog prefix and confirms the SQLite row exists before reporting `indexed`. Additionally, future physical-CD archive reviews flag a missing MusicBrainz catalog number for explicit acknowledgment instead of silently omitting it. No numbers are invented, and existing audio, manifests and archive names are not changed.

**Validation status:** implementation on test branch; GitHub CI and real Unraid Collection re-import remain acceptance gates. Existing dashboard percentages remain unchanged.

---

## Latest engineering change — MusicBrainz match refresh (2026-11-20)

PR #79 merged to `main` after passing GitHub Tests and Docker build (commit `ca0239a`); Unraid acceptance for read-only refresh confirmed by operator on Carmen Gomes Inc. *Desire* job. Implemented: operator-triggered, authenticated read-only refresh of an accepted MusicBrainz release's current Disc ID medium association. The saved TOC, disc ID, and completed verification are checked before the network lookup. Historical `INFERRED_OPERATOR_ACCEPTED` is never upgraded, and no audio, tagging, or archive operation is triggered. See [MUSICBRAINZ_MATCH_REFRESH.md](MUSICBRAINZ_MATCH_REFRESH.md) and [PROJECT_STATUS.md](PROJECT_STATUS.md).

**The operator's Unraid GUI now confirms the saved Disc ID is attached on medium 1 of the accepted release, while preserving the original inferred-approval status.** Percentages remain unchanged because this validates one bounded feature, not fully automatic release certainty or independent pressing identification.

Branding foundation #78 is merged to main; image binary integration and Unraid visual acceptance remain outstanding.

---

## Current development — safe MusicBrainz metadata refresh / restaging (2026-11-20)

PR #84 has been merged to main after successful GitHub Tests and Docker build (commit `c5625a7`). The new implementation adds read-only comparison between fresh MusicBrainz metadata and the accepted prior tagged copy; after explicit operator confirmation it may create a new verified-copy staging job **without changing the already published archive or the original durable workflow**. The Carmen Gomes catalog correction has not yet been confirmed live on Unraid. All GitHub Tests + Docker build must pass before merge; user hardware acceptance follows. See [METADATA_REPROCESS.md](METADATA_REPROCESS.md) and [PROJECT_STATUS.md](PROJECT_STATUS.md).

**Maturity percentages remain unchanged** pending repeatable tests and operator-confirmed deployment. Archive replacement/migration is not part of this feature.

---

## Unraid acceptance — MusicBrainz catalog correction observed (2026-11-20)

The operator tested PR #84 against existing Carmen Gomes Inc. *Desire* and saw the current MusicBrainz release return catalog `CGi2010`, absent in the original saved metadata. OSCAR correctly displayed 14 changes: one album catalog field, one CFMusic label catalog field, and the 12 proposed CATALOGNUMBER track tags. **Read-only comparison accepted on real Unraid.** A separate newly tagged staging copy has **not** yet been reported verified, and archive/Collection migration remains future work. Do not inflate domain maturity percentages based on the preview alone.

---

## Progress by area

| Area | Progress | Visual progress | Evidence / remaining gaps |
|---|---:|---|---|
| CD ripping on Unraid | **90%** | `█████████░` | Concurrent physical rips and an isolated LG diagnostic extraction observed; unattended detection and tray/Stop acceptance remain |
| FLAC & staging verification | **85%** | `████████▌░` | FLAC decode, SHA-256, CUE and cyanrip evidence verified on Tower; independent verification also exercised in Track Recovery |
| MusicBrainz & release selection | **80%** | `████████░░` | Boulez multi-disc media 4/6 and 6/6 archived; operator-accepted single-CD missing Disc ID fallback and user-controlled MusicBrainz TOC attach handoff (#74–#76); fresh read-only Disc ID match refresh accepted on real Unraid Carmen Gomes job (#79); unattended edition certainty remains |
| Classical metadata | **70%** | `███████░░░` | Works, performers and multidisc review; further edge cases remain |
| Archive publishing | **90%** | `█████████░` | Reviewed publication and versioned revision observed on Tower; new SOURCES preview and recovered publication pending |
| Independent AccurateRip / CTDB | **20%** | `██░░░░░░░░` | Independent AccurateRip v1/v2 passed 17/17 on Tower for Track Recovery; general independent verification and CTDB remain open |
| Automatic end-to-end workflow | **45%** | `████▌░░░░░` | Three-mode Go! workflow with durable release acceptance, isolated tagged copies and human-approved archive publish demonstrated; still user-advanced, no automatic CD insertion/fully unattended orchestration |
| Recovery, resume & cleanup | **20%** | `██░░░░░░░░` | Local selected-track recovery verified through Archive Review; versioned revision Verify passed. Controlled interruption, resume and cleanup acceptance remain open |
| Local & multi-platform collection management | **25%** | `██▌░░░░░░░` | Local catalog, export, logical genre sections and read-only Discogs PAT support; external collection sync and MusicBrainz OAuth remain open |

### Bar chart

This Mermaid chart uses the same baseline estimates as the table above (scale 0–100). The table is the accessible fallback when a GitHub client does not render Mermaid charts.

```mermaid
xychart-beta
    title "OSCAR development maturity estimates — reviewed 2026-11-22"
    x-axis ["Ripping", "FLAC staging", "MusicBrainz", "Classical", "Publishing", "AR/CTDB", "Automation", "Recovery", "Collection"]
    y-axis "Estimated progress (%)" 0 --> 100
    bar [90, 85, 80, 70, 90, 20, 45, 20, 25]
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
| 2026-11-22 | Reviewed through #140; no percentage change. | Recorded the narrow Tower Track Recovery and archive-revision results. Broader verification, hardware acceptance, cleanup and orchestration remain open. |
| 2026-11-20 | Reassessed MusicBrainz 75 → 80, archive 85 → 90, Go! automation 30 → 45; added separate collection-management 25. These are **subjective** domain maturity estimates, not completion or CI coverage. | Real Unraid: Boulez CD 4 and CD 6 both `published_verified`, separate `Disc 04`/`Disc 06` folders under one boxset; Disc ID of Carmen Gomes *Desire* attached to MusicBrainz via human-confirmed handoff; #74–#76 merged/tested. MusicBrainz OAuth, automated insertion, error recovery still not built. |

| Date | Change | Evidence |
|---|---|---|
| 2026-11-19 | Reassessed after PR #58 configuration UI (Best Guess / three Secure review levels); no percentage change because execution policies and unattended orchestration remain future work. | Settings migration/validation tests and [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 2026-11-19 | Reassessed after risk-based physical edition candidate UI; percentages unchanged pending Unraid testing and server-enforced approval evidence. | Unique candidates inspected read-only; ambiguous candidates prompt for catalog; see [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 2026-11-19 | Reassessed; no percentage change. PR #52's archive-audit CLI ran on real Unraid: 1 album, 12 FLACs, PASS_WITH_WARNINGS (expected EVIDENCE_NOT_EMBEDDED). Source-evidence embedding from PR #51 and independent CTDB are still untested. | User's terminal output of `docker exec oscar python -m oscar.archive_audit /archive`; [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| 2026-11-19 | Initial baseline: 90 / 85 / 75 / 70 / 85 / 20 / 30 / 20 | Physical multi-drive tests, verified Anastacia archive publishing (PR #50), source evidence preservation (PR #51, CI-tested), read-only archive auditor (PR #52, CI-tested), documented in [PROJECT_STATUS.md](PROJECT_STATUS.md) |

## Soloist metadata classification correction — PR #65

Real OSCAR Collection Library feedback exposed broad session performers incorrectly classified as soloists on pop albums. Fixed by preserving full source performer credits and limiting classical soloist display to explicitly tagged classical albums with soloist-marked contributor roles. Re-import can repair old automatically derived fields without changing archives. No change to Go controller or project progress percentages.

## Go! executable phase one — PR #64

Automatic durable job creation at rip start, verification callback and read-only release candidate discovery have been added with a single Go! interface. No automatic tagged-copy or final archive publication yet. **Keep the maturity estimates unchanged** pending GitHub checks, real Unraid physical acceptance and end-to-end safe tagged-copy/publish orchestration. Next priority: verified release resolver and explicit policy enforcement.

## Persistent workflow ledger toward Go! (PR #63)

A durable per-rip phase/event ledger with user mode snapshot and safe review deferral has been implemented as a **manually registered foundation**. It is not yet an automatic scheduler, and cannot restart an interrupted rip or auto-tag/archive. Maintain the eight qualitative percentages pending real Unraid acceptance and an executing state machine.

## Track-level collection evidence + Go! roadmap (PR #62)

Source-backed track/credit/Work indexes and a strictly exact-release+catalog MusicBrainz label-backfill action have been added to the collection workflow. **No completion-percentage increase yet:** CI and actual Unraid verification are separate; a persistent per-disc controller and safe metadata decision engine are not implemented. The next development priority is [AUTOMATION_ROADMAP.md](AUTOMATION_ROADMAP.md), not continued collection UI polish.

## Nextcloud-compatible exports and classical album discovery (PR #61)

Adds XLSX download plus read-only album-level search/sort by label and classical performers; safe in-place SQLite migration, and explicit label evidence recorded in *future* publication manifests. Track-level classical Work/Soloist tables, independent backfill of old label metadata and remote Discogs collection writes are still missing. Do **not** inflate existing percentages until CI, actual Unraid import and Nextcloud editor checks.

## Phase 1 collection catalog progress (PR #60)

Local database of OSCAR published archives, ODS/CSV export, sortable UI, read-only Discogs PAK identity/folder access and fixed metadata rip attribution are implemented in code. These do not yet provide a comprehensive physical ownership database, remote collection write, edition matching or automatic workflow. Keep all existing qualitative percentages unchanged pending CI and real Unraid acceptance.

## Proposed collection management extension

[Discogs and OSCAR local catalog design](DISCOGS_COLLECTION_CATALOG.md) covers secondary physical-edition discovery, optional collection sync, condition/sleeve/notes/folder entry, per-copy identity and sortable **ODS-first** export. **Design only: no implementation or progress-percentage change** until concrete features and tests exist. The initial eight baseline maturity estimates remain unchanged for that earlier design-only proposal; collection management is now tracked separately.

## Current development priorities

1. Test DriveFit and the read-only recovered Disc 11 SOURCES preview on Tower. Review the physical edition separately before any publication.
2. Verify the remaining tracked Go jobs, ETA, tray/Stop, refreshed metadata adoption and genre workflows on hardware. Test journal interruption and restart on designated fixtures.
3. Finish the public onboarding guide after reviewing the example Compose. Keep artwork, broader independent verification including CTDB, and external Collection integration on the roadmap.

*This is a planning aid, not a substitute for releases, CI logs, actual test reports or documented source evidence.*
