# External album verification (experimental)

Use this read-only tool to check existing split-track FLACs, for example an EAC rip. It reports FLAC integrity and attempts CTDB verification per disc. It does not create a rip job, submit to CTDB, write tags, update Collection, modify SOURCES.txt, or publish an album. See [issue #183](https://github.com/sin7ek/OSCAR/issues/183).

## Web UI

Set `OSCAR_EXTERNAL_LIBRARY_ROOT: /external-music` in the OSCAR service environment and add the bind mount `/mnt/user/music/Archive:/external-music:ro` to that service's volumes. Substitute the host directory if your external music lives elsewhere. Use a dedicated read-only bind mount even if the same host data is accessible to another service.

In **Collection → Verify an existing FLAC album**, select **Browse music library**, open the album folder and select **Verify this album against CTDB**. This also works when ripping is disabled. The usual OSCAR token or trusted local access is required. The folder browser stays inside the configured mount, lists visible directories and does not follow symlinks.

The check runs in the background and shows FLAC results and CTDB confidence per disc. **Show latest check** retrieves the most recent result until another album is checked or OSCAR restarts. The web UI does not save results or files in the source album.

## Run on Unraid

Use a directory containing one album with its intended audio FLACs. Choose a known complete rip that previously matched CTDB to test the match path. The source is mounted read-only and the inferred CUE is temporary.

```bash
read -r -p 'Full path to the album on Tower: ' album
docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m --mount "type=bind,source=$album,target=/album,readonly" ghcr.io/sin7ek/oscar:main python -m oscar.external_verification /album
```

The command prints JSON to the terminal. Look for `source_type: external`, `status: database_matched_candidate_layout`, and `ctdb.status: matched` with confidence for each disc. A returned report means the FLAC inventory and SHA-256 values were checked again at the end. Save the JSON outside the album if needed. In a non-container environment, run `python -m oscar.external_verification /path/to/album` with `flac` on PATH and `OSCAR_CTDB_EXECUTABLE` set to the absolute path of OSCAR's bundled or equivalently patched `ctdb-cli`.

## Inputs and limits

- Each FLAC needs a numeric `TRACKNUMBER`. Multidisc folders also need `DISCNUMBER` on all files. If all disc numbers are absent, the CLI assumes one disc. It reads totals from slash notation, `TOTALTRACKS` / `TOTALDISCS`, or `TRACKTOTAL` / `DISCTOTAL`. Provided totals must agree with the files. When totals are missing, the inferred inventory can miss a trailing disc or track.
- Input files must have consecutive track numbers from 1 per disc. Use a directory without symlinks or unrelated FLACs, including failed attempts or alternate encodes. CTDB requires CD PCM at 44.1 kHz, 16-bit stereo, and 588 samples per sector.
- The generated CUE assumes one FLAC per track starting at INDEX 01, contiguous audio and no hidden audio. This prototype uses track lengths and ignores any existing CUE. EAC gap handling, hidden audio and CD-Extra can produce a different TOC from the physical disc. A CTDB match applies to the inferred layout, independently of pressing identity or the original extraction method.
- `ctdb.status` distinguishes `not_found`, `no_audio_match`, `unsupported`, `unavailable` and `lookup_failed`. Read it per disc, including when the report says `integrity_passed`. A missing CTDB match alone does not establish a bad rip. AccurateRip is outside this prototype.
- Exit status 0 means the FLAC integrity tests passed, including when CTDB did not match. Exit status 1 means a decoder test failed or could not run. Exit status 2 means the album inventory could not be read or validated, including a changed input.
