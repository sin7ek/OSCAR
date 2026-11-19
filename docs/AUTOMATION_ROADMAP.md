# OSCAR — CD inserted → Go! automation roadmap

**State:** plans and implemented foundations as of November 19, 2026. This is *not* a completed automatic pipeline.

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
