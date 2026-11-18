# Classical works and movements (read-only first implementation)

OSCAR separates:
1. **Release** — the exact physical CD/box edition under review.
2. **Medium** — a particular disc, selected by explicit MusicBrainz Disc ID link.
3. **Recording** — the audio performance with artist role relationships.
4. **Work** — the musical composition, potentially a movement of a larger work.

## Display rule
The hierarchy is constructed **only** when MusicBrainz provides an explicit child-work → parent-work `parts` relationship (`direction=backward`).

- Consecutive tracks sharing the same explicit parent work MBID are grouped under its original MusicBrainz title.
- Without a parent link, a track remains independently displayed as ungrouped.
- Ambiguous or multiple parents are deliberately not assigned to a single work group.
- A track's title containing `:`, `Suite I`, `Symphony no. 5`, or `I. Andante` is **not** enough to claim a verified parent relationship.
- Explicit work MBIDs and titles are preserved, independently of release title and recording artist credit.
- Groupings are presentation only, with no audio processing, tagging, archiving or cleanup.

## User's hardware reference cases
- **Optiarc (Stravinsky)** — *Boulez Conducts Stravinsky*, CD 6 *Songs*: work and arrangement links, Pierre Boulez, Ensemble intercontemporain, various vocal soloists.
- **dev1 (Handel)** — Water Music Suite I, Jordi Savall and Le Concert des Nations; potential parent work for Prélude and Menuet I.
- **dev3 (Tchaikovsky)** — Symphony no. 5 in E minor, op. 64, movements I and II, Gennady Rozhdestvensky and London Symphony Orchestra.

These real-world texts establish the test themes; the parent relation objects in unit tests are synthetic. A full real-hardware MusicBrainz response must determine whether the hierarchy actually exists.

## Remaining work
- Recursive work chains beyond the first parent level, and movement numbering via MusicBrainz relationship attributes.
- Explicit alternate titles/transliterations of composer and work names (avoid replacing native-language spelling).
- Recording performance dates and arrangements with their own work identities.
- Long-term source snapshots/manifest schema and metadata-review approval.
- More complete support for cases where work relationships require separate MusicBrainz work lookups.

See https://musicbrainz.org/doc/MusicBrainz_API/Examples for relationship includes.
