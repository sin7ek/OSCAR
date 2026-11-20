## Whole-archive scan implementation (2026-11-20; PR pending validation)

The Collection UI now defaults to scanning **all indexed published archive leaves**, with one-album troubleshooting under Advanced. The server starts a bounded (10,000-leaf maximum) single background scanner job and exposes progress, source/verification failures, already-decided proposals and completion. Each leaf uses the existing exact release/Disc ID and SHA-256 checks. A failed album does not abort the rest. Progress is ephemeral to the worker process; individual proposal decisions persist in SQLite. Import published archive records before scanning if Collection is empty. **No change is automatically applied to archived FLACs.**

The old label enrichment button stays in Advanced until future approved migration can reflect label tags into the local catalog. MusicBrainz release ID is already present as `MUSICBRAINZ_ALBUMID` in FLAC and `release_id` in the immutable manifest. Discogs PAT renamed to `OSCAR_DISCOGS_PAT`. Code/CI and real hardware acceptance pending.

---

## Decision history UI: current versus historical actions (2026-11-20)

Real Unraid review showed `ignored → reopened → accepted` for Carmen Gomes' CFMusic label, while the old `ignored` history row still offered **Reopen decision**. History must preserve every event, but only the **latest event for a proposal whose current SQLite status is accepted or ignored** should offer an action. Old ignored or accepted events are read-only historical evidence, never a new actionable state. The API supplies `current_status` and `latest_event` so the client can enforce this presentation rule; the server independently validates current state and external evidence. UI correction pending release/Unraid test. Archive remains untouched.

---

# Archive-first metadata lifecycle — design decision (2026-11-20)

**Status:** design approved; read-only archive scan + durable decision ledger merged via PR #89 after passing GitHub Tests and Docker CI. Unraid acceptance pending. Archive update/migration remains unimplemented. Archive update/migration remains unimplemented. This design is not an authorization to rewrite existing archive files.

## Implementation milestone — Archive Metadata Scanner v1 (2026-11-20)

**Implemented and merged in PR #89 (Unraid acceptance pending):** Collection buttons **Scan archive for metadata additions** and **Scan archive for metadata changes** on a selected published album; source-of-truth archive leaf and SHA-256 manifest validation, FLAC tag readback, exact saved release/Disc ID/CD-medium MusicBrainz lookup, normalized per-field proposals, durable SQLite Accept/Ignore ledger, and decision history. The scan uses only published archiving evidence and `OSCAR_CATALOG_DB`; it never requires staging. Accepted means **approved for a future separately gated migration**, not applied; ignored exact proposals are suppressed on repeat scans while new values receive new fingerprints.

**Initial scope:** one Collection-selected album per scan (not a bulk recursive scan), catalog number, label and barcode additions, track TITLE/ARTIST changes. Deliberately block ambiguous media/recording identities, invalid hashes and provider omissions (no deletion proposals). No actual archive mutation or migration implementation, no artwork and no recording/work relationship edits yet. The GUI intentionally does not offer an Apply operation. Early deployments may have valid older archives whose physical Disc ID or recording tags are missing: scanner refuses these rather than guessing their identities. Broader archive layouts and legacy metadata sources will be addressed after smoke tests.

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
