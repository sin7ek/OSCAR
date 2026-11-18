# Classical metadata roles: composer versus performer

## Finding from a real OSCAR session
For `Boulez Conducts Stravinsky` — Disc 6 (*Songs*, 32 tracks), the old GUI displayed **Igor Stravinsky** beside every track. The original field was the **track artist credit**, **not** an explicit composer or performer assertion.

## Change
OSCAR now requests MusicBrainz recording-level and work-level relationships on the release lookup:

`recordings+artist-credits+discids+recording-level-rels+work-rels+work-level-rels+artist-rels`

It displays columns with separate provenance:

- **Composer:** explicit artist-composer relation linked to the work of the recording.
- **Performers:** conductor, performing orchestra, performer, vocalist and instrumentalist linked to the recording.
- **Artist credit:** retained separately in the API, never substituted for composer/performer.
- **Work ID / title:** explicit recording-to-work relation.

If MusicBrainz lacks relations, the GUI shows **—** for composer and **Not documented** for performers. It does not fill gaps by guessing from album title, composer credit, or track names.

## Remaining work
- Some classical performer credits may be attached to a different recording in MusicBrainz or to a release note; treat those as additional review sources, not equivalent recorded facts.
- Work hierarchy and movement numbering, arranger, lyricist and recording dates need a separate metadata model.
- Evaluate whether the 6-disc box lookup needs a larger or paginated/recording-level response strategy.
- Verify that the API actually supplies sufficient relationships for the Boulez 32-track medium.
- Keep physical edition approval and archival publishing disabled.

Sources: https://musicbrainz.org/doc/MusicBrainz_API/Examples and https://musicbrainz.org/relationships/artist-recording .
