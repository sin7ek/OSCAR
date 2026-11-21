# OSCAR genre discovery and library sections (first safe implementation)

OSCAR may classify **library views**, not physical artist/album directories.

## v1 (PR feature)

- Existing Collection index now stores `genres` (curated FLAC `GENRE` values) and `library_section` (`Classical`, `Popular`, `Unclassified`).
- Explicit, reviewed `manifest.profile=classical` is sufficient to place an album in Classical; **it is not enough to infer a musical period**. `Baroque`, `Romantic` etc require explicit genre evidence.
- Recognizes a deliberately small stable English editorial set (e.g. `Classical; Baroque` and `Electronic; Hardcore`). Multiple standalone FLAC genres become one semicolon-separated Collection display. Unrecognized free-form tags are ignored in navigation, never erased from source files.
- A new Collection library dropdown filters results logically. Search covers genres; CSV/ODS/XLSX can export the additional columns. Existing imported records are enriched safely on the next explicit **Import published archive records** action.
- No new drive access, no MusicBrainz writes, no file-system moves, no re-encoding or FLAC retagging. Existing local records and archived manifests remain in place.

## MusicBrainz genres (follow-on)

MusicBrainz has official `genres` separate from free-form `tags`, available via the API (release or release-group; `inc=genres`). A future **read-only suggestion** workflow should fetch the exact reviewed release and release group, store source/provenance, and offer a human-approved mapping to the OSCAR vocabulary. Artist genres are too broad to auto-apply. Keep provider suggestions separate from approved Collection values; never overwrite user-curated genres or confuse an empty provider genre with an error.

## Future logical vs physical split

Use only library views / optional separate read-only media-server projections first. Physical paths still follow `/archive/Artist/Album/Disc NN` to preserve existing immutable manifests, CUE and version chains. A physical `/archive/Classical` move would require a dedicated journaled path migration with explicit consent, backup and Unraid testing; **not part of genre indexing**.
