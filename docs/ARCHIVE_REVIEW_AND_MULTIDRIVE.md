# OSCAR archive review — consistency, cover art, CUE and multidrive status

This is a read-only *review* feature, **not** an archive publisher and not an independent AccurateRip/CTDB verifier. All previous FLACs, logs, original CUE and staging manifests remain untouched.

## Review workflow

1. On Unraid update OSCAR and open **Archive review · consistency, cover & CUE (read-only)**.
2. Select a completed tagging stage:
   - Original MusicBrainz tagged copy: select `original_tags` for **any genre** (pop, house, hardcore, compilations, classical).
   - Classical v2 tagged copy: select `classical_v2` if a separate reviewed Classical v2 copy already exists. This is optional and not a requirement for pop.
3. Enter original rip job ID and tagged-copy ID (or click **Fill first Handel reference** for the original 28-track MusicBrainz tagged copy).
4. Click **Review metadata, artwork & CUE**. The results provide:
   - All actual FLAC track titles, credited artists, MusicBrainz Recording IDs and Work IDs, with decoded FLAC durations.
   - **Review flags** for absent Recording IDs, titles/artists, identical Work IDs with different track titles, identical Recording IDs with substantially different FLAC lengths, and MusicBrainz track-length mismatches where the physical-release length was captured. These flags suggest human review; they are **not proof of a metadata error**.
   - An exact-physical-release Cover Art Archive candidate, if one is available. Album artwork is shown *only* as an online candidate, and is **not downloaded, embedded, or considered approved** until compared against the physical CD. No unrelated image or release-group image is silently substituted.
   - A **CUE preview** retaining the original cyanrip CUE's FILE references and all INDEX/PREGAP timing lines, while proposing reviewed TITLE/PERFORMER fields. OSCAR also shows a **separate future archive CUE proposal** with safe per-track filenames (`NN - Title.flac`). Those renamed archive FLAC files do not yet exist: the archive CUE proposal is not playable until an eventual publisher actually creates those exact filenames. OSCAR never guesses INDEX 00, HTOA, hidden audio, pause sectors or offsets. If the staged file list disagrees with the original CUE, both previews are withheld as `needs_review`. These are text previews only; review physical release before eventual publication.

## Consistency checker: why a duplicate Work ID isn't automatically a problem

MusicBrainz **Work** denotes a composition or movement. Multiple distinct **Recording** entities can legitimately refer to the same work. Thus Händel's *Air* and *Aria* tracks 18/21 may share an HWV 348 work while still having different performances/audio. A duplicate Work ID is not automatically a duplicate recording or a ripping failure.

OSCAR checks what metadata evidence actually exists. It does **not** currently calculate AcoustID/Chromaprint audio fingerprints, compare spectral content, independently validate musicological Work relationships, or query recording lengths from MusicBrainz on older saved metadata copies. A duration difference exceeding ten seconds is only flagged when a source MusicBrainz track duration is available. Source length is stored in new metadata previews, but is absent from the existing first 28-track tagged-copy preview.

All flags remain editorial recommendations for a human reviewer. No change is automatically made to a MusicBrainz relationship or to an audio file.

## Mobile responsive interface

The current OSCAR web UI provides single-column track cards on narrow screens for verification, tag inspection and Classical v2 previews. Full track tables remain available on desktop. Each card uses plain text, and previously exposed expandable full tags are preserved as details, rather than requiring scrolling a very wide table on a phone.

## Parallel drives

The cyanrip engine already tracks active rips by distinct configured optical drive identity; multiple drives can rip concurrently to separate UUID staging folders. This feature adds a **Parallel optical drives** dashboard that shows ready, running and unavailable drives, the most recently started job, current active count and available slots.

New environment setting (default: 3; range 1–16):

```yaml
environment:
  OSCAR_MAX_CONCURRENT_RIPS: "3"
```

Set `4` for a four-drive rig or `7` for seven drives, *once actual drives have been individually configured, offset-calibrated and mapped into the container*. A separate optical drive may be started from the dashboard or existing per-drive test-rip controls, with explicit confirmation and existing token or trusted-local UI access.

Limitations: no persistent queued jobs, no auto-eject, no disc insertion daemon, no power-loss recovery of incomplete rips, no global resource scheduling, no independent CTDB and no guarantee that seven USB/SATA drives can run at full speed on shared hardware. Monitor disk throughput, CPU, temperature, ports and hubs. Restarting the OSCAR container during active rips can interrupt them; preserve staging artifacts. **Three or more simultaneous physical drives have not yet been acceptance-tested on Unraid.**

## Next steps

- Test the existing Händel tagged copy in read-only archive review, then approve/edit the CUE and cover candidate.
- Test a standard pop album, a Various Artists compilation and a continuous-mix house/hardcore CD, including per-track artist and tracks/mixed transition handling.
- Test two then three drives in parallel on Unraid. Verify separate job IDs, logs, outputs, drive offsets and AccurateRip reports.
- Only after these checks design operator-reviewed archive publication, immutable provenance and recovery-safe persistent queueing. Do not delete original staging files.

## Boulez 32-track hardware feedback: CUE performer provenance and missing work

The first real 32-track Boulez Classical v2 review found matching Cover Art Archive art for the exact physical release, source-index-preserving CUE previews and a successful FLAC tag readback. It also exposed two important shortcomings:

- The generated CUE used the MusicBrainz `ARTIST` credit (`Igor Stravinsky`) as the per-track `PERFORMER`, even on Hugo Wolf compositions and where explicit vocalists, the Ensemble intercontemporain and conductor Pierre Boulez were already documented. A release/track artist credit on classical albums may name a **composer**, and must not be unconditionally converted into a performing musician. New **read-only** proposals prefer explicitly documented recording performer relationships (names only) and a documented common conductor for the album level. For classical tracks without explicit performer evidence, omit rather than invent `PERFORMER`. Pop and dance tracks without classical relationships still use their credited artist. The original cyanrip CUE remains untouched.
- The summary returned `no_detected_conflicts` while track 24 `Tilim-bom` lacked a MusicBrainz Work relationship. When some tracks have documented Work IDs, other unlinked tracks receive a **review** observation `missing_classical_work_link` (not a factual mismatch and no inferred composition). For the Boulez disc track 24 needs editorial verification; work vs recording identities must stay separate.

Neither the original CUE nor staged audio or tagged files are rewritten. The proposed archive CUE still refers to future files until separately created and validated. CUE INDEX/PREGAP information is still preserved **as reported**, not independently verified. Album artwork remains a review-only candidate.
