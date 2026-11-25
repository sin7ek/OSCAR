# Coordinated multidisc archive revision — implementation contract

**Status:** [#110](https://github.com/sin7ek/OSCAR/pull/110) merged the opt-in group LABEL Apply and explicit reconciliation. On Tower, the Boulez group changed 39 tracks on CDs 4 and 6, retaining the originals. The read-only verifier from [#112](https://github.com/sin7ek/OSCAR/pull/112) returned `Integrity PASS` for both revised discs. [#116](https://github.com/sin7ek/OSCAR/pull/116) records this result. Tower subsequently confirmed completed RELEASECOUNTRY revisions and read back DE on all 90 Boulez and 63 Mahler tracks. Full two-generation country Verify, interruption/reconciliation and coordinated GENRE Apply remain open. See the [Tower acceptance record](PROJECT_STATUS.md#tower-acceptance--2026-11-25).

## Combined metadata review

In **Collection → Archive metadata maintenance**, choose any published disc from the boxset under **Advanced · scan only one archive album**. **Preview coordinated multidisc metadata update (read-only)** lists the current value, proposed value and approval status per disc for `LABEL`, `GENRE` and `RELEASECOUNTRY`. Run the Collection additions/changes scans and approve the desired proposals on each affected disc. A field with approvals is eligible for Apply only when every present disc is already correct or explicitly approved for that field. A field without any approvals can be reviewed separately later.

The same Apply can write multiple approved fields per CD, with one retained generation per affected disc. The country is written as the MusicBrainz release-area code to the FLAC Vorbis tag. Recovery and read-only Verify use the journal's approved changes. Verify can still check a prior revision using the retained generation from its successor. Legacy single-field journals remain supported.

## Problem and scope

An archived MusicBrainz release may have only some physical CDs published. The initial Boulez preview showed discs 4 and 6 of 6, both with approved `LABEL=Deutsche Grammophon` proposals. The later complete preview had six discs and only 4 and 6 required changes. The affected set **must be discovered dynamically** for every preview and inside the locked apply. A fingerprint obtained with two discs must become stale when a fifth disc is indexed.

## Strict transaction boundaries

- **Only operator-approved values** on already published, individually verified physical CD leaves; no missing-disc fabrication and no use of staging.
- Dedicated `OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS=1` opt-in, independent of single-disc revisions and history cleanup; authenticated preview and apply with typed approval.
- One release-level plan and stable digest binds release UUID, every indexed leaf path, disc number/total, original publish ID, original manifest hash, proposal fingerprints, target values, and missing-disc set. Refuse conflicting/unknown additional accepted changes.
- Inside one shared `.oscar-publish.lock`, rescan all indexed discs and check identical fingerprint. Validate all original FLAC SHA-256, Disc ID/medium/recording identity against fresh MusicBrainz, CUE and source-evidence hashes.
- Fully prepare **every** new tagged leaf in isolated temporary directories *before moving one existing archive*. Independently check approved Vorbis values, preserved STREAMINFO audio MD5, full decode with `flac -t`, new SHA-256, and non-audio evidence. Preserve original filenames/CUE bytes; no artificial evidence or guessed labels.
- Create a **durable release-level journal** in SQLite before first directory rename. Record one per-disc operation in deterministic disc order with old path, temp path, hidden original path, original/new publish IDs and digests, and progress.
- Publication on Unraid is a **coordinated recoverable sequence**, not a real multi-directory filesystem atomic transaction. During interrupted promotion, leave a `prepared`/recovery-needed journal; never call it an all-or-none commit or hide partially published states.
- Each disc's original generation must be moved, byte-identically, into its exact operation-specific path under `.oscar-archive-versions`. Never overwrite paths; never remove them automatically.
- After **all** new leaves exist and are independently verified, atomically commit all Collection rebindings, sourced label and genre projections, precise `applied` proposal statuses and decision events in one SQLite transaction; then mark the group completed.
- Operator-invoked reconciliation, under the same lock, must verify all original and new generations, refuse ambiguous states, and either complete a fully verified publication or safely restore all original paths where possible. No destructive blind rollback.
- Do not reuse the single-disc `archive_revision.apply` on one boxset leaf. No Clean of incomplete/coordinated operations.

## Gates and tests

1. Two-of-six preview remains read-only; five-of-six scenario correctly discovers discs 1,2,3,4,6; 5 missing.
2. Preview fingerprint changes on newly published disc, changed FLAC/manifest/approval, or changed MusicBrainz evidence.
3. No apply without independent boxset opt-in, current preview, and explicit operator approval.
4. Inject failures while preparing, after journaling, after each original move, after each promotion, and before SQLite commit. Validate original restoration or explicit resumable ambiguity, never silently report success.
5. Ensure original FLAC hashes and extraction evidence are intact, all new FLAC streams decode, and Collection has no duplicate rows.
6. Validate real Unraid read-only preview first; then user-approved real migration. CI and Docker build are necessary but not live acceptance.
7. Only after that: separate sacrificial-archive Verify/Clean/Verify & Clean tests with external backup.

## Follow-on work

Independent CTDB verification in staging and read-only post-publication review (not mere TOCID lookup), preserving separate AccurateRip/CTDB confidence and avoiding automatic submission or repair. Then artwork acquisition across exact release sources and improved `SOURCES.txt`/cyanrip provenance output.

## Safety

Never mutate, re-encode, rename or delete original Unraid archive audio without explicit operator approval. This document specifies behavior; it is not evidence that multi-disc Apply is implemented.


## LABEL implementation notes (PR #110)

- Module: `src/oscar/archive_revision_boxset_apply.py`. Uses the existing archive lock and single-disc verified FLAC copy/retag helper, but does **not** run single-disc Apply.
- Enable using the distinct `OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS=1` setting **only in a controlled test environment initially**. Existing single-disc and cleanup flags are separate.
- REST: `boxset-preview`, `boxset-apply`, `boxset-workers/{task_id}`, `boxset-operations`, and `boxset-reconcile`, all authenticated.
- UI: preview presents Apply only for all-present-disc-approved groups when explicitly enabled, and has separate history/recovery controls.
- The group DB transaction is atomic. The cross-directory filesystem rename sequence **is not atomic**; interrupted groups are reported as `prepared` and must be reconciled. It may temporarily expose mixed publication generations.
- Candidate copies are verified before any original move. All retained originals remain intact after a successful operation. Reconciliation must verify original+new and audio STREAMINFO MD5 identity before committing Collection.
- Original #110 implementation migrated accepted release-scope `LABEL` only. Every present disc is checked; already-correct discs remain byte-identical and unversioned, while each changed disc needs exactly one accepted label proposal. No other metadata fields, no album rename, no automated rollback or cleanup. These restrictions intentionally fail closed.
- Worker progress state is in-memory; the durable group journal survives restarts. If worker status is lost, inspect group history.
- Tests presently include synthetic fake-FLAC journal transitions for partial failures and stale plans. They are **not a substitute for real-FLAC end-to-end tests**.
- **Remaining acceptance:** inject an interruption with real FLACs on a sacrificial Unraid/FUSE fixture and verify journal reconciliation and both generations. Archive originals must remain retained.

- A newly ripped CD already containing the exact reviewed `LABEL` is included in the group fingerprint but is not rewritten, moved or backed up by this metadata-only migration.
