## Read-only coordinated label preview for incomplete multidisc releases (2026-11-20; PR #108 merged (GitHub Tests and Docker build green, real Unraid preview pending))

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

## Initial approved archive migration implementation (2026-11-20 — PR #95 merged; Unraid acceptance pending)

An opt-in, **staging-independent** Archive Metadata Migration v1 is now implemented for **one single-CD archive leaf per operation**. The Collection UI provides **Preview approved archive migration for selected album** (read-only) and **Apply approved archive revision** with explicit confirmation. Actual writes are disabled unless the operator sets `OSCAR_ENABLE_ARCHIVE_REVISIONS=1` in the Portainer environment. No automatic migration is triggered by Accept, scan or container startup.

### Migration contract

1. Read the currently indexed published original archive, validate all FLAC SHA-256 hashes and their archived MusicBrainz release/Disc ID/recording identities, the published original CUE hash and ExtractionEvidence hashes. Do not load staging.
2. Collect only decisions still at `accepted` for that exact original archive revision, and re-check each approved field against current exact MusicBrainz CD medium data before creating a stable review fingerprint.
3. Preview source/target directory and every accepted metadata field. `CATALOGNUMBER` changes **must** update the album folder naming, e.g. `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]` → `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`. An approved `DATE` adds or replaces the folder year and updates the Collection year in the same revision. A year-only MusicBrainz date stays year-only in the tag. An approved `RELEASECOUNTRY` updates the country code on all tracks.
4. On explicit operator confirmation, duplicate the original entire album into an isolated temporary sibling directory. Modify **only approved FLAC Vorbis fields** (`CATALOGNUMBER`, `LABEL`, `BARCODE`, `DATE`, `RELEASECOUNTRY`, `TITLE`, `ARTIST`, `GENRE`), preserve audio STREAMINFO MD5, verify decoded audio with `flac -t`, read the actual tags back and recompute each whole-file SHA-256. Re-validate source CUE/extraction evidence and preserve every other original file.
5. Create a new `published_verified` manifest with a **new** publish ID, the new FLAC hashes, an explicit parent publish ID/parent manifest SHA-256 and list of approved proposal fingerprints. The original publication manifest is never edited.
6. Under the existing exclusive cross-process archive publication lock, write a durable SQLite migration journal, move the original album **without changing its contents** into `/archive/.oscar-archive-versions/<old-publish-id>/<operation-id>`, and atomically promote the fully verified new album to the reviewed destination. Never overwrite a pre-existing destination.
7. In a transactional SQLite update, rebind the existing Collection archive row to the new path, set reviewed catalog number, preserve nonblank manually curated Collection labels, mark only those exact approved proposals as `applied` and append immutable `applied` decision events. Subsequent Collection imports exclude `.oscar-archive-versions` and must not recreate retired historical paths. Retained original versions are never deleted.
8. If promotion fails before publication, attempt no-overwrite restoration of the original directory. If promotion succeeds but the DB transaction is interrupted, the durable journal remains `prepared`. The operator can inspect **View archive revision history and recovery status** and invoke **Reconcile interrupted revision** to verify both generations and complete the journal/database transition safely. No in-place retagging or blind cleanup.

### Initial v1 limits and Unraid acceptance gate

- **No boxset/multi-disc migrations yet.** A release folder shared by multiple discs must be revised as a coordinated unit; v1 explicitly refuses partial boxset migration.
- Album track filenames and CUE references remain as originally reviewed; title tag changes do not silently rename track files.
- Source version history consumes extra disk space; keep archive root backup and sufficient free capacity. Temporary crash artifacts are retained for review instead of being silently deleted.
- The worker's in-memory live progress does not survive container restarts, but the durable SQLite journal does; recovery is explicitly operator-initiated.
- This opt-in code is **not** accepted on real Unraid until a dry-run preview on Carmen Gomes and Anastacia, an explicit reviewed application, verification of new path, collection index, intact original history, rescanning with zero repeated proposals and a recovery/rollback inspection. Do not set the opt-in flag on production before reviewing the preview and destination paths.
- Priorities before expanding scope: transactional crash-recovery stress testing on Unraid shfs, broader multivalue tags, works/recordings, boxset-wide coordinated migration, safe retention policies.
- Passing offline Python tests with controlled fake FLAC objects and a Docker build is necessary but **not sufficient** evidence for real audio-integrity/recovery behavior.

---

## Whole-archive scan implementation (2026-11-20; PR pending validation)

The Collection UI now defaults to scanning **all OSCAR-shaped published archive manifest leaves directly from the configured archive root**, including legitimate releases not yet indexed in Collection, with one-album troubleshooting under Advanced. Hidden retained history and staging leftovers are excluded. Malformed candidate manifests are handed to the individual scanner and reported as failures instead of silently disappearing. The server starts a bounded (10,000-leaf maximum) single background scanner job and exposes progress, source/verification failures, already-decided proposals and completion. Each leaf uses the existing exact release/Disc ID and SHA-256 checks. A failed album does not abort the rest. Progress is ephemeral to the worker process; individual proposal decisions persist in SQLite. Collection import is not required for whole-archive scans, but a published album must be indexed before an approved archive migration can be applied. **No change is automatically applied to archived FLACs.**

The old label enrichment button stays in Advanced until future approved migration can reflect label tags into the local catalog. MusicBrainz release ID is already present as `MUSICBRAINZ_ALBUMID` in FLAC and `release_id` in the immutable manifest. Discogs PAT renamed to `OSCAR_DISCOGS_PAT`. Code/CI and real hardware acceptance pending.

---

## Decision history UI: current versus historical actions (2026-11-20)

Real Unraid review showed `ignored → reopened → accepted` for Carmen Gomes' CFMusic label, while the old `ignored` history row still offered **Reopen decision**. History must preserve every event, but only the **latest event for a proposal whose current SQLite status is accepted or ignored** should offer an action. Old ignored or accepted events are read-only historical evidence, never a new actionable state. The API supplies `current_status` and `latest_event` so the client can enforce this presentation rule; the server independently validates current state and external evidence. UI correction pending release/Unraid test. Archive remains untouched.

---

# Archive-first metadata lifecycle — design decision (2026-11-20)

**Status:** design approved; read-only archive scan + durable decision ledger merged via PR #89 after passing GitHub Tests and Docker CI. Unraid acceptance pending. Archive update/migration remains unimplemented. Archive update/migration remains unimplemented. This design is not an authorization to rewrite existing archive files.

## Implementation milestone — Archive Metadata Scanner v1 (2026-11-20)

**Implemented and merged in PR #89 (Unraid acceptance pending):** Collection buttons **Scan archive for metadata additions** and **Scan archive for metadata changes** on a selected published album; source-of-truth archive leaf and SHA-256 manifest validation, FLAC tag readback, exact saved release/Disc ID/CD-medium MusicBrainz lookup, normalized per-field proposals, durable SQLite Accept/Ignore ledger, and decision history. The scan uses only published archiving evidence and `OSCAR_CATALOG_DB`; it never requires staging. Accepted means **approved for a future separately gated migration**, not applied; ignored exact proposals are suppressed on repeat scans while new values receive new fingerprints.

**Initial scanner scope (superseded by full-root scanning):** one Collection-selected album per scan, catalog number, label and barcode additions, track TITLE/ARTIST changes. Deliberately block ambiguous media/recording identities, invalid hashes and provider omissions (no deletion proposals). No actual archive mutation or migration implementation, no artwork and no recording/work relationship edits yet. The GUI intentionally does not offer an Apply operation. Early deployments may have valid older archives whose physical Disc ID or recording tags are missing: scanner refuses these rather than guessing their identities. Broader archive layouts and legacy metadata sources will be addressed after smoke tests.

**Acceptance:** GitHub Tests + Docker build must be green before merge. On Unraid import the published Carmen Gomes Inc. archive into Collection, select it, run Additions; expect catalog `CGi2010` as pending if absent in archived FLACs, along with any other source-backed missing label. Ignore, rerun scan and confirm suppression persists through a restart; if provider later changes a value, test a distinct proposal. Do not delete staging just to test the feature; simulated absent staging is covered by automated tests. Archive migration remains a separate future PR.

---

## Principle

**Staging is temporary; the verified published archive must remain independently maintainable after staging has been removed.** An OSCAR archive must carry sufficient provenance to identify its original physical CD, its accepted MusicBrainz release and its verified original audio. Ongoing metadata operations must read only the archive and its durable catalog/evidence, never assume that the old `oscar-<job>` staging directory or `metadata-copy-<id>` still exists.

Historical extraction logs/TOC/CUE, the originally published manifest and audio-integrity evidence must remain available in the archive as immutable proof. Avoid equating a MusicBrainz Disc ID match or later metadata corrections with confirmed physical pressing identity.

## Proposed Collection functions

### Scan archive for metadata additions
- Find currently absent, externally sourced candidate fields such as release catalog number, barcode, label, credits, recorded performers, composer/work/recording relationships, and artwork, when supported by an explicitly validated release identity.
- Distinguish a truly absent value from a user-curated blank and an edition whose evidence is unresolved.
- Never invent an identifier or auto-fill from a different pressing. A new addition is a proposal, not an archive write.

### Scan archive for metadata changes
- Compare archived, reviewed metadata with newly retrieved release and track metadata (MusicBrainz first, additional verified providers later).
- Show changed values, removals, additions to multi-valued tags, version/relationship changes and track-by-track evidence. Treat release/recording/work identity changes and any removal as high-review-risk.
- Neither scan changes FLAC tags, file names, CUE, manifests, Collection SQLite, original evidence, or publication history.
- Metadata comparison should use MusicBrainz release/medium/recording identity and saved archive evidence, **not** just album title/artist fuzzy similarity.

## Durable change proposal / decision ledger

Persist in a separate SQLite catalog-compatible schema (or dedicated DB), independently of staging:
- stable archive/item identity (publish ID + archive manifest lineage, release UUID, disc position and optionally track/recording ID), source provider and source object UUID;
- field path and scope (release/medium/track/recording/work), canonicalized archived value and proposed value, content hashes, source observation timestamp, complete provider provenance and current archive revision/hash;
- stable semantic change fingerprint over item identity + provider + field + canonical before/after values + relevant identities; not over just the timestamp, transient HTTP response ordering or a release-wide scan timestamp;
- observed status, **pending / accepted / ignored / superseded / blocked / applied / failed**, user acknowledgement time and non-sensitive justification where provided;
- immutable decision-event history and reference to the exact archive revision at which a change was applied;
- persistent scan cursor/retry state and failures recorded separately. A failed or unavailable lookup must **never** be represented as a deletion or an approved change.

### Suppression and rediscovery contract

- `Ignore` suppresses that **exact semantic proposal** across subsequent scans; `Accept` also prevents repeating the same operation once applied. Keep ignored decisions inspectable and **reversible via Reopen decision**. The earlier `ignored` or `accepted` event is never deleted; a `reopened` event restores `pending` only after verifying the published archive revision and the still-current MusicBrainz value.
- If the source proposes a different value for the same item/field, or if the underlying archive value/revision changes, reevaluate and offer a new proposal as appropriate. A source fetch that is semantically identical must not reappear because its timestamp or serialization changed.
- For multi-value tags, canonicalize equivalent order only when the field is semantically unordered; retain meaningful sequence for tracklists and credits.
- When a newer value supersedes an older pending/ignored proposal, preserve historical decisions and link the new proposal to the former one, not overwrite the past.
- A previously ignored value returning after an intervening different revision is a new decision context when the archive/source lineage has materially changed.
- Accepted proposal and successfully applied proposal are different states; failures should not become 'applied'.

## Accept / Ignore UI

Display each change with archived value, source value, source URL/UUID, evidence strength, affected track count, location, risk level and why it is proposed. Provide explicit `Accept change` and `Ignore change` choices, batch decisions only where safely compatible, and decision-history view.

Approval should be bound to the precise, freshly verified proposed change and archive revision (optimistic concurrency). No silent global accept and no automatic remote MusicBrainz editing. Stronger confirmation and separate review for altered release identity, changed track counts/order, removed tags or audio-relevant CUE information.

## Applying an accepted archive change (separate future phase)

- Operate solely on an archive-backed source; never require historical staging.
- Read/validate the immutable archived origin manifest, original CUE/TOC and verified FLAC integrity; record current hashes before any operation.
- Preserve original audio bytes/FLAC STREAMINFO audio MD5 and verify decoded FLACs; note that metadata-only retagging **does** change whole-file FLAC SHA-256, so store both old and new hashes with chain of provenance, not a false assertion that file hashes stay the same.
- Create a **new version** in a temporary sibling directory/immutable snapshot, using copy-on-write/atomic no-overwrite promotion where supported. Do not directly retag in-place. Leave original archived generation recoverable; no automatic deletion or merging away historical evidence.
- Generate a new manifest revision, parent/child relation and explicit change log. Preserve all immutable extraction evidence and old published manifests; never forge their original file hashes.
- Check the whole new album/boxset leaf (including CUE references, disc indices, cover choices, track count, all files, paths and metadata readback) and reject collisions/path traversal/symlinks.
- Make Collection SQLite changes transactionally only after the new on-disk generation is durably verified. Handle crash-before/after promotion through a recovery record; never claim success just because the worker returned.
- **Required on applying an accepted physical-release CATALOGNUMBER change:** include a reviewed archive-folder naming migration, e.g. `/archive/Carmen Gomes Inc/Desire (2010) [fa89edc1]` → `/archive/Carmen Gomes Inc/[CGi2010] Desire (2010) [fa89edc1]`. This must be part of the separately approved versioned archive migration, never an automatic side effect of Scan or Accept. Refuse destination collisions, verify old/new audio and manifest hashes, retain the original archive generation for rollback, and transactionally update every Collection archive-path/index reference only once the new generation is confirmed. No stale Collection links, lost original publication evidence, or manual folder renames.
- Require a verified rollback path and separate operator consent before any retirement/deletion of old versions. Keep original source-integrity evidence throughout.

## Robustness / boundaries

- Do not depend on MusicBrainz always being online. Apply existing rate limiter, response-size caps, verified endpoints and retries; retain last known good external observation with timestamps.
- Preserve operator-curated Collection columns and local values. Distinguish source-proposed updates from human edits. Never let a catalog import silently overwrite manual curation.
- Make archive scanning incremental and bounded, with on-demand album or whole Collection scans; no continuous mandatory provider polling.
- Avoid mass edits when provider responses are incomplete or ambiguous. No destructive archive cleanup without a separately audited retention policy.

## Real-world decision correction — Carmen Gomes *Desire* (2026-11-20)

The operator accepted `CATALOGNUMBER = CGi2010` at 2026-11-20T20:46:53.576873+00:00 and accidentally ignored `LABEL = CFMusic` at 2026-11-20T20:49:27.220609+00:00. The accepted catalog proposal is still **approval only**, not a tag or archive-folder update. `Reopen decision` should make the label proposal pending again, without deleting the historical ignore event, so it can then be accepted. No archive file changes occur. Verify this on real Unraid after the new release is deployed.

---

## First acceptance fixture

Carmen Gomes Inc. *Desire*, accepted release `fa89edc1-32f9-4290-8788-bbac2e366a46`, published archive ID `3908eef79f114450b0a7eb76bec44926`, corrected MusicBrainz catalog `CGi2010`, and newer staging-copy ID `cd2959e6cc2b4c4ab6fafb590808b2db`. **Acceptance must also succeed with staging directory intentionally unavailable in the test fixture.** Expected detection is an addition of `CGi2010`, exactly one durable proposal/decision across repeated identical scans, and a new proposal if the external value changes again. No new archive writes during scan or ignore. Applying changes is a separate later PR with explicit end-to-end validation.

## Implementation order

1. Read-only archive-derived metadata snapshot + consistency/hash/identity validation and per-field normalized diff against provider (no staging dependence).
2. Durable change-proposal and user-decision ledger with stable fingerprint suppression and new-revision rediscovery.
3. Collection UI for both scan modes, per-proposal evidence, Accept/Ignore and history; test rejection, repeated scans, changed values and crash/restart persistence.
4. Separate, strictly gated archive revision publisher with atomic promotion, hash/audit chain and Collection transaction/recovery.
5. Only after these are proven on Unraid, consider opt-in recurring scans and long-term staging cleanup.

GitHub Tests + Docker build must pass on each feature PR before merge to main, followed by operator Unraid tests. Update `PROJECT_STATUS.md`, `PROGRESS.md` and this document at each implementation milestone. No project's progress percentages are changed for a design alone.
