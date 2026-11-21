# Coordinated multidisc GENRE revision — acceptance and safety contract

This extends the existing opted-in coordinated LABEL migration to a **separate, explicit GENRE mode**. Legacy LABEL API calls, operation journal entries and historical Verify remain valid (missing `field` defaults to LABEL).

## Operator workflow

1. **Collection → Import published archive records**, if necessary; open **Scan archive for metadata additions/changes** (whole collection or individual leaves). New MusicBrainz curated GENRE proposals are *not* applied automatically.
2. For the same physical MusicBrainz boxset, explicitly **Accept** every missing/inconsistent but independently reviewed release-scope GENRE proposal. Do not silently accept an ambiguous edition or unsupported genre.
3. Select any indexed boxset disc, click **Preview coordinated multidisc genres (read-only)**. It validates all indexed discs, exact MB disc/recording identities, matching release-group genres, consistent old FLAC genre values per disc, approvals pinned to publication hashes, and the exact missing/present medium set.
4. Enable the **existing** `OSCAR_ENABLE_BOXSET_ARCHIVE_REVISIONS=1` only after backup and operator review. A separate, typed **Apply coordinated boxset revision** is required, with a GENRE-specific plan fingerprint.
5. OSCAR stages new FLAC generations for **only** approved discs, validates each new FLAC, retains every original under `.oscar-archive-versions`, journals promotion, verifies decoded audio and non-audio evidence, updates genre/section in Collection in one transaction, and marks decisions as applied. Missing CDs are never fabricated. Existing manually curated Collection values block unsafe overwrite.
6. Open **View multidisc revision history / recovery → Verify original, audio, metadata and Collection**. Field-specific metadata diff must permit only the approved `GENRE` changes, not changes to LABEL or any other tag.

## Limits

- Group migration is still **not filesystem atomic across multiple disc directories**. A failed/interrupted operation must be explicitly reconciled; do not move/delete files by hand.
- It does not decide a physical Classical/Popular archive split (deferred, must remain optional).
- Genre source is only the release or exact release group's **official positive-count MusicBrainz genres**, normalized to a limited vocabulary. Missing genres remain unclassified; artist guesses or free-form tags never enter Vorbis tags automatically.
- Not a physical pressing or AccurateRip/CTDB authentication.
- CI and real Unraid acceptance are distinct. Previously successful Boulez LABEL revision must be verified not to regress.
