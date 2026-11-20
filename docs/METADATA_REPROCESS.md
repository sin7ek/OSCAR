# Safe MusicBrainz metadata refresh and reprocessing

## Motivation / real Unraid evidence

Carmen Gomes Inc. — *Desire* was published with verified original rip staging, a separately verified tagged copy, and a durable `ARCHIVE_PUBLISHED` record. After publication, the operator corrected the catalog number on MusicBrainz. The archive name and old tags reflect the previously saved metadata; a later MusicBrainz edit must **not** silently rewrite them.

This functionality supports **new metadata comparison and a separate tagged staging copy**, not archive replacement.

## Operator workflow

1. In Go! load an **existing accepted Semi Automatic** job (including `ARCHIVE_PUBLISHED`). For Carmen Gomes the historical job is `b68488f667cc492d8dd94f90717cdb28`, accepted release `fa89edc1-32f9-4290-8788-bbac2e366a46`.
2. Choose **Refresh metadata from MusicBrainz (compare, no writes)**. The authenticated endpoint `POST /api/go/jobs/{job_id}/musicbrainz/metadata-refresh` uses the saved accepted release UUID and the original verified rip. It verifies the original tagged copy via read-back and compares album identity, labels, catalog numbers and individual planned FLAC tags.
3. If MusicBrainz has the updated number, the comparison should show **old catalog: missing** and **new catalog: [confirmed value]**. This is an external lookup and is not assumed to propagate instantaneously. Verify the printed catalog number on the physical CD/booklet; a MusicBrainz match alone does not prove pressing.
4. Only when differences exist, click **Create new reviewed staging copy (no archive replacement)** and explicitly confirm. `POST /api/go/jobs/{job_id}/musicbrainz/reprocess-copy` checks the fingerprint against a **fresh** preview and invokes the existing lossless tag-copy pipeline with a new ID. Use **Check new staging copy** to see completion and FLAC tag/hash read-back status.
5. Keep the original rip, the original metadata copy, the archived published copy and the historical Go ledger **unchanged**. New metadata copy is a separate experimental staging artifact; there is intentionally **no UI action to promote/replace the published archive** in this PR.

## Safety and failure behavior

- No rerip; no source deletion or mutation; no renaming an existing archive path; no SQLite Collection rewrite; no new archival publication.
- Reject missing or changed original copy evidence, incomplete source verification, unmatched/replaced accepted release, unsafe symlinks, changed track ordering, mismatching fingerprints and absent required operator confirmation.
- Compare only the previously operator-accepted release, never silently switch to another MusicBrainz edition.
- MusicBrainz request uses existing rate limiter/retry and remains read-only. User secrets never appear in logs, response or GitHub.
- The previously accepted identification status `INFERRED_OPERATOR_ACCEPTED` does not become physical-pressing verification.
- After app/container restart, completed isolated staging copies remain inspectable via the existing copy status/inspect endpoints; in-progress interrupted copies are not automatically retried.
- Repeat explicit staging requests can create a different independently identified copy; do not repeat unnecessary work. No automatic rerun.

## Acceptance criteria

All GitHub Python tests and the PR Docker build must pass before merge to `main`. Then deploy to Unraid and confirm the new MusicBrainz catalog metadata is actually present in the comparison. Test an isolated new copy only after validating physical packaging. Verify tagged-copy integrity; demonstrate the old archive manifest, existing published folder, current Collection record and source staging are untouched.

**Future, separate PR:** an opt-in, audited archive replacement/migration plan requiring independent old/new hash checks, verified rollback, catalog reconciliation and explicit operator approval; not implemented here. The MusicBrainz OAuth collection integration is an unrelated next phase.
