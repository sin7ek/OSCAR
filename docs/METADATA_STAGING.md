# Reviewed MusicBrainz metadata and staged tagged copies

**Experimental. No archive publication, automatic cleanup, or source modifications.**

## Workflow

1. Finish a cyanrip rip and obtain a successful OSCAR verification report (status checks_passed).
2. In OSCAR, open **Metadata & tagging (experimental)** and enter the original 32-character job ID and a specific MusicBrainz **release** UUID, not a release group ID.
3. Click **Preview MusicBrainz tags**. A token-protected request checks that the original Disc ID matches exactly one release medium, verifies the track count, and shows label/catalogue number, barcode, physical release date, names, work hierarchy, composers and performers.
4. Review the release against the physical CD packaging. Click **I reviewed this release — create separate tagged copies** and explicitly confirm the selected release. OSCAR re-fetches MusicBrainz and refuses to proceed if the preview fingerprint changed.
5. OSCAR creates metadata-copy-UUID/audio/ inside the existing staging job, copies each original FLAC to a new file, and tags only the copies with Mutagen Vorbis comments. Before copying it compares source SHA-256 to the rip manifest; after tagging it checks FLAC STREAMINFO audio MD5 and runs FLAC -t on every new copy. A metadata-manifest.json and metadata-preview.json are saved in the new directory.
6. No original FLAC, CUE, state, rip log or verification report changes. No archive promotion or cleanup. Incomplete copies must not be used.

## Tags and provenance

Standard album/track/disc and MusicBrainz release/disc/recording/release-track tags are created. Where MusicBrainz explicitly documents relationships, composer artist IDs, work IDs, parent work title (GROUPING), conductor, orchestra and performer details are also tagged. Artist credits are never invented as composer or performer relationships.

The physical release year is not the recording/composition date. Missing facts remain missing rather than guessed. English aliases, movement numbering, cover art, revised CUE and archive naming are deferred to subsequent stages. The copied FLAC file hash changes due to tags; the decoded audio stream MD5 must not.

## Access and limitations

POST /api/rip/jobs/{job_id}/metadata/preview, POST /api/rip/jobs/{job_id}/metadata/copy, GET /api/rip/jobs/{job_id}/metadata/copies/{copy_id}. All require OSCAR rip token and opt-in; preview/copy additionally require MusicBrainz enabled. A Disc ID is evidence for the medium, not necessarily unique evidence of the physical release.

Reference: first fully verified hardware job f41806152a614b1a9006b10456b9bbd4, Handel / Jordi Savall, 28 tracks, Astrée Auvidis ES 99220 (1999). Real-world metadata review and tagged-copy test still pending. An interrupted copy operation may leave a partial directory; OSCAR never treats such a directory as a completed copy.

## Inspect the actual saved FLAC tags

After a tagged copy reports `tagged_copy_ready_for_review`, open OSCAR's **Inspect saved FLAC metadata** panel. Enter the original rip job ID and the new tagged-copy ID. The inspector uses Mutagen to read the **actual Vorbis comments** on every new FLAC (not only a cached MusicBrainz plan). It compares all values with the saved reviewed preview, displays the per-track composer, work, grouping, conductor, orchestra and full tag dictionaries, and rechecks the tagged file's SHA-256 and STREAMINFO MD5 against the copy manifest. An extra tag, changed field or hash mismatch triggers `review_required`.

Reference on 19 November 2026: Händel staging job `f41806152a614b1a9006b10456b9bbd4` and first completed tagged-copy ID `3ac951bdd5b74ad8b484aaea955eb757`. User reported 28 tagged files completed; the actual per-track readback is pending. This feature does not modify any file or contact MusicBrainz.

GET `/api/rip/jobs/{job_id}/metadata/copies/{copy_id}/inspect` requires standard token auth or the explicitly enabled trusted-UI mode below.

## Optional no-repeat-token trusted local UI

The OSCAR rip token is a protection against other computers on the network launching disk operations. It is not intrinsically required to make the ripping/verification/tagging pipeline automatic: the background jobs can use local server-side permission once the operator has authorized the system.

For a deliberately isolated installation (loopback, protected private LAN, or authenticated reverse proxy), Portainer may set:

```yaml
environment:
  OSCAR_TRUSTED_LOCAL_UI: "1"
```

After redeploy, OSCAR's own browser UI replaces repeated token prompts with its normal confirmation dialogs and sends a custom same-origin action header. This mode **still requires** the independent `OSCAR_ENABLE_RIPPING=1` opt-in for drive access and the existing explicit action confirmations. Keep `OSCAR_RIP_TOKEN` configured for scripts/clients as desired; the browser no longer needs to ask for it when trusted local UI mode is on.

**Security warning:** this is *not authentication*. It explicitly trusts users who can reach the OSCAR interface on the private network. Same-origin and custom-header checks limit cross-site browser submissions but cannot prevent another machine or local program on the trusted LAN from constructing its own requests. Do not expose OSCAR directly to the internet. Restrict network exposure to trusted devices or place it behind a properly authenticated reverse proxy. Do not use this mode on a shared/untrusted Wi-Fi or publicly accessible LAN. It is disabled by default; without it, the rip token remains mandatory.

There is no automatic deletion, archive publishing or unattended disc detection in this release; enabling this option does not change that.
