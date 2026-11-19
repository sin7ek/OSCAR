# OSCAR — CD inserted → Go! automation roadmap

**State:** plans and implemented foundations as of November 19, 2026. This is *not* a completed automatic pipeline.

## One audio pipeline; two identification policies

Audio checks are equally strict in every mode: verified staging, FLAC decode, SHA-256, CUE consistency, original extraction evidence, and preserved source. A MusicBrainz Disc ID by itself never proves a pressing.

| Step | Best Guess (Full Automatic intention) | Secure: Semi Automatic | Secure: Review before Archive | Secure: Full Manual |
|---|---|---|---|---|
| Disc detection and candidate search | Automatic | Automatic | Automatic | User starts |
| Physical edition | Plausible highest-evidence candidate, marked INFERRED | Corroborated edition evidence or pause | Same plus final preview review | Explicit review |
| Ambiguity, missing metadata | Preserve verified rip and defer; never invent IDs | Ask catalog/barcode or defer | Same | Same |
| Audio integrity verification | Mandatory | Mandatory | Mandatory | Mandatory |
| Tag/classical Work mapping | Only supported source relationships | Same | Same | Same |
| Publishing | User-enabled automation after independent checks | Only after evidence gate | Explicit approval | Explicit approval |
| Local catalog | Update after verified publish | Same | Same | Same |
| Discogs collection write | Separate opt-in per physical copy | Same | Same | Same |

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
