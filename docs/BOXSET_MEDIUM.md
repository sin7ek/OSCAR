# Exact disc identification within classical boxsets

## Problem
A MusicBrainz Disc ID may return a **multi-disc release**. The original OSCAR display showed only its release title and did not identify which physical disc was inserted.

## Implementation
- OSCAR re-reads the inserted disc's standard TOC and Disc ID.
- For a selected release, it fetches the MusicBrainz release with `recordings+artist-credits+discids`.
- It finds the medium explicitly containing this Disc ID and validates the medium track count against the inserted disc.
- It displays `Disc X of Y`, optional medium title, track titles and credited artists plus recording MBIDs in the JSON response.
- Exact matches are **candidates requiring physical-edition review**; matching track count alone does not identify a disc.
- Source audio, Archive and local tags are never modified.

## Real reference case
The user's Optiarc AD-7200S produced Disc ID `sT6cTPp0_qZRfvu1jHQ8VBNx.X4-`, 32 tracks and lead-out sector 261408. MusicBrainz associates it with release [Boulez Conducts Stravinsky](https://musicbrainz.org/release/423f636d-742d-47b0-9ba2-51515a6fdfd2), a six-CD Deutsche Grammophon box. The medium inspector should identify the inserted disc as **CD 6: Songs** if this Disc ID is attached to that release medium.

## Verification
1. Update to the latest GHCR image after main-branch publishing passes.
2. Keep existing settings, `OSCAR_ENABLE_MEDIA_PROBE=1`, `OSCAR_ENABLE_TOC_PROBE=1`, `OSCAR_ENABLE_MUSICBRAINZ=1`, `/dev/sr2` and GID 19.
3. In OSCAR click **Check inserted discs**, **Read TOC and MusicBrainz ID**, and **Find release candidates on MusicBrainz**.
4. Click **Inspect disc & tracklist** next to the Boulez release.
5. Check `Disc 6 of 6`, 32 tracks, titles and physical-edition details. Any mismatch should remain review-only.

## Intentionally postponed
- Work and movement hierarchies, composer/conductor/performer relationships and recording dates; artist credits alone are **not** sufficient for classical metadata.
- Persistence of a multi-disc ingest job and boxset completion.
- Rip engine, external verification, publication and cleanup.
- Automatic approval of an edition or inference of INDEX 00 / HTOA from standard TOC.

API: `GET /api/release-medium?stable_id=<device-id>&release_id=<release-mbid>`.
