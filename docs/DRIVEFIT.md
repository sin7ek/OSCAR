# DriveFit — optical-drive diagnostics

## v1 (read-only retrospective)

OSCAR has a separate **Diagnostics** tab with **DriveFit**. The authenticated `GET /api/diagnostics/drivefit` summarizes existing OSCAR staging `state.json`, `plan.json` and `verification-report.json` files per configured drive. No optical device is opened or tested; data is never changed or deleted.

It shows connected drive identity and firmware (if available), available sample size, extraction duration, verified/review-required counts, rip failures/interruption reports, and cyanrip-reported extraction errors. Historical observations are bounded, and missing/deleted staging folders are not counted. No wear sensors, physical lifespan estimate, normalized speed benchmark or definitive replacement judgement is available in v1.

**Causation and interpretation:** Slow extraction can reflect CD length, optical characteristics, manufacturing, drive firmware and secure-reading strategy, not just a worn mechanism. AccurateRip not found can reflect database coverage; a negative AccurateRip result is not independently measured drive health. Many seconds per disc is not a meaningful drive comparison unless length and conditions are controlled. A `review_required` verification state is not a hardware failure.

**Planned v2:** Persist a separate, privacy-conscious append-only drive-performance ledger outside the staging lifecycle, storing limited non-secret aggregate evidence after each rip. Derive normalized wall-clock vs audio-duration throughput where TOC supports it. Record retry/error indicators only when a stable, documented cyanrip 0.9.3 field can be parsed reliably; don't confuse output progress text or AR confidence with retry counts.

**Planned v3:** An explicit controlled test using the *same known-good pressed CD* on multiple drives, with operator confirmation, consistent read offsets, per-drive firmware, CD sector count, environment and baseline snapshots. Trend across repeated discs, report `insufficient evidence`, `change detected` or `investigate` (not an invented 0–100 health score). Require multiple corroborating abnormal measurements before recommending hardware inspection/replacement; never trigger automatic ripping or destruction.

This feature is independent of draft coordinated multidisc migration PR #110. CI passing is not evidence of live Unraid acceptance.
