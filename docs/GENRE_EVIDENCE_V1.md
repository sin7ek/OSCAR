# Genre Evidence & Confidence v1 — read-only provider comparison

**Merged in [#124](https://github.com/sin7ek/OSCAR/pull/124); GitHub Tests and Docker build passed. Tower exercised the read-only preview with MusicBrainz and Discogs.** The feature is a read-only source-by-source preview in **Collection → Archive metadata maintenance → Genre evidence — source comparison (read-only)**, using the already selected published album. API `POST /api/collection/genre-evidence/preview` requires the existing OSCAR RIP token and accepts `archive_path`, optional explicit numeric `discogs_release_id`, and one of the existing settings policy names (`secure`, `semi_automatic`, `best_guess`). This endpoint never writes to archive/FLAC/Collection/SOURCES or approves proposals.

## Current source capabilities

- MusicBrainz: exact archive release UUID / release-group fallback, positive-vote official genres only. Preserve vote counts and origin. One provider group even when both endpoints were checked.
- Discogs: explicit **operator-supplied** release ID using configured `OSCAR_DISCOGS_PAT`, read-only API release endpoint, match physically printed archive catalog number and CD format before treating genre/style as an applicable source. A barcode match is additional evidence. Never search by ambiguous title alone or pretend physical pressing verification.
- No automatic Qobuz or web scraping. Qobuz needs authorization/licensing research; reviews or store pages can be evaluated later as operator-supplied, independently sourced citations. Current v1 is **not** five-source consensus and makes no statistical claims.

The tool groups source claims conservatively, normalizes into the existing versioned editorial genre set, shows missing/unknown/unsupported replies as abstentions, and reports agreement fractions among applicable independent sources. `high` means at least three independent album/release claims with at least 75% agreement, `medium` has at least two majority claims; conflicts/missing evidence remain for review. These thresholds are **experimental and not calibrated probabilities of truth**.

## Security / provenance

- Validated real published archive manifests and every indexed FLAC before fetching; matched exact local MusicBrainz release ID; no user-provided network URL accepted; fixed HTTPS provider hosts.
- No automatic tag writes, no physical-release confidence upgrade, no genre authority inferred from artist/composer alone.
- Keep public provider attribution, scope, source and vote counts in the JSON report. `evidence_fingerprint` hashes claims to support future durable review.
- This is **not yet** persistent `genre_evidence` in `manifest.json` or rendered `SOURCES.txt`; the user requested this and it remains a separate milestone because the existing archive verifier correctly rejects changing non-FLAC evidence in a versioned metadata migration. Never edit historic `SOURCES.txt` in-place.
- Existing staged new-rip Genre and reviewed single-/multidisc revisions from PRs #117 and #118 remain unchanged.

## Acceptance

### Tower results — 2026-11-27

| Fixture | Read-only preview result |
| --- | --- |
| Anastacia — *Freak of Nature* | MusicBrainz release genre `pop` normalized to `Pop`, limited confidence (1/1). |
| Carmen Gomes — *Desire* | MusicBrainz reported `no_genre`. No genre was proposed. |
| Jean Michel Jarre — *Équinoxe*, catalog `800 025-2` | MusicBrainz reported `no_genre`. Discogs release `4709815` was classified based on matching catalog number and CD format. Its raw claims were Electronic, Experimental, Ambient and Synth-pop. OSCAR proposed Electronic and Ambient, each at limited confidence (1/1). |

The operator confirmed these results in the Tower UI. They cover a positive claim, missing genre data and an applicable Discogs claim. They do not establish physical pressing identity, archive write acceptance or conflicting-provider coverage.


On Unraid, first re-import Collection if needed. Use **Carmen Gomes — Desire**, optional exact Discogs release ID only if physically reviewed and the Discogs PAT configured. Confirm no-provider/unknown/mismatched-catalog cases fail safely or show abstentions. Repeat with Anastacia, verifying positive MB genres/votes. Verify the archived `SOURCES.txt` and FLACs remain byte-identical after each preview. The 2010 Bernstein/Mahler 11-CD box is a separate **inferred physical edition** and must not be published purely from a genre report.

Next milestone: store auditable provider observations + operator decision in a durable local ledger and generate SOURCES/manifest provenance for **new archive publications**, then independently design a safe versioned provenance revision for existing albums, adding explicit non-audio evidence allowlists and complete historical tests.

See the [genre evidence design](GENRE_EVIDENCE_CONFIDENCE_DESIGN.md) for proposed evidence snapshots, provider eligibility, review and publication requirements.
