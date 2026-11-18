# Standard TOC and MusicBrainz release candidates (read-only preview)

This feature extends the working Optiarc media-presence probe with **libdiscid** (MetaBrainz) TOC reading. No audio is extracted.

## New endpoints
- `GET /api/toc?stable_id=<known-drive-id>` — standard CD TOC, track start sectors/lengths, MusicBrainz Disc ID, TOC string.
- `GET /api/releases?stable_id=<known-drive-id>` — re-read the TOC then retrieve MusicBrainz release *candidates*, preserving all editions for manual selection.

Both require the drive to be **enabled and detected with a persistent identity**. Neither changes files. Both are switched **off by default**.

## Existing Portainer stack
**Preserve your existing custom network, own IP, read-only mounts, user/group, `devices`, settings volume and security options.** After a successful `main` image build, add only:

```yaml
environment:
  OSCAR_CONFIG_PATH: /config/settings.json
  OSCAR_ENABLE_MEDIA_PROBE: "1"
  OSCAR_ENABLE_TOC_PROBE: "1"
  OSCAR_ENABLE_MUSICBRAINZ: "1"
  TZ: Europe/Amsterdam
```

Keep the current Optiarc read-only mapping:

```yaml
devices:
  - /dev/sr2:/dev/sr2:r
group_add:
  - "19"
```

Before deploying, confirm `/dev/sr2` is still the Optiarc.

## Testing
1. Insert a **test audio CD**, then press **Check inserted discs**.
2. When `disc_present · audio` appears, press **Read TOC and MusicBrainz ID**.
3. Check track count, offsets and lead-out.
4. Press **Find release candidates on MusicBrainz**. This performs an external API request using a descriptive User-Agent with a per-process 1.1-second minimum interval.
5. If multiple editions appear, *none is automatically chosen*. Compare catalog number, barcode, artwork, performers and physical CD.

MusicBrainz API access requires outgoing HTTPS to musicbrainz.org; failures do not block the local TOC reader.

## Important limits
- Standard TOC track offsets represent track starts (INDEX 01). **INDEX 00 pregaps, HTOA and audio extraction are not yet checked.**
- AccurateRip Disc ID and CTDB verification are not implemented here.
- MusicBrainz Disc ID identifies disc layout, **not a unique physical edition**.
- There is no automatic archive publication or deletion.
- This alpha GUI currently has **no authentication**. Restrict to a trusted LAN or an authenticated proxy.

References:
- https://metabrainz.github.io/libdiscid/discid_8h.html
- https://musicbrainz.org/doc/MusicBrainz_API
