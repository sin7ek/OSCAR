# Automatic English alias enrichment

The medium inspector now automatically resolves MusicBrainz artist and work aliases.

## Behavior
- On inspecting an exact medium, collect unique MBIDs for displayed composers and works.
- Submit bounded batches of at most **8 unique MBIDs** to `POST /api/name-aliases/batch`. The server hard-limits requests to 12 entities.
- Reuse the existing MusicBrainz process-wide request rate limit (minimum 1.1 seconds between requests); network enrichment is gradual, and the tracklist displays immediately.
- Store each response in `/config/aliases.sqlite3`, under the existing writable OSCAR config volume, keyed by entity type and MBID.
- Positive English alias cache: 30-day TTL. No-English-alias cache: 7-day TTL.
- On lookup failure, the previous record is not overwritten. A failed entry remains clearly flagged for retry, not fabricated or replaced by sort-name.
- The original name is always retained. All aliases require MusicBrainz provenance. No machine translation.
- A simple per-page visual progress message reports how many unique names were processed.
- The `EN` button remains as a retry path when an individual lookup fails.

## Unraid/Portainer
No new environment variables are needed if `/config` already maps to `/mnt/user/appdata/oscar` and the directory is writable by UID 999. Optionally set `OSCAR_ALIAS_CACHE_PATH` to a custom file path on a writable volume.

The SQLite file is metadata only. There are **no accesses to music archive paths** and no changes to FLAC files.

## Future enhancements
- Preload a background job after disc identification and present metadata snapshots in a full review UI.
- Deduplicate aliases across multiple parallel containers/worker processes with a centralized job queue and shared MusicBrainz rate limiter.
- Implement release-specific transliterations and composer/performer naming preferences.
- Verify alias tag indexing with Navidrome; a sort-name is not an English alias.
- Continue with cyanrip secure extraction after metadata workflow is stable.
