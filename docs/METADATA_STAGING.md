# Reviewed MusicBrainz metadata and staged tagged copies

**Experimental. No archive publication, automatic cleanup, or source modifications.**

## Workflow

1. Finish a cyanrip rip and obtain a successful OSCAR verification report (status checks_passed).
2. In OSCAR, open **Metadata & tagging (experimental)** and enter the original 32-character job ID and a specific MusicBrainz **release** UUID, not a release group ID.
3. Click **Preview MusicBrainz tags**. A token-protected request checks that the original Disc ID matches exactly one release medium, verifies the track count, and shows label/catalogue number, barcode, physical release date, names, work hierarchy, composers and performers.
4. Review the release against the physical CD packaging. Click **I reviewed this release — create separate tagged copies** and explicitly confirm the selected release. OSCAR re-fetches MusicBrainz and refuses to proceed if the preview fingerprint changed.
5. OSCAR creates metadata-copy-UUID/audio/ inside the existing staging job, copies each original FLAC to a new file, and tags only the copies with Mutagen Vorbis comments. Before copying it compares source SHA-256 to the rip manifest; after tagging it checks FLAC STREAMINFO audio MD5 and runs FLAC -t on every new copy. A metadata-manifest.json and metadata-preview.json are saved in the new directory.
6. No original FLAC, CUE, state, rip log or verification report changes. No archive promotion or cleanup. Incomplete copies must not be used.

## Tags and provenance

Standard album/track/disc and MusicBrainz release/disc/recording/release-track tags are created. Where MusicBrainz explicitly documents relationships, composer artist IDs, work IDs, parent work title (GROUPING), conductor, orchestra and performer details are also tagged. Artist credits are never invented as composer or performer relationships.

The physical release year is not the recording/composition date. Missing facts remain missing rather than guessed. English aliases, movement numbering, cover art, revised CUE and archive naming are deferred to subsequent stages. The copied FLAC file hash changes due to tags; the decoded audio stream MD5 must not.

## Access and limitations

POST /api/rip/jobs/{job_id}/metadata/preview, POST /api/rip/jobs/{job_id}/metadata/copy, GET /api/rip/jobs/{job_id}/metadata/copies/{copy_id}. All require OSCAR rip token and opt-in; preview/copy additionally require MusicBrainz enabled. A Disc ID is evidence for the medium, not necessarily unique evidence of the physical release.

Reference: first fully verified hardware job f41806152a614b1a9006b10456b9bbd4, Handel / Jordi Savall, 28 tracks, Astrée Auvidis ES 99220 (1999). Real-world metadata review and tagged-copy test still pending. An interrupted copy operation may leave a partial directory; OSCAR never treats such a directory as a completed copy.
