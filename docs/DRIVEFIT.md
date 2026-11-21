# DriveFit — optical-drive diagnostics

## v1 and persistent history (read-only diagnostics)

OSCAR has a separate **Diagnostics** tab with **DriveFit**. The authenticated `GET /api/diagnostics/drivefit` summarizes existing OSCAR staging `state.json`, `plan.json` and `verification-report.json` files per configured drive. No optical device is opened or tested; data is never changed or deleted.

It shows connected drive identity and firmware (if available), available sample size, extraction duration, verified/review-required counts, rip failures/interruption reports, and cyanrip-reported extraction errors. **Newly completed jobs are also summarized in a persistent SQLite history file beside settings.json** (normally /config/drivefit.sqlite3). It survives staging cleanup and restarts, and can be backed up with /config. It stores no album names, audio, file paths or MusicBrainz Disc IDs. Older jobs not previously recorded can be shown while their staging folders still exist, but are not automatically retained retroactively. No wear sensors, physical lifespan estimate, normalized speed benchmark or definitive replacement judgement is available in v1.

**Causation and interpretation:** Slow extraction can reflect CD length, optical characteristics, manufacturing, drive firmware and secure-reading strategy, not just a worn mechanism. AccurateRip not found can reflect database coverage; a negative AccurateRip result is not independently measured drive health. Many seconds per disc is not a meaningful drive comparison unless length and conditions are controlled. A `review_required` verification state is not a hardware failure.

**Persistent v2:** The bounded, privacy-conscious per-job drive-performance SQLite ledger now records non-secret metrics after each rip, then updates with independently reviewed verification outcomes. Derive normalized wall-clock vs audio-duration throughput where TOC supports it. Record retry/error indicators only when a stable, documented cyanrip 0.9.3 field can be parsed reliably; don't confuse output progress text or AR confidence with retry counts.

**Planned v3:** An explicit controlled test using the *same known-good pressed CD* on multiple drives, with operator confirmation, consistent read offsets, per-drive firmware, CD sector count, environment and baseline snapshots. Trend across repeated discs, report `insufficient evidence`, `change detected` or `investigate` (not an invented 0–100 health score). Require multiple corroborating abnormal measurements before recommending hardware inspection/replacement; never trigger automatic ripping or destruction.

This feature is independent of draft coordinated multidisc migration PR #110. CI passing is not evidence of live Unraid acceptance.
