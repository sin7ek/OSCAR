# Classical Metadata v2 — reviewed CD sections vs MusicBrainz works

OSCAR's first Händel hardware test (`f41806152a614b1a9006b10456b9bbd4`) and successful 28-track tagged copy (`3ac951bdd5b74ad8b484aaea955eb757`) showed that accurate tagging and good *musicological* organisation are different issues. The physical release describes Water Music **Suite I** in tracks 1–12, **Suite II** in tracks 13–22 and the Royal Fireworks music in tracks 23–28, while the linked MusicBrainz composition parent records involve HWV 348, 349, 350 and 351. OSCAR must never confuse these two classification systems.

## Implemented experimental workflow

1. Deploy the updated OSCAR Docker image and open **Classical metadata v2 — review**.
2. Enter the original rip ID and **the completed tagged-copy ID**, not the original raw ripping folder or a partially failed copy.
3. Review the proposed **physical CD sections**. Every track must belong to precisely one explicitly named range; overlaps and gaps are rejected. The on-page starting ranges for the first Händel reference CD are only suggestions and must be checked against the liner notes.
4. Optional movement titles may be supplied per track, **explicitly**. OSCAR never infers movement numbers/titles from punctuation, track numbers, Roman numerals or work titles. When not reviewed, the MOVEMENT field stays absent.
5. Click **Preview classical v2 tags**. OSCAR verifies the actual saved tagged FLACs and the original MusicBrainz preview from staging, then constructs a separate new metadata proposal. No MusicBrainz request is needed to inspect this existing release; supplemental English aliases are used only when already present in the local alias cache, with no machine translation.
6. Only after reviewing the per-track proposal and confirming the action may OSCAR create a **new** `metadata-v2-<UUID>/audio` subdirectory under the *same rip job*. It writes modified Vorbis comments only to newly copied FLAC files, runs `flac -t` on each, confirms the audio STREAMINFO MD5 is unchanged and writes `classical-v2-preview.json` and `classical-v2-manifest.json` on completion.
7. **Nothing** is automatically published, renamed, archived, cleaned up, or written back to the previous copy. Any incomplete v2 copy remains in staging and must not be treated as completed.

## Field definitions

| Field | Meaning / source |
| --- | --- |
| TITLE | Physical release's MusicBrainz track title, preserved |
| RELEASE_SECTION | Operator-reviewed physical CD section name |
| WORK | Explicitly linked MusicBrainz work title(s), preserved |
| MUSICBRAINZ_WORKID | Explicitly linked MusicBrainz work ID(s), preserved |
| WORK_PARENT | Explicit parent work title(s) from MusicBrainz relationships |
| MUSICBRAINZ_WORKPARENTID | Explicit parent work ID(s) |
| MOVEMENT | Only an explicitly supplied reviewer override |
| COMPOSER / CONDUCTOR / ORCHESTRA | Original documented MusicBrainz artist/role names, preserved |
| COMPOSER_EN / CONDUCTOR_EN / ORCHESTRA_EN | Supplemental English MusicBrainz artist aliases, **only if locally cached** |
| WORK_EN / WORK_PARENT_EN | Supplemental MusicBrainz English work aliases, **only if locally cached** |

The previous overloaded `GROUPING` field is deliberately removed **from the new v2 copies only**. The original v1 copy retains its source tags and provenance. The source title and all related MusicBrainz entity IDs are preserved.

## Important boundaries

- The metadata preview says **requires_review**, even if all preexisting checks passed. It does not certify the edition or correctness of MusicBrainz work relationships.
- Two different tracks may legitimately refer to the same MusicBrainz work; the *Air* vs *Aria* reference on tracks 18/21 remains an editorial issue and OSCAR does not silently merge or correct it.
- Cached English aliases are displayed as extra fields and never replace original names. Missing aliases remain absent, not a failure; remote alias enrichment happens through the separate cache/worker workflow.
- There is no automatic creation of a release CUE, cover art, Navidrome-specific tag mapping or final file naming in this version.
- An explicit operator-approved CD section is editorial metadata distinct from a MusicBrainz composition relationship; both can be valid concurrently.
