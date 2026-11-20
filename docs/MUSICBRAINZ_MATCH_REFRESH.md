# MusicBrainz match refresh — existing accepted Go! jobs

## Scope

A strictly read-only, operator-triggered refresh for an **already accepted Semi Automatic** physical CD job. In Go!, enter the saved job ID and advance the workflow to display **Refresh MusicBrainz match (read-only)**. The button performs an authenticated POST to:

`/api/go/jobs/{job_id}/musicbrainz/refresh-match`

The endpoint re-reads saved `plan.json`, staging state and completed verification evidence, then fetches the **currently accepted MusicBrainz release** using the existing release-medium lookup and shared MusicBrainz rate limiter.

## Results

- `disc_id_now_attached`: a single CD medium on that exact release now contains the original saved Disc ID and its track count matches.
- `disc_id_not_attached`: the accepted release does not have the saved Disc ID attached.
- `ambiguous_or_incompatible`: the response cannot support a unique, compatible CD-medium match.

The result is returned only to the requesting UI; it is **not persisted** as new approval. The job retains `INFERRED_OPERATOR_ACCEPTED`, and `physical_edition_verified=false` always. A matching Disc ID is not proof of the exact physical pressing. Do not automatically regenerate tags, move/copy/publish audio, or change the accepted release.

The action refuses jobs that lack an accepted Semi Automatic release, disabled MusicBrainz lookup, unsafe or inconsistent saved physical TOC/Disc ID, or complete track-by-track verification. Network failures return an error, never a positive match. The action never accesses a live optical drive.

## Regression evidence and next checks

Automated checks cover an attached medium, missing/ambiguous Disc ID, bad physical evidence, incomplete verification, UI presence and authentication. GitHub tests and Docker CI must pass **before merging**. A successful CI run is **not** a hardware/Unraid validation.

On Unraid, reopen the historical Carmen Gomes Inc. *Desire* job `b68488f667cc492d8dd94f90717cdb28` (release `fa89edc1-32f9-4290-8788-bbac2e366a46`, Disc ID `VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-`). Verify that MusicBrainz currently reports the Disc ID on exactly one compatible CD medium. Confirm the historical provenance, archive contents and source audio are unchanged. If the job cannot be refreshed, inspect the saved TOC and verification evidence rather than inventing it.

Follow-on work: factual English MusicBrainz edit-note templates, then server-side MusicBrainz OAuth read-only collection access and collection comparison.
