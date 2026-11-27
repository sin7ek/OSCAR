# Reviewed genres in OSCAR FLAC archives

## Implemented scope (development PR)

**Source**: official positive-count MusicBrainz `genres` on the exact release (first choice) or its identified release group (fallback). OSCAR ignores free-form `tags`, artist-based genre guesses, unsupported exotic styles and non-positive votes. It normalizes to the existing controlled `archive_genres` list. When neither MusicBrainz source supplies a recognized genre, OSCAR can use broad genres from Discogs CD entries that match artist, title, barcode and catalog number. The classified matches must agree. A verified MusicBrainz medium and a configured Discogs token are required. If MusicBrainz genre lookup is incomplete, defer the fallback.

**Newly ripped CDs**: the normal exact-release MusicBrainz metadata preview shows genre names and their source. When an operator confirms creating a tagged staging copy, OSCAR writes each genre as its own FLAC Vorbis comment (e.g. `GENRE=Classical`, `GENRE=Baroque`). New archives record the Discogs genre source URL in SOURCES.txt and the manifest. Original cyanrip FLACs remain untouched, and the existing staging integrity checks compare STREAMINFO-MD5 and decode every copy. MusicBrainz Disc ID alone is not proof of the physical edition.

**Already published single CDs**: Collection's existing `Scan archive for metadata additions/changes` can now create durable `GENRE` proposals after checking archived release/recording IDs and every track's existing genres for internal consistency. **Accept** only records a decision; it never modifies FLACs. `OSCAR_ENABLE_ARCHIVE_REVISIONS=1` and the existing explicit Archive Revision preview/Apply are still required to copy/retag, verify and retain the previous generation under `.oscar-archive-versions`. The Collection genre and logical library section are updated only in the same finalization transaction, derived from the approved proposal and actual promoted GENRE tags. The Discogs fallback proposes additions only. The approved Discogs source URL is recorded in the revision manifest. Original extraction and publication evidence is preserved.

**Not yet delivered**: coordinated multidisc GENRE Apply on existing boxsets, and customized per-release/track genre curation UI. Group migration currently **only supports LABEL** and must not be reused or bypassed for GENRE. This does not decide the open question of physically splitting Classical and Popular archives, which remains explicitly optional and deferred.

## Acceptance criteria

- CI Tests and Docker image build, then new CD preview/copy and reviewed single-CD GENRE migration on Unraid.
- Independent Verify, release/proposal integrity and original-generation SHA evidence.
- Simulated MusicBrainz genre absence, unsupported styles, and conflicting old track tags must fail closed or remain unclassified.
- No automatic archive writes, no unrequested physical library restructuring or cleanup.
