# Proposal: Genre Evidence & Confidence Engine

**Status:** design proposal, **not implemented**, 2026-11-22. This document records the operator's requested direction and testable safety requirements; confidence thresholds and provider eligibility need a separate implementation/review decision. Physical Classical/Popular archive splitting remains opt-in and undecided.

## Problem

OSCAR currently accepts normalized official MusicBrainz release/release-group `genres` as candidate GENRE values. MusicBrainz genres are user-contributed tags with vote counts, not objective physical-release facts. This was sufficient for Anastacia's `Pop` Unraid acceptance, but does not solve missing/weak genre evidence for Carmen Gomes Inc. – `Desire`. Generic artist genres must never silently determine an album's genre.

Genre confidence is **not** rip verification, disc identity proof, metadata edition confidence, or audio quality. They have separate assurance and provenance fields. No provider alone proves the exact physical pressing.

## Sources and eligibility

- **MusicBrainz**: official `genres` and vote counts for the verified release first, release-group as fallback, never unreviewed arbitrary `tags` as genres. Record MBID, entity type, count, URL, fetched timestamp, tag-list snapshot hash, and match evidence.
- **Discogs**: read-only release-level `genres` + `styles`; do not compare an arbitrary master or adjacent pressing without cross-reference to catalog number, barcode, label and format. Its broad genre and specific style are separate raw claims.
- **Qobuz**: album-level genre, only through a permitted officially accessible service/authorized API. Verify API terms, application-key eligibility, retention and attribution **before building a connector**. A webpage/retail listing without a licensed API may at most become a manually cited operator-supplied reference.
- **Other sources**: label/artist's official album description; trusted specialist album reviews; library/store catalogs with identifiable edition and clear publication origin. No arbitrary scraping or artificial source-count inflation. Manual operator citation is supported.
- **User curations**: explicit operator assertion is separately labelled `operator_approved`; distinguish it from public provider votes or independent confirmation.

Every observation must include `source_id`, `source_type`, exact URL or stable provider ID, `entity_scope` (physical release/release group/album/artist), release-match evidence, original genre/style string, canonical mapped genre(s), timestamp, API status, source-independence cluster and source reliability tier. Store unsuccessful queries as `no_genre` or `unavailable`—not as votes against a genre.

## Vocabulary and normalizing

- Preserve original verbatim provider labels, normalize only to a versioned controlled OSCAR genre/style vocabulary (e.g. `Classical; Baroque`, `Electronic; Hardcore; Gabber`, `Jazz`).
- Broader and narrower labels are **compatible**: `Jazz` and `Vocal Jazz` are not a contradictory 50/50 split. Likewise `Electronic`, `Hardcore`, `Gabber` may be nested. Independently infer a specific genre only if evidence supports that specificity.
- For a compilation/mixed-mode boxset, release-level genre may be a broad classification and per-track genres must not be invented from release metadata.
- MusicBrainz and Discogs sometimes reuse user-entered tags. Multiple pages derived from the same upstream provider count as **one independence group**, not independent corroboration.
- Do not erase existing approved FLAC genres based on a new provider result. Conflict goes to metadata review.

## Confidence, support and decisions (proposed policy, not statistical calibration)

Calculate per canonical genre: `sources_checked`, `sources_with_applicable_claims`, `independent_clusters`, `clusters_supporting_genre`, `clusters_conflicting`, and a bounded weighted support score; disclose these values in UI.

**A majority percentage is agreement among applicable independent evidence, not a probability of truth.** Example: 3 of 5 independent applicable sources say Jazz = 60% agreement, not `P(Jazz)=0.60`. Five checked sources with one `no_genre` and three Jazz give 3/4 = 75% among actual genre claims, but the missing result also reduces coverage.

Suggested initial gate:

| Outcome | Evidence / conflict requirement | Action |
| --- | --- | --- |
| high_confidence | at least 3 independent applicable album-level evidence clusters, clear compatible majority (e.g. >= 75%) and **no credible unresolved conflicting specific genre** | Eligible for automatic recommendation; write rules still mode-dependent |
| medium_confidence | at least 2 independent compatible album-level clusters or majority with gaps/minor conflict | Recommend with explanation; explicit approval required outside Best Guess policy |
| conflicting | roughly balanced credible clusters (e.g. 50/50), incompatible styles, uncertain album match, or serious contradictory expert evidence | Manual approval only, no automatic genre write |
| unknown | zero/one weak relevant cluster or no safe mapping | Keep Unclassified, show sources checked |

**These are design placeholders:** calibrate against a diverse operator-reviewed test corpus before promoting thresholds to a live rule. No false numerical precision. Some albums legitimately belong to several genres; require evidence per tag and distinguish broad parent genres from independently supported subgenres.

## Workflow mapping (genre trust != physical-edition trust)

Actual OSCAR settings are `identification_mode=best_guess|semi_automatic|secure` and `secure_review_level=on_ambiguity|before_archive|every_step`. Documentation may call these Best Guess / Semi Secure / Secure, but do not invent a second product mode. Genre assurance does not upgrade or bypass physical-release identification gates.

- **Best Guess**: auto-propose high-confidence genres; *automatic* write to new staging copies can be opt-in when the release workflow already authorizes it; mark inference and confidence in provenance. Unverified edition stays unverified. Low/conflicting data remains empty or pending.
- **Semi Automatic**: show evidence comparison for reviewed physical release; require operator approval for medium, low/conflicting and optional high if settings dictate. Persist accepted candidate and evidence snapshot.
- **Secure**: respect existing exact-release/physical-medium and `secure_review_level` gates. Require explicit reviewer assent for genre tagging before archiving until a separate operator-approved secure policy is defined. No unapproved provider claim can become definitive. Secure indicates conservative review policy, **not a claim that music genre has been objectively proven**.
- All modes: changes to already-published FLACs continue to require explicit versioned metadata revision with originals retained, never in-place rewriting.

## Provenance storage and SOURCES.txt

**Current actual behavior:** `src/oscar/archive_publish.py` creates a human-readable `SOURCES.txt`, and `manifest.json` includes release IDs, processing profile and source metadata. Both are part of published non-audio integrity evidence. Existing single-CD and boxset verification demands non-FLAC evidence remains byte-identical between old/new generations.

Proposed:
1. Store canonical `genre_evidence` payload in the archive **manifest** and local Collection (or a SHA-256-bound additional JSON evidence sidecar), including `model_version`/policy version, normalized tags, source URLs/IDs, original claims, vote counts, query timestamp, source match and independence assessment, agreement fractions, confidence category, operator action, reviewed timestamp and exact publication/proposal fingerprint. No credentials or authorization tokens.
2. Render a concise, auditable **Genre provenance** section in `SOURCES.txt`, e.g.:

   `Genre: Jazz | assurance: medium | decision: operator_approved | sources: MB(release:none), Discogs(release:Jazz), Qobuz(album:Jazz) | checked_at: ...`

   Use complete citations/IDs in structured manifest, not misleading abbreviations as the sole record. Record independently sampled sources and abstentions.
3. **Do not silently modify SOURCES.txt or append sidecars in an existing published generation.** Add these only in a newly staged and verified generation after operator approval. Change the metadata-only migration's evidence verifier to allow a **strict, fingerprinted, journal-approved difference only in genre provenance fields/SOURCES**, preserving CUE/logs/artwork/extraction evidence byte for byte. Existing legacy revisions' historical verification must remain compatible with unchanged SOURCES; any unexpected non-audio edit still fails. Provenance-only updates must also be versioned.
4. `GENRE` in FLAC remains one Vorbis value per genre; no fake confidence value inside `GENRE`. Confidence/provenance may optionally be exposed via separately named tags in a future decision, but canonical evidence lives in manifest + SOURCES.
5. Changes to confidence or provider votes cannot retroactively alter archived decisions. Refresh creates a new evidence snapshot and review, never rewriting historical manifests.

## Proposed acceptance milestones

1. Pure classification/evidence model + normalizer, human-reviewed cases (Anastacia/Pop, Carmen Gomes/unknown or Jazz with evidence, Baroque broad-vs-style, electronic/hardcore, mixed compilations), explicit conflicting and duplicated-source tests.
2. MusicBrainz vote provenance and Discogs read-only release-level evidence adapters; opt-in Qobuz adapter only after API/terms verification. Mocked provider failure and rate-limiting tests.
3. Review UI with per-source claims, independence, confidence and confirmation. Distinguish Best Guess/Semi Automatic/Secure settings, while keeping physical identity gates.
4. Persist provenance in new-rip `manifest.json` + `SOURCES.txt`, with SHA integrity and stable format version.
5. Add approved versioned provenance+genre revisions to existing single-CD / coordinated boxset, with full negative integrity tests, double-revision historical lineage and read-only Unraid acceptance.
6. Calibration: count editor disagreements/false positives and review ambiguous examples before enabling any automatic high-confidence tagging policy.

**Non-goal:** automatically adding crowd-sourced genres to MusicBrainz or Discogs; physical archive splitting; scraping sites without permission; claiming 3/5 consensus is a statistically calibrated probability.
