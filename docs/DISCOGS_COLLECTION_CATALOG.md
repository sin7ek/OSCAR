# OSCAR — Discogs integration and local collection catalog (design proposal)

**Status:** Phase 1 implemented in PR #60 (local published-archive inventory, ODS/CSV export, read-only Discogs account/folders); collection writes, release search and complete owned-copy catalog remain planned. **Date:** 2026-11-19.  
**Related:** [PROJECT_STATUS.md](PROJECT_STATUS.md), [PROGRESS.md](PROGRESS.md), [ARCHITECTURE.md](ARCHITECTURE.md).  
**Sources:** https://www.discogs.com/developers/ ; https://support.discogs.com/hc/en-us/articles/360009334593-API-Terms-of-Use ; https://support.discogs.com/hc/en-us/articles/360007425393-How-Can-I-Add-Collection-Wantlist-Notes

## Goals

1. Supplement **MusicBrainz** (Disc ID, releases, recordings, works, artists, classical performance relationships) with **Discogs** (physical edition catalog/barcode/label/format, packaging and pressings). Never silently overwrite MusicBrainz works/recording IDs with Discogs guesses. Show evidence origin, IDs, fetched_at and discrepancies.
2. Offer **opt-in** Discogs collection management after successful, verified OSCAR archive publication: associate a *specific physical copy* with the correct Discogs release ID and optionally a Discogs collection folder, Media Condition, Sleeve Condition and Notes.
3. Create an **OSCAR-owned local catalog database** with a searchable/sortable web UI and reliable export to **OpenDocument Spreadsheet (.ods)** as first choice, **CSV** as interoperability fallback, and optional **.xlsx**. Users own their catalog independently of Discogs availability.
4. Respect Best Guess vs Secure identification settings; *Best Guess* selection is marked **INFERRED** (never physically verified). Discogs collection writes must not happen silently based on an inferred physical release without explicit opt-in and a clear warning.

## Proposed architecture

- SQLite with migrations and backup in persisted `/config` (do not reuse/alter rip or metadata worker stores unexpectedly), e.g. `/config/catalog.sqlite3`. Never place mutable catalog database within immutable `/archive`.
- Logical records: `physical_copies` (one row per owned item), `releases` (normalized MB release UUID, Discogs release ID, catalog number/barcode, user-sourced physical evidence), `rip_jobs` (existing staging ID), `archives` (immutable final path, manifest hash, verification status), `discogs_links` (folder ID, release ID, **instance ID**, last sync state and timestamp), `collection_notes` (user-owned local fields and provenance), `sync_events` (idempotent auditable operations/errors).
- Local copy ID is *not* a MusicBrainz release ID, Discogs release ID, or archive job ID. Multiple physical copies of the same release are distinct. Multiple rip jobs may reference the same physical copy; archive publication and collection sync are distinct transitions.
- Local fields such as purchase location/date/price, storage shelf, media/sleeve condition and custom private notes belong to the user. Avoid storing provider-restricted data longer than permitted by the Discogs API terms. Keep provider-derived transient data and independently entered facts distinct.
- Read-only Discogs discovery by catalog number, barcode, title, label, format and country, with candidate comparison; MusicBrainz remains authoritative for tag structures and classical work/recording relations. Discogs metadata is additional *physical edition evidence* and cannot prove the audio identity alone.
- Discogs collection sync: authenticated connection with minimal scope; list existing folders; allow selecting folder and user-entered condition/notes; search existing collection instances **before POST**, and retain returned **instance_id** to prevent accidental duplicates. Fetch current custom collection fields and map field IDs dynamically (do not assume fixed IDs). Preview before write; no delete/removal without separate explicit confirmation. Handle 429/rate-limit, token expiration, retries and partial success idempotently.
- After archive verification, display `Add this physical copy to Discogs?` with choices `Skip`, `Save as local task`, `Preview and add`. Default **Skip** until account connected and opt-in enabled; no automatic writes merely because Best Guess is selected. Media and sleeve condition are graded physical observations, never inferred from rip quality.
- The local catalog is authoritative for **OSCAR's own copy/job/archive history**. Discogs sync is optional and failure does not invalidate the verified rip, modify archival audio or block publishing.
- An identification-correction workflow must be possible without reripping: retain source evidence, make a new tagged copy from verified staging, append new release identification/sync history, and never silently overwrite an archived album.

## Spreadsheet and UI

- Search, sortable columns and filters: artist, title, composer, year, release format, label, catalog number, barcode, Discogs ID, MusicBrainz release UUID, copy/instance count, physical condition, folder, date acquired, archived/not archived, archive path, last integrity audit, source confidence, missing edition evidence.
- **ODS primary export** compatible with LibreOffice Calc; create a standards-compliant workbook containing `Collection`, `Archive Jobs`, `Release Evidence`, `Audits`, `Export Metadata`. Write sensible typed dates/numbers and stable explicit column headings; support sorting/filtering in Calc; UTF-8 CSV per sheet optional. XLSX optional for Excel compatibility.
- Export should be reproducible, reflect the catalog snapshot as of a documented UTC timestamp, and include *only user-authorized data*. Treat CSV and spreadsheet formula injection as security-sensitive: escape leading `=`, `+`, `-`, `@` in untrusted text; no executable spreadsheet formulas from external metadata. Never export API credentials/tokens or provider-restricted content without checking the license.
- Optional local backups are part of OSCAR retention policy, not a replacement for the original immutable FLAC archive and manifest.

## Discogs API legal and safety considerations

- Discogs API Terms distinguish **CC0 release metadata** (e.g. titles, dates, formats, tracklists, barcodes, credits) from **Restricted Data** (Discogs user collection data, marketplace, images). The API imposes retention/display restrictions and requires attribution. Before coding, validate the current terms, particularly restricted user-data storage/export; never assume all Discogs-derived fields can be permanently cached or redistributed.
- The application UI must show the required Discogs attribution and disclaimer next to Discogs-provided data. Preserve credentials in a secured configuration/secret store, never in Git, logs, export, or archive manifest.
- Design for rate limits and intermittent provider failure. Do not build a Discogs marketplace scraper.

## Proposed incremental implementation

1. **Local catalog schema + migrations + backup + read-only inventory** from existing valid OSCAR published manifests. Protect against symlinks/path traversal and never modify archived files. Add sortable/filterable UI and ODS/CSV export tests; keep privacy and spreadsheet injection controls.
2. **Discogs metadata candidate search** and read-only release evidence comparison. Respect per-provider source attribution and rights. Test ambiguous cases including Händel E 8512 and Citycat where Disc ID-only lookup fails.
3. **Discogs account connection** with explicit user authorization, read-only folder/custom-field/collection mapping and secure token storage.
4. **Confirmed write flow after verified publication** with choose folder, media/sleeve condition, notes, per-copy instance IDs, duplicate protection, audit log, error recovery and safe retry.
5. **Optional synchronization** and bounded automation. Secure and Best Guess policy remains separate from audio verification. Physical edition confidence must be labelled accurately and collection writes never imply independent AccurateRip/CTDB success.

## Acceptance criteria (future implementation PRs)

- Existing archived Anastacia release can be indexed locally without changes to archive contents; no fake Discogs ID assigned.
- E 8512 can appear as a Discogs candidate even without the matching MusicBrainz Disc ID attached; no automatically fabricated MB relationship.
- User can store an edition as unresolved and later correct tags from the original rip without a rerip.
- Two physical copies of same release remain distinct rows and Discogs instances. Retrying a successful collection sync does not add duplicates.
- ODS export opens in LibreOffice Calc, sorts/filters correctly, and round-trips Unicode names; CSV text cannot execute formulas; tokens/notes visibility respected.
- Provider rate-limit/auth errors never affect ripping or immutable archive publication.
- GitHub CI, actual Unraid hardware acceptance and user-visible sync results recorded separately in `PROJECT_STATUS.md`; progress percentages change only with evidence.

**Phase 1 implemented (PR #60):** SQLite catalog stored in `/config/catalog.sqlite3` (override `OSCAR_CATALOG_DB`), explicit idempotent import from OSCAR `published_verified` archive manifests, sortable and searchable local web inventory, ODS/CSV export, Discogs account/folder discovery using only `OSCAR_DISCOGS_PAK` at runtime (no token stored in SQLite or Git). Imported records describe *published archives*, not a complete inventory of separately owned physical copies. No provider-derived restricted data is exported.

**Rip attribution:** New reviewed metadata-tagging copies receive fixed Vorbis Comments `RIPPED_WITH=Ripped with OSCAR - Preserve Every Note.` and `RIPPER_URL=https://github.com/sin7ek/OSCAR`. The original extraction files and old published archives remain untouched. Classical v2 carries the attribution forward by retaining the original tags. Archive copying preserves the verified tagged FLAC bytes. This is an attribution tag, not proof of an independent AccurateRip/CTDB pass.

**Not yet implemented:** Discogs release search and automatic candidate comparison; authenticated Discogs collection writes; media/sleeve/folder/notes editing and remote sync; per-physical-copy ownership records; XLSX export; persistent audit history; unattended orchestration. The read-only Discogs folder lookup is optional and does not require OAuth Consumer Key/Secret when a Personal Access Token is configured.
