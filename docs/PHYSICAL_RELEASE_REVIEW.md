# Physical release comparison — read-only

OSCAR separates **disc audio identity** from the **physical CD edition**. Different pressings, reissues and combinations can share a MusicBrainz Disc ID. An exact Disc ID match alone must never silently select a different catalog number, barcode, packaging or disc count.

## Current workflow

1. Rip and successfully verify the CD; keep the original staging job.
2. Open **Physical release comparison (read-only)** in OSCAR.
3. Supply the verified staging job ID, a **specific MusicBrainz release UUID** (not a release-group UUID), the catalog number actually printed on your physical CD, and optionally its printed barcode.
4. OSCAR retrieves MusicBrainz metadata for that candidate release and checks the catalog number, barcode, track count and whether the original Disc ID is attached to a matching medium. It shows discrepancies as review items.
5. **Nothing** is written or approved by this comparison. A match across these fields means *consistent evidence*, not proven pressing identity. No source FLAC, tagged staging copy, rip log, original CUE or archive data is changed.

The existing **Metadata & tagging** workflow deliberately still requires a particular MusicBrainz release with an attached, matching Disc ID. This safety check is **not bypassed** by the new read-only comparison. If the correct physical edition exists but the Disc ID is attached only to a different edition, the correct process is to verify it and add/link the Disc ID through MusicBrainz externally; OSCAR itself will not alter MusicBrainz or fabricate the missing link.

## Hardware test cases, 19 November 2026

- **Anastacia — Freak of Nature**, Epic catalog **504757 2**, single CD, 12 tracks, physical barcode from public listing **5099750475720**, MusicBrainz candidate [4b370e6c-e6d2-36a5-8c47-5337a2d77d69](https://musicbrainz.org/release/4b370e6c-e6d2-36a5-8c47-5337a2d77d69). Original rip job `0c81d7d445ce4e29aa95da10c866bcf9`, Disc ID `fHRjyL_F16yLkOO1ddr2Hedl0A0-`. This Disc ID is currently indexed for the distinct **Freak of Nature / Not That Kind** 2CD release, catalog EPC 513365 9. Verify whether it is also attached to the intended single-CD release; if not, review linking it on MusicBrainz.
- **Various — Essential Dance Traxx**, Citycat Club catalog **CCC 97001**, 1997, 14 tracks. Rip job `95dbf0da233d4a3887800a517a149b3c`, Disc ID `UNzDV9I7c4DxDxpasZu014z4sQs-`. Public descriptions support the identity but there is **no verified correct MusicBrainz release UUID yet**. Do not tag the unrelated candidate `Ibiza Party` as if it were this CD. Create/review the correct MusicBrainz release when sufficient physical source evidence exists, then link the Disc ID.
- **Boulez Conducts Stravinsky**, Deutsche Grammophon disc 6 of 6, correctly matched and already used to test the classical tagging, artwork and CUE-preview pipelines. The Cover Art Archive candidate contains a sticker absent from the user's copy; this may be a removable sticker and does not by itself prove a separate edition. Never edit or discard existing cover art without checking physical sources.

## Future goals (not implemented here)

- Search candidate releases by catalog number/barcode directly in OSCAR, not only by Disc ID.
- Compare full per-track durations, recording IDs, printed titles and physical-medium evidence; no automatic fabricated confidence.
- Operator decision history and evidence snapshots for physical-edition approval, including notes about cover-art differences.
- MusicBrainz editing/linking assistance with clear user confirmation.
- Only after physical-edition review and verified export paths: an atomic archive publisher that **renames copied** FLAC files from the initial `Unknown track.flac` names, generates a corresponding usable CUE, and verifies the published collection. **No automatic renaming/publishing exists yet.**

The original rip's `Unknown track.flac` names are intentional staging names. Current CUE proposals with artist/title filenames refer to files that have **not** been created, so they must not be used as completed archive manifests.
