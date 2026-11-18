# Staging verification report — prototype

After a cyanrip staging job completes with `status=needs_verification`, OSCAR can independently read the existing staged data and provide a **non-destructive report**. It does not modify FLAC/CUE/log files, change the rip state to verified, or publish anything.

## User workflow

1. Once the rip finishes, keep its staging directory intact.
2. In OSCAR's web UI, under **Staging verification (experimental)**, paste the 32-character job ID; e.g. `f41806152a614b1a9006b10456b9bbd4` for the first successful Händel CD.
3. Click **Verify staged rip**, enter the OSCAR rip token and inspect the per-track table. FLAC stream decoding may take some time. The UI polls while it runs.
4. The report is stored at `/staging/oscar-<jobid>/verification-report.json`. Existing rip files remain untouched.

API: `POST /api/rip/jobs/{job_id}/verification` starts the check; `GET /api/rip/jobs/{job_id}/verification` retrieves progress or the persistent report. Both require `X-OSCAR-RIP-TOKEN` and the existing opt-in `OSCAR_ENABLE_RIPPING=1`. The source job must have status `needs_verification` and cyanrip exit code 0. Reusing the same job returns its existing report; OSCAR does not overwrite it.

## Checks

- Expected track count from `plan.json` vs FLACs, tracks and log.
- SHA-256 from `state.json` recomputed for each FLAC; this checks whether the file changed since the hash was recorded.
- Full FLAC stream integrity using the installed `flac -t --silent` on **each file** (fixed argument list, no shell).
- Extract `EAC CRC32`, AccurateRip v1/v2 CRC, status and confidence **from cyanrip's captured console log**, associating each with the track number in the log. Missing or failed confirmation requires review.
- Confirm the original CUE's 28 `FILE` references match the staged FLAC names and confirm `Ripping errors: 0` is present.

A report of `checks_passed` means **all these observed checks passed**, not `verified archive`. `review_required` covers missing evidence, malformed CUE, mismatched hashes or decode errors.

## Deliberate limitations

- **No independent AccurateRip database implementation**: values are parsed from cyanrip's output only.
- **No CTDB**, optical re-read, HTOA/pre-gap audio reconstruction, CUE index provenance verification or authoritative physical-edition determination.
- The CUE check validates referenced filenames, **not** the completeness/correctness of all sector indexes or hidden audio.
- The original job's `state.json` remains `needs_verification`; no automatic archive or deletion even if all checks pass.
- The first complete HDD test (Nov 19, 2026) previously showed 28/28 AccurateRip v1 and v2 matches and all files passed manual `flac -t`. This new report should be **tested against that real staging directory on Unraid** after deployment, but CI is only simulated.
- Retain staging evidence. Later a verified publisher can consume the report only after additional independent checks and physical release review.

