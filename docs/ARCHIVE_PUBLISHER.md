# OSCAR safe archive publisher (first opt-in version)

**Status:** Code shipped via the feature PR after CI; hardware deployment **not yet proven**. This feature is explicitly disabled by default and never deletes originals. Use initially with the known-good Anastacia 12-track staging copy; after that, the Boulez Classical v2 copy (32 tracks).

## How it works

1. Source rip must have a saved `checks_passed` verification report. Metadata must have been copied to a completed **Original MusicBrainz tagged copy** or **Classical v2 tagged copy**, and the operator must have reviewed the physical edition.
2. From OSCAR's **Publish verified FLAC archive (explicit opt-in)** panel, enter the original job ID, the completed tagged-copy ID, the copy kind and the music processing profile (`auto` by default).
3. Click **Preview proposed archive (read-only)**. It shows the destination path, final FLAC filenames, full CUE including original recorded INDEX/PREGAP lines, and all outstanding metadata-review observations. The generated `fingerprint` binds this proposal to the exact source manifest and preview.
4. Explicitly confirm the physical edition and CUE/track names. Acknowledge any listed uncertain work/recording relations separately. Optionally select **Include Cover Art Archive front image**, but only after visually comparing it to the user's physical package and explicitly accepting the exact candidate (Boulez's removable-looking sticker may differ); cover is saved as a separate `cover.jpg`/`cover.png`, **not embedded in FLACs**.
5. Confirm publication. A background worker copies each tagged FLAC to a **new** hidden staging directory under the destination filesystem, verifies source SHA-256 and STREAMINFO MD5, decodes the copied FLAC, compares its full SHA-256 and audio MD5 with the source, writes an `album.cue` with exact existing FILE references, verifies those references, then writes `SOURCES.txt` and `manifest.json`. Only after all checks pass is the verified directory atomically promoted with Linux `renameat2(RENAME_NOREPLACE)`. No existing album/disc may be overwritten.
6. The UI polls status while the OSCAR process is running. The new folder contains `NN - Title.flac`, `album.cue`, `manifest.json`, `SOURCES.txt` and optionally a separately reviewed cover image.

## Audio and metadata sources

`SOURCES.txt` records the selected MusicBrainz release and edition status, disc position, audio source and AccurateRip evidence per track, published FLAC SHA-256 values, and archived evidence paths and hashes. Go! Archive Review shows the proposed text before approval.

- A regular rip uses `PHYSICAL_CD_RIP` and attributes its saved AccurateRip results to cyanrip.
- A Track Recovery publication uses `HYBRID_REPAIRED_CD_RIP`. Each row identifies the source job and file and records the identical raw-source and recovery-copy SHA-256. The verification section attributes the saved v1/v2 results to the independent `trackverify -R` run. `ExtractionEvidence/` contains the recovery source map, saved verification report and available verifier transcript.
- Publication checks the archived FLACs and CUE references against the reviewed staging inputs. OSCAR does not run another AccurateRip or CTDB lookup during publication. Physical edition identification requires separate evidence.

For Unraid acceptance, open the recovered Mahler/Bernstein Disc 11 in Go! Archive Review and expand **Proposed SOURCES.txt**. Expect 16 tracks from the original full-disc job and **Disc 11 / Track 07** from the replacement diagnostic job, with v1/v2 results and both source and published file hashes. If publishing to a test archive, compare the resulting text with the preview and confirm the archived recovery evidence matches the saved staging records.

## Unraid / Portainer requirements

- Keep existing `/config` and `/staging` volumes. Do not replace your production Portainer stack with `compose.preview.yml` or change staging storage.
- Add a dedicated writable archive mount to the existing OSCAR container (choose and verify a real safe host directory **outside the source staging**). Example for a **separate, empty test destination**:
  `/mnt/user/oscar-archive-test:/archive` on the host/container. The example uses a **separate host share**, not a subdirectory inside the existing `/mnt/user/ai-workspace` staging share. Create/verify this empty host directory first. Do not map the existing music library writable in early tests.
- Set `OSCAR_ARCHIVE_ROOT=/archive` and `OSCAR_ENABLE_ARCHIVE_PUBLISH=1` explicitly. Publishing remains disabled when the flag or mount is absent. Original ripping opt-in/token/trusted UI settings continue to govern authorization.
- `/archive` must exist and be writable to OSCAR's container user; paths through symlinks are rejected. A lockfile `/archive/.oscar-publish.lock` serializes publication across cooperating OSCAR processes on that filesystem.
- No implicit network access for cover images unless you separately check the artwork checkbox and approve the cover. No automatic cover artwork edit or embedding.
- If publishing fails halfway through, a hidden `.oscar-unpublished-<id>` directory may remain for inspection. OSCAR does **not** automatically delete or reuse partial files. You can inspect or separately remove only clearly identified failed temporary directories after reviewing them, but never delete original staging.
- The output path is `<album artist>/<catalog prefix> <album title> (<year>) [release-uuid-prefix]/`, with `Disc NN/` for multidisc sets. A second publish of the same album/disc is **refused**. An overwrite is never the default behavior.

## Hardware acceptance sequence

### Anastacia

- Rip job `0c81d7d445ce4e29aa95da10c866bcf9`
- MusicBrainz release `4b370e6c-e6d2-36a5-8c47-5337a2d77d69`
- Catalog `504757 2`, barcode `5099750475720`
- **Copy kind:** `original_tags`; profile `auto` should choose `standard`.
- **Completed tagged copy ID:** copy the identifier from the previously successful metadata inspection or Archive Review; it has not been included in the canonical status document, so don't guess it.
- Expected: 12 final tracks with readable titles, Anastacia track CUE PERFORMER, zero metadata observations, correct CUE FILE references and a manifest. First try without artwork, then optionally test separately with a different album copy or a test archive destination.

### Boulez

- Rip job `699e010ffdda46ea80cc67b07b72a28e`
- Release `423f636d-742d-47b0-9ba2-51515a6fdfd2`, disc 6 of 6
- **Copy kind:** `classical_v2`; profile `auto` should choose `classical`.
- **Completed Classical v2 copy ID:** recover from the successful Archive Review or Classical v2 status; **not** the original v1 copy ID `331f89f080d747a381dae81c8d01f799`.
- Expected: 32 distinct title-named FLACs under `Disc 06`, conductor/ensemble/vocalist CUE credits, one explicit `missing_classical_work_link` review observation for track 24. Only proceed after consciously acknowledging that this source metadata gap remains unresolved. Album image has a sticker compared with the user's physical copy; leave artwork unchecked if not accepted.

### Citycat

- Original job `95dbf0da233d4a3887800a517a149b3c`, catalog `CCC 97001`, 14 tracks.
- **Not eligible for publishing**: proper physical MusicBrainz release missing; rip has been deferred to OSCAR's release review backlog. Do not substitute the unrelated `Ibiza Party` metadata. No archive copy or workarounds until edition evidence is resolved.

## Future work

- Automated full-release identification and MusicBrainz fallback cache/providers (#40), rather than manually pasting job/copy IDs.
- Persistent publication-progress journal and restart recovery, disk-space preflight, richer metadata tracklist comparison against physical packaging, more robust cross-process device/mount selection.
- Integrated extraction→verify→match→tag→review→publish automation profiles (#32).
- Optional cover embedding and user-supplied cover handling, independent INDEX00/HTOA and CTDB checks, read-only post-publish revalidation UI.

This version has **no cleanup feature** and must never delete the original ripping evidence.
