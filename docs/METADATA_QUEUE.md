# Durable MusicBrainz alias retry queue

OSCAR can recover transient MusicBrainz alias failures without keeping the browser tab open.

## Behavior

- The alias batch endpoint returns immediately after its normal lookup; a 429, 5xx, cooldown, or network failure enqueues a deduplicated (artist/work, MBID) job in SQLite.
- The queue persists at /config/metadata_queue.sqlite3, configurable through OSCAR_METADATA_QUEUE_PATH. Resolved aliases remain separately cached in /config/aliases.sqlite3.
- Retries back off from 90 seconds to a maximum of one hour. After eight unsuccessful attempts, the job becomes failed and is retained for diagnosis.
- Jobs survive container restarts. Transactional claims and expiring 180-second leases allow work to be recovered after an unexpected shutdown.
- Only the opt-in worker processes jobs. Set OSCAR_ENABLE_METADATA_WORKER=1 in the **existing** Unraid/Portainer stack, keeping /config writable.
- GET /api/metadata-queue reports pending, running, done and failed counts, plus worker_enabled.
- EN ↻ marks transient failures. The tooltip indicates whether the retry was persisted. Reopen the disc inspector later to show refreshed cached names.

## Scope and safety

Only MusicBrainz artist/work alias enrichment is queued. Disc ID lookup, release selection, artwork, ripping, FLAC tagging and archive publication are not queued or modified. The browser does not yet live-refresh completed retries. There is no cancellation/task management UI.

The MusicBrainz rate limiter is process-local. Keep one OSCAR worker/container until cross-process IP-wide coordination is implemented. Do not deploy parallel workers in production.

## Unraid smoke test

1. Verify GitHub Actions has published the new main image ghcr.io/sin7ek/oscar:main.
2. Add OSCAR_ENABLE_METADATA_WORKER: "1" under environment in the **current** stack, without replacing its device/security settings.
3. Pull latest and redeploy; /config must remain persistent and writable.
4. Open /api/metadata-queue and confirm worker_enabled is true.
5. During a real transient MusicBrainz failure, verify a persisted EN ↻ tooltip and an increase in pending.
6. When MusicBrainz recovers and retry delay passes, confirm done increases; reopen the inspector to see resolved names.

Offline tests cover persistence, deduplication, lease recovery, retry and terminal errors.
