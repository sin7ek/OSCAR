# Select refreshed metadata copy before first Go publication

**Status:** merged in [#126](https://github.com/sin7ek/OSCAR/pull/126) after GitHub Tests and Docker build passed. Live adoption of a refreshed copy on Tower remains open. The adoption action writes no archive files.

## Problem and live test case

An operator with a verified, accepted Semi Automatic staging CD can improve the *same* MusicBrainz release after the initial tagged staging copy, for example adding catalog number `477 8668` to Deutsche Grammophon Mahler/Bernstein *The Symphonies* (2010, 11-CD box). The existing MusicBrainz reprocess action creates an independently identified second staging copy but Go's durable workflow still references the first.

**Exactly identified user staging jobs:**
- **Disc 02:** `5b48c63b756a473197af192b65505a63` (4 tracks, Symphony No. 2 II–V).
- **Disc 03:** `e4ca0a116f744e0799d2dbf04161f6f1` (3 tracks, Symphony No. 3 I–III).
- **Disc 04:** `8665644102f241c69d981abb640ef8f1` (5 tracks, Symphony No. 3 IV–VI, Symphony No. 6 I–II).

**Original staging fixtures.** Tower later reported Collection publications for discs 02 and 03. Use a still-unpublished eligible job to test adoption before a first publication. The user is ripping three additional CDs. Do not assume their IDs or disc positions until the operator provides them.

## New flow

1. For an accepted, verified Semi Automatic Go job in `METADATA_READY`, run **Refresh metadata from MusicBrainz**. This compares the original tagged copy against the same accepted release, without writes.
2. If changes exist, explicitly create an independent tagged staging copy, then **Check new staging copy**, which reads the actual tags, hashes and STREAMINFO audio MD5.
3. After a successful readback, click **Use verified refreshed copy for FIRST Go publication**. The server checks that both copies are correctly linked to the same job/release and physical disc/track identity, verifies source rip SHA evidence again, and atomically replaces Go's active `metadata_copy_id` and `metadata_fingerprint` inside SQLite while recording an adoption event.
4. Reopen Go, use **Review actual tags, classical works, CUE and archive destination**, review the *new* fresh fingerprint, physical edition/catalog, expected 11-CD structure and disc number. Publication still needs its own explicit separate approval.

## Safety

- Refuse adoption if the job is published, interrupted, no longer `METADATA_READY`, not the original accepted Semi Automatic release, or if an archive publication has EVER been reserved for this job.
- Refuse changed or missing original source file/track ordering, mismatched release/disc identity, changed fingerprint, unverified tagged copy, or inconsistent source hashes.
- No new audio extract, no overwrite, no in-place tagging, no publication, no archive history cleanup. The originally tagged staging copy remains preserved.
- A successful adoption does **not** upgrade `INFERRED_OPERATOR_ACCEPTED` to physically verified. The operator must confirm physical packaging and audio separately. The MusicBrainz catalog currently lists both `002894778668` and `477 8668`; OSCAR might still propose `[002894778668]` as folder prefix, as it chooses from the release's catalog list. Do not silently promise `[477 8668]`; a catalog preference feature would be separate.
- The existing standalone refresh-copy feature must continue to work for **already published** Carmen Gomes jobs, but adoption is refused for them.

## Acceptance on Unraid

After merging CI-green code, pull fresh main. For Mahler CD 02, choose refreshed staging copy, inspect, adopt, then re-open Go archive preview and check verified readback, published edition, catalogue tags and destination. Repeat CD 03/04 only after CD 02 safely validates. Verify jobs remain `METADATA_READY`, nothing published automatically and prior copies remain. Do not publish until the operator confirms the physical release and destination.

