# OSCAR — CD inserted → Go! automation roadmap

## Current Go! workflow — 2026-11-25

Go! runs rip and verification, records edition lookup evidence and guides the operator through the configured release and archive review. The three policy choices are available. Explicitly enabled Best Guess can automatically publish when all of its checks pass. Semi Automatic has been exercised through reviewed publication on Tower. Insertion-triggered ripping is available as an explicit per-drive opt-in. Tower acceptance and unattended review remain open.

### Automatic start on insertion

Under **Settings → Optical drives**, enable **Start ripping automatically when I insert an audio CD** on each drive you want to use, then save. The drive must be enabled, persistently identified and have a configured read offset. Automatic start is off by default and requires the existing ripping opt-in. Saving the setting uses the existing rip authorization.

OSCAR must observe an empty drive or open tray followed by two consecutive observations of a CD with audio tracks. Leave the tray open for at least one three-second poll when replacing a disc. The monitor respects the concurrent-rip limit and starts the regular tracked Go! extraction and post-rip verification. The result appears in RipReview. A disc already inserted at service startup or when opting in requires a manual Go! start or an observed removal and reinsertion.

### RipReview

The Go! worklist reads the persistent job ledger and saved extraction evidence. It groups jobs by next action, including read again, audio/data review, edition review and archive review. Lookup gaps remain visible separately from a reported mismatch. For a proven track-specific issue, Review recommends an eligible idle drive using DriveFit and can start a separate, explicitly confirmed diagnostic after checking the inserted Disc ID. Track Recovery opens with both job IDs and the affected tracks filled in.

Unattended re-reads and automatic recovery remain future increments. RipReview neither changes verification and publication policy nor starts another physical read merely because an issue was detected.

### Advanced review handoffs

Review provides prefilled handoffs from a verified rip to metadata preview, tagged-copy inspection and read-only archive preview. Semi Secure and Secure expose optional physical identifiers for MusicBrainz/Discogs comparison. Guided Disc ID attachment uses operator confirmation on MusicBrainz. Go! records independent CTDB evidence for eligible full-disc rips and includes it in the archive provenance.

See the [dashboard](PROGRESS.md) and [current acceptance tests](PROJECT_STATUS.md#next-acceptance-checks). The milestones below retain their original design and implementation context.

## One verified audio pipeline; three top-level operating modes (design decision, 2026-11-19)

**Requested ordering:** **Best Guess (Full Automatic) → Semi Secure (Semi Automatic) → Secure**. This is the intended future policy design; the current persisted configuration and Go! phase 1 still only implement `best_guess` and `secure`. Do not claim `semi_automatic` is available until its UI, configuration, ledger and transition guards are implemented and tested.

Audio checks remain equally strict in **all three** modes: cyanrip extraction into preserved original staging, FLAC decode, SHA-256, CUE consistency, audio verification and immutable evidence. A matching MusicBrainz Disc ID is candidate evidence, **not** proof of physical pressing. The three modes differ in how much release-identity uncertainty and operator interaction they permit—not in audio-integrity standards.

| Policy | Best Guess — Full Automatic | Semi Secure — Semi Automatic | Secure — evidence-first |
|---|---|---|---|
| Rip and verify | Automatic | Automatic | Automatic |
| Disc ID / TOC / MusicBrainz candidate ranking | Automatic | Automatic | Automatic |
| Candidate selection | Highest credible candidate may be automatically selected and marked `INFERRED` | System proposes a candidate, **operator reviews/accepts or replaces it**, even if inferred | Requires physical edition corroboration (catalog/barcode/other reliable pressing evidence) or stops for review |
| Wrong pressing risk | Deliberately accepted by mode choice; never mislabel inference as physically verified | Explicitly accepted **per proposed release** by operator if selected without physical confirmation | Must not silently accept inferred pressing as physically verified |
| No credible release candidate | Verified original rip kept for review; no invented identity | Verified original rip kept for review | Verified original rip kept for review |
| Metadata tagging and copy | Future: automatically, after verification and valid source-based metadata; inferred attribution retained | Future: prepare non-destructive preview; **only after operator release approval** create tagged copy | Future: only after strict edition evidence and required reviews |
| Archive publication | Future: automatic only when Full Automatic explicitly enabled and all integrity gates pass | Future: **requires final operator approval before publication** | Future: requires strict physical edition gate, plus configured review level |
| Collection/index | Only after successful publication; preserve inference status | Only after approved publication; preserve inferred vs verified status | Only after approved publication; preserve verified status |

**Semi Automatic user journey:** **Go! → rip → verify → candidate(s) + evidence → [Approve this release / Choose another / Save for later] → tagged-copy preview → [Publish / Save for later]**. Release acceptance and archive publication are two separate approvals; avoid a single misleading “Approve everything” click by default. A reviewed inferred candidate stays `INFERRED, OPERATOR_ACCEPTED`, **not** `PHYSICALLY_VERIFIED`, unless independent physical evidence is actually recorded. A review action is idempotent, persisted against the exact job/MB release UUID, and blocked if the candidate or staged files have changed.

**Secure submodes remain configurable** as they are today (`on_ambiguity`, `before_archive`, `every_step`). Semi Automatic is a **separate top-level mode**, not a new spelling for the existing `Secure: Semi Automatic` column or `secure_review_level`. When the new mode ships, rename legacy UI wording to avoid confusion and preserve previously saved `secure` and `best_guess` values and existing jobs unchanged. Suggested stable setting: `identification_mode=semi_automatic`, with a dedicated persisted ledger state. It must never silently migrate an existing Secure job to a more permissive policy.

**Real acceptance example:** Essential Dance Traxx absent from MusicBrainz can legitimately produce an inferred *Ibiza Party* Disc ID candidate. Best Guess may accept that risk under its configured automation policy. Semi Automatic must **show the candidate for approval before use**. Secure pauses until physical edition evidence is sufficient. Never invent a missing release or claim the other album is the owned physical pressing.

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

## Second implementation increment — PR #64 Go! controller

Implemented: operator clicks Go!, a persistently snapshotted workflow is created **before** the cyanrip worker starts, successful extraction triggers verification automatically, a read-only next-step endpoint checks saved TOC against MusicBrainz after verification, and Best Guess can persist a *clearly inferred suggestion*; Secure returns a physical-review requirement. The existing recording and archive publishing APIs are NOT automatically invoked, and source evidence is never deleted. GUI polling is only a progress display; verified audio work runs server-side. A restart during extraction is surfaced as interrupted and deliberately not retried automatically.

Still to build: evidence-based physical edition resolver with persistent catalog/barcode, provider-limited restart-safe job scheduler, safe automatic metadata-copy and publish flow with per-mode validation, automatic post-publication catalog-index update and recoverable errors. See priorities below.

## First implementation increment — PR #63 persistent job ledger

A separate SQLite ledger can now **manually** register an existing saved staging rip, snapshot the user's selected currently supported Best Guess or Secure review policy, record immutable stage transitions and allow review deferral/resume. It reconciles its phase with actual staging verification evidence, without touching audio. This is persistence only: it does **not** create jobs at disc insertion, resume interrupted cyanrip, decide editions, generate tags, or publish archives. Real automatic scheduling requires the next milestones below.

## Current foundations

OSCAR already has optical-drive configuration, cyanrip staging and verification, multiple drives, read-only release candidate and physical-edition review, safely tagged staging copies, Classical v2, review/publish and archive integrity audit. Best Guess/Secure settings persist but are *not an executing workflow engine*. The local collection supports archive import, spreadsheet export, and read-only Discogs PAK identity/folders. PR #62 adds per-track indexing of archived FLAC Vorbis tags (contributors, Works, IDs, provenance) and explicit exact-MusicBrainz-release+catalog label backfill.

## Next engineering priorities in order

1. **Persistent per-job state machine and restart recovery.** Implement transitions DETECTED → IDENTIFIED_OR_DEFERRED → RIPPING → VERIFYING → METADATA_READY → TAGGED_COPY_VERIFIED → ARCHIVE_PREVIEW_READY → PUBLISHED → CATALOG_INDEXED. Add REVIEW_REQUIRED/FAILED. Journal each transition with immutable source IDs, hashes, error and retry state; persist the user's chosen mode at start. Never duplicate publication after restart.
2. **Evidence-scored release resolver.** Compare Disc ID, TOC, track count, catalog, barcode, MusicBrainz and physical Discogs candidate evidence. Best Guess may intentionally select a plausible *inferred* release; Secure never silently resolves ambiguity or unlinked physical editions. Preserve user-entered printed identifiers. Avoid MusicBrainz Work or Recording fabrication.
3. **Single Go! controller for verified rip through tags/publish.** Reuse currently-tested components through strict server-side validation rather than GUI button chaining; ask only on policy-required review states. Keep original rip/CUE/log and metadata copy, never auto-delete. Test idempotent retries, power interruptions and provider errors.
4. **Post-publication catalog and optional Discogs write.** Update local archive/track index from successful manifest; maintain separate physical-owned-copy records. Only confirmed Discogs additions, with per-instance duplicate protection, folder, media/sleeve condition and notes, independent of audio verification.
5. **Real hardware tests.** One pop release (Anastacia no-write regression), one genuinely unambiguous CD, classical Händel E 8512 (do NOT tag ES 99220), a box-set, a missing release (Essential Dance Traxx), multi-drive and restart. Confirm XLSX/ODS in Nextcloud Collabora/ONLYOFFICE. CI cannot substitute for real Unraid acceptance.

## Metadata and provenance contracts

One release can have multiple physical copies and multiple rip jobs. A publishing archive, collection item and Discogs instance are distinct. Album label backfill requires both matching MusicBrainz release UUID and printed catalog number, never extrapolation from another edition. Per-track Works/recording IDs/performer roles come only from archived FLAC comments, with source field. Unknown credit stays unknown. A soprano or violin performer is not automatically a soloist without an explicit solo credit. Divergent Work-name and Work-ID arrays must not be zipped incorrectly.

The route to 'CD erin → Go!' is the **next main project priority** after the track-index acceptance; do not spend subsequent cycles polishing collection UI without first establishing the persistent orchestration and safe release identity engine.
