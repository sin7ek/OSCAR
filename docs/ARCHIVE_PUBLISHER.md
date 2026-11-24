# OSCAR safe archive publisher (first opt-in version)

**Status:** Explicitly approved archive publication was observed on Tower for Anastacia, Boulez and Carmen Gomes. The publisher is opt-in and preserves original rip evidence. [#138](https://github.com/sin7ek/OSCAR/pull/138) shipped structured source provenance with green PR Tests and Docker build. The new Go! SOURCES preview and publication of a recovered disc still need separate Tower acceptance. See [project status](PROJECT_STATUS.md).

## How it works

1. Source rip must have a saved `checks_passed` verification report. Metadata must have been copied to a completed **Original MusicBrainz tagged copy** or **Classical v2 tagged copy**, and the operator must have reviewed the physical edition.
2. From OSCAR's **Publish verified FLAC archive (explicit opt-in)** panel, enter the original job ID, the completed tagged-copy ID, the copy kind and the music processing profile (`auto` by default).
3. Click **Preview proposed archive (read-only)**. It shows the destination path, final FLAC filenames, full CUE including original recorded INDEX/PREGAP lines, and all outstanding metadata-review observations. The generated `fingerprint` binds this proposal to the exact source manifest and preview.
4. Explicitly confirm the physical edition and CUE/track names. Acknowledge any listed uncertain work/recording relations separately. Review the front cover shown in Go! or Archive Review. Compare it with the physical package, switch the source or select **Upload your own cover artwork**, and explicitly approve the image before publishing.
5. Confirm publication. A background worker copies each tagged FLAC to a **new** hidden staging directory under the destination filesystem, verifies source SHA-256 and STREAMINFO MD5, decodes the copied FLAC, compares its full SHA-256 and audio MD5 with the source, writes an `album.cue` with exact existing FILE references, verifies those references, then writes `SOURCES.txt` and `manifest.json`. Only after all checks pass is the verified directory atomically promoted with Linux `renameat2(RENAME_NOREPLACE)`. No existing album/disc may be overwritten.
6. The UI polls status while the OSCAR process is running. The new folder contains `NN - Title.flac`, `album.cue`, `manifest.json`, `SOURCES.txt` and, when approved, `folder.jpg` next to the disc’s FLACs. The same JPEG is embedded as the front cover in each published FLAC.

## Audio and metadata sources

Use **Review → Advanced tools** to search MusicBrainz by barcode, catalog number, title or matrix/runout. Matrix search checks indexed release annotations. Try a distinctive fragment when the full inscription yields no candidates. Review the release against the physical disc as annotations are incomplete and a shared code can appear on more than one release.

Transcribe the matrix from the inner ring in **Go!** while accepting a Semi Automatic release, or in **Metadata & tagging** while previewing a manual tagged copy. OSCAR records the optional transcription per disc as a custom Vorbis comment `MATRIX_RUNOUT` and attributes it to the operator in `SOURCES.txt` and the archive manifest. Search results do not populate the tag. Both Go and manual publication show the proposed `SOURCES.txt`.

`SOURCES.txt` records the selected MusicBrainz release and edition status, disc position, audio source and AccurateRip evidence per track, published FLAC SHA-256 values, and archived evidence paths and hashes. Go! Archive Review shows the proposed text before approval.

**Front cover** records the artwork source and SHA-256 in both `SOURCES.txt` and the manifest. The approval is bound to the exact JPEG. OSCAR validates the embedded pictures, FLAC decoding and audio checksums, then records new archive file hashes. Tagged staging files and original rip files are preserved. On Tower, test the Cover Art Archive result, a Discogs fallback and a replacement upload in a test archive. Open the archived FLAC and compare its embedded cover with `folder.jpg`.

The **Edition search** section records saved lookup evidence for the disc and MusicBrainz release used by the tagged copy. The standard Go! Disc ID/TOC lookup records its evidence automatically. When the operator runs **Find matching editions**, the same section also includes the supplied identifiers, whether the candidate was suggested, and matched Discogs references, matrix comparisons, provider country values and lookup warnings. The archive manifest retains the same evidence. The provider results are kept as a historical comparison from the recorded date. Editing or approving an edition remains separate from discovery.


- A regular rip uses `PHYSICAL_CD_RIP` and attributes its saved AccurateRip results to cyanrip.
- A Track Recovery publication uses `HYBRID_REPAIRED_CD_RIP`. Each row identifies the source job and file and records the identical raw-source and recovery-copy SHA-256. The verification section attributes the saved v1/v2 results to the independent `trackverify -R` run. `ExtractionEvidence/` contains the recovery source map, saved verification report and available verifier transcript.
- Publication checks the archived FLACs and CUE references against the reviewed staging inputs. Publication uses saved verification evidence. For a new rip interrupted before its automatic CTDB check, archive preparation can complete the pending attempt. Physical edition identification requires separate evidence.

For Unraid acceptance, open the recovered Mahler/Bernstein Disc 11 in Go! Archive Review and expand **Proposed SOURCES.txt**. Expect 16 tracks from the original full-disc job and **Disc 11 / Track 07** from the replacement diagnostic job, with v1/v2 results and both source and published file hashes. If publishing to a test archive, compare the resulting text with the preview and confirm the archived recovery evidence matches the saved staging records.

## Independent CTDB evidence and Discogs pressing comparison

After each successful full-disc rip, OSCAR automatically runs independent CTDB verification on the saved FLACs and eligible CUE. This also runs when cyanrip has no positive AccurateRip result. CTDB evidence does not change the existing AccurateRip-based publication policy. The optical drive is released before the check. Match confidence, no audio match, disc not found and lookup failure are separate outcomes. Review shows the saved outcome. The archive preview and final publication report it in `SOURCES.txt`, with the same result in `manifest.json` and the hash-bound `ctdb-report.json` in extraction evidence.

In **Review → Advanced tools → Staging verification**, enter the complete staged rip job ID and select **Verify this staged disc against CTDB**. OSCAR checks the ordered cue and saved input hashes, then runs `ctdb-cli --xml verify` against the existing FLACs. A match reports database confidence, separate from the AccurateRip evidence. No database entry, no audio match, and lookup failure have distinct outcomes. Verification never submits a rip or applies repairs. CTDB requires a complete supported CUE and does not change archive or Track Recovery approval rules.

The OSCAR container bundles a self-contained Linux build of [ctdb-cli](https://github.com/Masterisk-F/ctdb-cli/tree/627d2daae63d638c6ca9b578a2abba1290a45350) at `/opt/ctdb/ctdb-cli`. Standalone installs can configure `OSCAR_CTDB_EXECUTABLE` to the absolute path of a compatible build. The container includes the corresponding verifier source archive under `/usr/share/doc/oscar/`.

For cyanrip CUEs with pregaps stored in the preceding FLAC, OSCAR accepts the repeated track header and removes the duplicate in a temporary CUE used only by the verifier. File order, INDEX positions and original files are preserved. The report records both CUE hashes.

For cyanrip CD-Extra layouts with a trailing Mode 1 data session, OSCAR checks the FLAC sector lengths and CUE audio starts against the saved audio TOC. It also validates the data-track start, pregap, length and lead-out from the original cyanrip log. The bundled patched verifier receives the full physical TOC and a temporary audio-only CUE. CTDB identifies the complete disc, while the audio checksums cover the FLACs only. The report and SOURCES.txt include the exact full TOC. Existing audio-only CD-Extra reports require a new CTDB lookup. The original CUE, FLACs and data file are unchanged.

The reviewed archive CUE for this layout describes the audio tracks only. OSCAR records the omitted data track in SOURCES.txt and the manifest, preserves the complete original CUE in ExtractionEvidence, and retains the original binary data file in staging. Unsupported non-audio CUE layouts remain in review.

The pinned verifier also distinguishes network or database access errors from a confirmed not-found response. Standalone CD-Extra verification requires OSCAR's `--disc-toc` patch. A direct database lookup using the reported Machines In Motion layout found one entry with confidence 5, while the audio-only TOC returned HTTP 404. Verification of the actual FLACs on Tower remains necessary.

The same full TOC supports a second AccurateRip lookup when cyanrip reported no database entry and recorded both calculated CRCs for every track. OSCAR compares the logged values against the exact full-disc AccurateRip response. It maintains the existing positive-match and FLAC integrity requirements and records the lookup URL, physical TOC, matching versions and confidence. Machines In Motion's original log has all 15 v2 CRCs matching the full-disc AccurateRip entry, confidence 1 each. Verify the existing staging job on Tower before continuing.

A completed lookup result is saved as `ctdb-report.json` with the original CUE and FLAC hashes. Rerun **Proposed SOURCES.txt** after verification. Publication includes the compatible report under `ExtractionEvidence/` and its result in `SOURCES.txt` and the manifest. A transient lookup failure is shown immediately and preserves any previous completed lookup.

Use **Compare physical pressings with Discogs** in Advanced tools, or open it from Semi Automatic Go! review. Enter barcode or catalog number and any observed matrix, mastering SID and mould SID. OSCAR uses the private `OSCAR_DISCOGS_PAT` already supported by the container. It compares identifiers within each numbered Discogs variant for the first five CD candidates. Discogs comparison is read-only. Release approval and tag sources still use the reviewed MusicBrainz edition.


## Unraid / Portainer requirements

- Keep existing `/config` and `/staging` volumes. Do not replace your production Portainer stack with `compose.preview.yml` or change staging storage.
- Add a dedicated writable archive mount to the existing OSCAR container (choose and verify a real safe host directory **outside the source staging**). Example for a **separate, empty test destination**:
  `/mnt/user/oscar-archive-test:/archive` on the host/container. The example uses a **separate host share**, not a subdirectory inside the existing `/mnt/user/ai-workspace` staging share. Create/verify this empty host directory first. Do not map the existing music library writable in early tests.
- Set `OSCAR_ARCHIVE_ROOT=/archive` and `OSCAR_ENABLE_ARCHIVE_PUBLISH=1` explicitly. Publishing remains disabled when the flag or mount is absent. Original ripping opt-in/token/trusted UI settings continue to govern authorization.
- `/archive` must exist and be writable to OSCAR's container user; paths through symlinks are rejected. A lockfile `/archive/.oscar-publish.lock` serializes publication across cooperating OSCAR processes on that filesystem.
- Opening cover review looks up artwork from the accepted MusicBrainz release in Cover Art Archive. If unavailable, OSCAR tries the uniquely linked Discogs CD release when a Discogs token is configured. You can enter a Discogs release ID or URL manually or upload a JPEG, PNG or WebP. An upload and every downloaded image are normalized to JPEG for the preview and publication. The automatic Best Guess publication path does not select or approve artwork.
- If publishing fails halfway through, a hidden `.oscar-unpublished-<id>` directory may remain for inspection. OSCAR does **not** automatically delete or reuse partial files. You can inspect or separately remove only clearly identified failed temporary directories after reviewing them, but never delete original staging.
- The output path is `<album artist>/<catalog prefix> <album title> (<year>) [release-uuid-prefix]/`, with `Disc NN/` for multidisc sets. A second publish of the same album/disc is **refused**. An overwrite is never the default behavior.

[PR #139](https://github.com/sin7ek/OSCAR/pull/139) is open. It adds selected and excluded source-attempt details for new recoveries. It explicitly identifies unavailable historical details for earlier recovery jobs. Existing production source input is a local diagnostic rip.

## Initial hardware fixtures

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
- Independent INDEX00/HTOA checks and read-only post-publish revalidation UI.

This version has **no cleanup feature** and must never delete the original ripping evidence.
