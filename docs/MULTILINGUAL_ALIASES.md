# Multilingual aliases in OSCAR (read-only)

Keep original MusicBrainz entity name **and** English aliases separately, keyed by immutable MusicBrainz entity MBIDs. Do not translate the original field in place.

## Defaults and configurable settings

- `name_display=original_and_english` — display original + English name when known.
- `name_display=original` — original alone.
- `name_display=english` — prefer English when available, preserving original in metadata.
- `english_alias_fallback=original` — default if an English alias is missing.
- `english_alias_fallback=sort_name` — optional artist sort name, **not** an English translation.

These preferences are persisted in `/config/settings.json`, backward-compatible with previously saved configuration.

## How to use
1. Keep `OSCAR_ENABLE_MUSICBRAINZ=1` and your existing read-only drive mappings.
2. In **Language & names**, select *Original + English* (default), save preferences.
3. Inspect a CD release/medium. In the Composer or Work cells, click **EN** next to a specific entity to request its English alias on demand.
4. Alias lookup uses MusicBrainz `/ws/2/artist/{MBID}?inc=aliases&fmt=json` or `/ws/2/work/{MBID}?inc=aliases&fmt=json`. Requests use the existing 1.1s process rate limit. A local UI promise cache prevents duplicate fetches in one page session.
5. **EN ✓** means a locale-marked English alias was returned. **EN —** means no current English alias was found. The original remains available.

No bulk fetching across all tracks: this could create hundreds of unnecessary MusicBrainz requests for a classical boxset. Names are fetched only when requested.

## What this does NOT yet do
- No FLAC audio tagging or publication. Original and English names remain distinct API fields; OSCAR is not yet writing aliases to FLAC tags.
- A MusicBrainz sort name may be a *romanization or sorting order*, not a translation; it is not automatically used as an English alias.
- Navidrome supports `COMPOSERSORT` and other sort tags, but cross-client search for arbitrary custom alias tags needs verification. We will test that once OSCAR has a safe tagging pipeline. Avoid concatenating original + English into the single `COMPOSER` tag.
- This MVP requires pressing **EN** on each composer/work you want to resolve. Future improvements could offer queue-backed alias enrichment and cache snapshots for 1,000+ discs.
- AI/machine translation is disabled; absent MB aliases remain clearly absent.

## Examples
- Igor Stravinsky: original **Игорь Фёдорович Стравинский**, English **Igor Stravinsky** when available from MB.
- Pyotr Ilyich Tchaikovsky: preserve the Cyrillic original and whichever current English alias MusicBrainz provides.
- `Pastorale` / `Pastoral`: do not confuse translated titles with arrangements/versions; maintain work MBIDs.

## Sources
- https://musicbrainz.org/doc/MusicBrainz_API
- https://musicbrainz.org/doc/Aliases
- https://github.com/navidrome/navidrome/discussions/5692
