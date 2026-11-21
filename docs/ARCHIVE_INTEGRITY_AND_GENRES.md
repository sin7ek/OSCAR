# Archive integrity verification and genre/library design

## Implemented in this PR: read-only completed-boxset Verify

Under **Collection → Advanced tools → coordinated multidisc revision history**, completed group revisions now offer **Verify original, audio, metadata and Collection**.

The authenticated endpoint `POST /api/collection/archive-revisions/boxset-verify` takes the completed group operation ID and never modifies either archive generation or the Collection. It checks:
- publication identity, original and revised manifests and FLAC file SHA-256 against recorded hashes;
- inherited CUE/extraction evidence integrity, additional artwork/SOURCES/log byte identity;
- original/revised decoded-audio STREAMINFO MD5 identity; independently decodes each original FLAC (new generation is also decoder-tested by existing engine);
- full Vorbis-comment diff, requiring **all tags other than explicitly approved LABEL and any pre-existing RECORDLABEL alias to remain identical**;
- local Collection release/disc/label/provenance and approved metadata decision state.

Verification failure must report the affected disc/tag and **must never** automatically restore, delete, retag or approve an archive. This verifies *migration integrity*, not independently the physical pressing, MusicBrainz correctness, or CTDB.

## Next implementation — controlled genre taxonomy

MusicBrainz exposes **genres**, a curated subset of its folksonomy tags, through `inc=genres`; unreviewed free-form tags must not automatically become archive genres. Query release first, then release-group; record source, counts and query time. Artist genre is too broad to assign automatically to an album and should be a suggestion only.

Use two concepts:
1. **Library section**: `Classical`, `Popular`, or `Unclassified`. This is an editorial navigation grouping, **not** a genre; explicit archive `profile=classical` or reviewed genre can place an album into Classical. Do not derive it from composer names.
2. **Styles/genres**: limited, controlled, operator-approved values in a stable hierarchy, e.g. `Classical; Baroque`, `Classical; Romantic`, `Electronic; Hardcore`, `Rock; Alternative Rock`, `Jazz`. A multidisc box set should have release-level genres; track-specific outliers remain track-level. Never infer `Baroque` solely from the composer because composers can cross periods and arrangements.

Keep original MusicBrainz genre suggestions and operator-approved normalized labels separately, with provenance and snapshot date. Map to canonical headings using an explicit versioned dictionary; expose original detail in advanced views. Missing or conflicting evidence yields `Unclassified` or `Needs review`, not invented tags.

**Non-destructive archive split first:** filter and view Classical/Popular/Unclassified inside OSCAR Collection, optionally provide separate read-only media-library projections. Do NOT physically move existing published paths as part of genre assignment: that would invalidate manifest path evidence, Collection links, versioned-history lineage, and media-server mappings. A future physical relocation would require explicit migration/journal/recovery and backup gates.

## Acceptance

- Real Boulez group operation `7e20981bad8a4145bc7e3ad6d9cecd61` is reported completed. User independently confirmed all 90/90 LABEL and 39/39 decoder tests on revised discs, and read-only preview showed 6/6 already-correct. This is not yet full generation-by-generation metadata/evidence verification.
- Run the new read-only **Verify** against that operation and inspect every disc result before claiming acceptance.
- Verify synthetic negative test when a non-LABEL tag unexpectedly changes and a missing original is reported as failure (not an unintended mutation).
- GitHub CI is distinct from real Unraid testing.
