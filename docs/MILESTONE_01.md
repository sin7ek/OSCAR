# Milestone 01 — Optical-drive and verifier feasibility

- [ ] Read-only inventory of Unraid optical devices (stable /dev/disk/by-id identifiers, firmware, capabilities).
- [ ] Establish drive read offsets and handling of caching, C2, gaps and possible HTOA.
- [ ] Run cyanrip with a physical test disc in a dedicated test staging directory, never Archive.
- [ ] Compare rip TOC, indices, logs and audio evidence with an existing verified reference rip.
- [ ] Confirm AccurateRip v1/v2 behavior including **missing** entries.
- [ ] Confirm real CTDB command-line verification on Linux; record exact tool/runtime/version.
- [ ] Check valid per-file FLAC decoding and audio checksums.
- [ ] Demonstrate safe interruption and resumability.
- [ ] Collect a classical metadata case with multiple editions.
- [ ] Document installation strategy for an opt-in Docker/Unraid deployment.

**Acceptance:** reproduce known verification edge cases (Part VI, Part VIII, Datafile I) where feasible, and show no existing Archive files were modified.
