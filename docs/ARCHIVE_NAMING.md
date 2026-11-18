# Archive naming profiles (preview; no writes)

OSCAR uses the **physical release**, not the musical composition, as the primary directory unit. The text inside square brackets at the beginning of an album directory is the **label's physical-release catalogue number**, not a work number such as HWV, BWV, KV, opus or a MusicBrainz ID.

Preferred schemes:

- Album: `ALBUM ARTIST/[CATALOGUE] ALBUM (RELEASE YEAR)/DD-TT - TITLE.flac`
- Compilation: `Various Artists/[CATALOGUE] ALBUM (RELEASE YEAR)/DD-TT - TRACK ARTIST - TITLE.flac`
- Classical: `Classical/COMPOSER/[CATALOGUE] ALBUM (RELEASE YEAR)/DD-TT - MOVEMENT OR TITLE.flac`

For a classical release featuring **several composers**, use `Classical/Various Composers/` instead of arbitrarily assigning it to a composer. The release year is the year of the selected physical edition, not the recording or composition year. If catalogue number and/or release year are undocumented, omit them rather than inventing values. Preserve the evidence for all original names and catalogue variants in tags/manifests.

## Conductor and performer handling

**Do not automatically add conductor, ensemble or soloist to every directory.** These roles can vary between tracks on the same album and can make paths unwieldy. Keep their MusicBrainz IDs, names (original and aliases), credited roles and recording dates in the archive manifest and FLAC tags. For two editions with no catalogue number or otherwise ambiguous paths, a human can optionally provide a **reviewed performer suffix**: e.g. `Symphony no. 5 (1990) [Rozhdestvensky - LSO]`. It must not be automatically inferred from a single track.

## Implementation state

The `POST /api/archive/name-preview` endpoint accepts metadata and returns **relative paths as text**; it does not read, move, create, rename or tag audio. Its output requires physical-release review. No archive publication is available. Track and album text is sanitized for path components. Folder collision checks and stable published naming are future work.

This scheme is **not yet activated in cyanrip staging**: raw rip output stays under isolated UUID job directories and has no dependency on MusicBrainz metadata.
