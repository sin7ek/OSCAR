# Live ripping progress and ETA (OSCAR Go!)

**Feature implementation:** in-progress Go! drive cards show a read-only progress bar per running cyanrip job and update automatically about every 3.5 seconds while a Go tab with authenticated session is open. No optical drive commands are issued to refresh; no extraction, original files or archive metadata changes.

## Source and accuracy

Current production cyanrip (Debian 0.9.3) is invoked with redirected combined output to `cyanrip-console.log`. OSCAR does not currently receive a guaranteed machine-readable per-sector progress stream. The v1 implementation therefore reads only the existing original staging `plan.json` track count and currently created `audio/N - *.flac` files, rejecting symlinks and unsafe/missing plans. Since a FLAC can exist *while still being written*, a track is counted completed **only after the next contiguous track's file appears**. During active extraction the progress percentage stays below 100%. A long final track can take time despite a nearly full bar; completion only follows cyanrip process exit and later independent verification.

The progress percentage is **completed tracks / total tracks**, NOT elapsed audio-duration or sectors. The screen labels that distinction. ETA is deliberately **rough track average** using elapsed seconds since extraction started divided by at least **two completed tracks**, multiplied by remaining track count. It is omitted until sufficient evidence exists, and will fluctuate for Mahler/classical music with long uneven movements, bad CD reads, rereads, or verification after rip. Unknown ETA is displayed as `calculating…`, never as invented accuracy. Progress and ETA are transient observations; no filesystem mutations, job ledger amendments, or provenance writes.

## Unraid acceptance

1. On fresh `main`, initiate rips of known sacrificial/test CDs on each of the three configured drives (GH24NS95, Optiarc AD-7200S, hp DH16AAL), keeping pre-existing live rips untouched; open Go.
2. Check three independent bars, 3.5-second refresh with no repeated prompts in trusted-local session, and track counts as file output progresses. Verify no bar claims a track finished before its following track starts.
3. Run a one-track CD, a long Mahler movement and a damaged/slow-reading disc, and verify ETA is marked as rough or unavailable, never `100%` while cyanrip still runs.
4. Verify accurate separate completed job/verification statuses and original cyanrip logs; reload the UI and test service-restart interruptions. UI alone does not establish rip/AccurateRip/CTDB success.
5. Do not confuse newly implemented Python CI/Docker build with actual hardware acceptance.

**Follow-on:** If cyanrip has stable text/sector progress on the exact deployed version, sample anonymized real `cyanrip-console.log` outputs and build version-tested sector/track duration-weighted progress. Do not guess from arbitrary terminal percentages or change cyanrip flags solely for UI aesthetics.
