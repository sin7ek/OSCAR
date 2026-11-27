# Staging verification report

After a cyanrip staging job completes with `status=needs_verification`, OSCAR can independently read the existing staged data and provide a **non-destructive report**. It does not modify FLAC/CUE/log files, change the rip state to verified, or publish anything.

## User workflow

1. Once the rip finishes, keep its staging directory intact.
2. In OSCAR's web UI, under **Staging verification (experimental)**, paste the 32-character job ID; e.g. `f41806152a614b1a9006b10456b9bbd4` for the first successful Händel CD.
3. Click **Verify staged rip**, enter the OSCAR rip token and inspect the per-track table. FLAC stream decoding may take some time. The UI polls while it runs.
4. The report is stored at `/staging/oscar-<jobid>/verification-report.json`. Existing rip files remain untouched.

API: `POST /api/rip/jobs/{job_id}/verification` starts the check; `GET /api/rip/jobs/{job_id}/verification` retrieves progress or the persistent report. Both require `X-OSCAR-RIP-TOKEN` and the existing opt-in `OSCAR_ENABLE_RIPPING=1`. The source job must have status `needs_verification` and cyanrip exit code 0. Reusing a job with a successful `checks_passed` report returns that report. **Failed/incomplete reports can be retried** using the same button. The prior report is saved separately as `verification-report-previous-<random-id>.json` before OSCAR updates the current `verification-report.json`. Audio, original CUE, logs and state remain unchanged.

## Checks

- Expected track count from `plan.json` vs FLACs, tracks and log.
- SHA-256 from `state.json` recomputed for each FLAC; this checks whether the file changed since the hash was recorded.
- Full FLAC stream integrity using the installed `flac -t --silent` on **each file** (fixed argument list, no shell).
- Extract `EAC CRC32`, AccurateRip v1/v2 CRC, status and confidence **from cyanrip's captured console log**, associating each with the track number in the log. At least one positively matched AccurateRip version (v1 or v2) can satisfy verification when the other version is **absent**; an explicitly negative result for either version requires review. The report records `accuraterip_coverage`, `single_version_tracks` and per-track absent/negative evidence, so a one-version match is never represented as two matches.
- Confirm the original CUE's audio `FILE` references match the staged FLAC names and confirm `Ripping errors: 0` is present.

A report of `checks_passed` means **all these observed checks passed**, not `verified archive`. `review_required` covers missing evidence, malformed CUE, mismatched hashes or decode errors.

## Deliberate limitations

- AccurateRip normally uses cyanrip's reported results. For validated trailing-data CD-Extra discs with an absent cyanrip lookup, OSCAR independently queries AccurateRip using the complete physical TOC and compares the original logged v1/v2 CRCs. Audio CRCs are not independently recalculated by this second lookup.
- OSCAR automatically runs CTDB as a separate check after an eligible full-disc rip. **Verify this staged disc against CTDB** can also run it manually. Its result enters publication evidence without changing AccurateRip-based staging approval. On Tower, the full physical CD-Extra TOC identified *Machines in Motion* and its 15 audio tracks matched CTDB at 5/5. See [archive publishing](ARCHIVE_PUBLISHER.md).
- The CUE check validates referenced filenames, **not** the completeness/correctness of all sector indexes or hidden audio.
- The original job's `state.json` remains `needs_verification`; no automatic archive or deletion even if all checks pass.
- The first complete HDD test (Nov 19, 2026) showed 28/28 AccurateRip v1 and v2 matches and all files passed manual `flac -t`. The later CD-Extra acceptance used a separate 15-track physical disc.
- Retain staging evidence. Later a verified publisher can consume the report only after additional independent checks and physical release review.


## Field bug and recovery — first Händel test

The initial report for staging job `f41806152a614b1a9006b10456b9bbd4` returned `review_required` with `RipError: Rip log too large for automatic verification`: cyanrip's verbose progress output exceeded the old arbitrary 6 MB input limit. This **was not a ripping error**; cyanrip had completed 28 FLACs, 28/28 AccurateRip matches for both versions, and a manual FLAC decode check had passed. OSCAR also accidentally cached the failed verification report as final.

The fix streams the unchanged log in 64 KB chunks, filters out bulky carriage-return progress reports, and retains only CRC32, AccurateRip v1/v2, track metadata, output filename and final ripping-error lines for parsing. The input retains a 512 MB byte-processing safety limit and a 2 MB retained-evidence limit. Existing failed/incomplete reports can now be retried without deleting anything or reripping the CD. Re-run **Verify staged rip** on the same job after deploying the updated image. If the output still says `review_required`, inspect the per-track table to identify specific missing evidence.

## Multidrive regression: v2-only AccurateRip CD (November 19, 2026)

Three optical drives concurrently completed 12-track, 32-track and 14-track jobs: **58 distinct audio FLAC files**, all with no reported ripping errors, valid CUE filename references, matching SHA-256 and successful FLAC decoding. The first two returned 12/12 and 32/32 matches in AccurateRip v1/v2; the third returned 14/14 AccurateRip **v2** matches (confidence 4) and no v1 records. Its initial `review_required` status was due to OSCAR's overly strict both-versions-required policy, **not** a reported checksum mismatch. The updated policy accepts a single positive version when the other is simply absent, clearly marks the outcome as `single_version_on_some_tracks` and does not hide explicitly negative checks. It never adds CTDB/independent AccurateRip evidence. Existing `review_required` reports can be re-run and previous output is retained as history. Preserve all staging files.
