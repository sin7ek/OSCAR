# OSCAR genre discovery and library sections (first safe implementation)

OSCAR uses genres to classify **Collection views**.

## v1 (PR feature)

- Existing Collection index now stores `genres` (curated FLAC `GENRE` values) and `library_section` (`Classical`, `Popular`, `Unclassified`).
- Explicit, reviewed `manifest.profile=classical` is sufficient to place an album in Classical; **it is not enough to infer a musical period**. `Baroque`, `Romantic` etc require explicit genre evidence.
- Recognizes a deliberately small stable English editorial set (e.g. `Classical; Baroque` and `Electronic; Hardcore`). Multiple standalone FLAC genres become one semicolon-separated Collection display. Unrecognized free-form tags are ignored in navigation, never erased from source files.
- A new Collection library dropdown filters results logically. Search covers genres; CSV/ODS/XLSX can export the additional columns. Existing imported records are enriched safely on the next explicit **Import published archive records** action.
- No new drive access, no MusicBrainz writes, no file-system moves, no re-encoding or FLAC retagging. Existing local records and archived manifests remain in place.

## Genre sources

Reviewed genre proposals use official MusicBrainz release or release-group genres. The established Discogs fallback can suggest a broad genre when matching CD releases agree and MusicBrainz supplies no applicable genre. See [Reviewed genres](REVIEWED_GENRE_TAGGING.md) and [Genre Evidence v1](GENRE_EVIDENCE_V1.md).

## Physical archive split deferred

The operator deferred physically separating Classical and Pop/Rock/Dance on 2026-11-21. Collection defaults to **All libraries** and the section dropdown changes the view. The archive continues to use artist and album directories, with disc subdirectories where applicable. Choosing a section does not require genre tagging or move files.

A physical split would be a separate opt-in change with a reviewed path-migration plan, retained generations, backups and Unraid acceptance. A read-only media-server projection could be evaluated separately.
