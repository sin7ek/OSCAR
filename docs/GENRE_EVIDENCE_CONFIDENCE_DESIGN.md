# Genre evidence and provenance design

## Current implementation

[Genre Evidence v1](GENRE_EVIDENCE_V1.md) is a read-only source comparison for a published release. It displays official MusicBrainz claims and optional catalog-matched Discogs claims, with source attribution, grouped evidence, abstentions and agreement. The existing [reviewed genre workflow](REVIEWED_GENRE_TAGGING.md) separately supports MusicBrainz tags and a Discogs genre fallback where matching CDs agree. New publications already record the genre source and an available Discogs release URL in `SOURCES.txt`, and store the source URL in the manifest.

This design covers richer evidence and approval history, possible additional eligible sources, and a reviewed publication path. Its proposed thresholds and automatic write policies require separate implementation and acceptance. Tower confirmed representative read-only provider comparisons and the 2,227-entry vocabulary cache. Conflicting-provider coverage and a live UI preview of a newly recognized subgenre remain open.

## Problem

MusicBrainz genre votes and Discogs styles are editorial claims. Album-level evidence can help with missing genres. Genre agreement does not establish pressing identity, rip verification or audio quality. Artist genres are too broad to determine the genre of a particular album.

## Sources and eligibility

- **MusicBrainz**: official `genres` and vote counts for the verified release first, release-group as fallback, never unreviewed arbitrary `tags` as genres. Record MBID, entity type, count, URL, fetched timestamp, tag-list snapshot hash, and match evidence.
- **Discogs**: read-only release-level `genres` + `styles`; do not compare an arbitrary master or adjacent pressing without cross-reference to catalog number, barcode, label and format. Its broad genre and specific style are separate raw claims.
- **Qobuz**: album-level genre, only through a permitted officially accessible service/authorized API. Verify API terms, application-key eligibility, retention and attribution **before building a connector**. A webpage/retail listing without a licensed API may at most become a manually cited operator-supplied reference.
- **Other sources**: label/artist's official album description; trusted specialist album reviews; library/store catalogs with identifiable edition and clear publication origin. No arbitrary scraping or artificial source-count inflation. Manual operator citations are a possible extension.
- **User curations**: explicit operator assertion is separately labelled `operator_approved`; distinguish it from public provider votes or independent confirmation.

Every observation must include `source_id`, `source_type`, exact URL or stable provider ID, `entity_scope` (physical release/release group/album/artist), release-match evidence, original genre/style string, canonical mapped genre(s), timestamp, API status, source-independence cluster and source reliability tier. Store unsuccessful queries as `no_genre` or `unavailable`—not as votes against a genre.

## Vocabulary and normalizing

- Preserve verbatim provider labels and use the cached MusicBrainz vocabulary, built-in spellings and explicit aliases to normalize names. For example, `Alt-Pop` becomes `Alternative Pop`. New web-only terms can remain explicit review candidates with their original spelling.
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
| high_confidence | at least 3 independent applicable album-level evidence clusters, clear compatible majority (e.g. >= 75%) and **no credible unresolved conflicting specific genre** | Candidate for recommendation under a future approved policy |
| medium_confidence | at least 2 independent compatible album-level clusters or majority with gaps/minor conflict | Recommend with explanation for explicit review |
| conflicting | roughly balanced credible clusters (e.g. 50/50), incompatible styles, uncertain album match, or serious contradictory expert evidence | Manual approval only, no automatic genre write |
| unknown | zero/one weak relevant cluster or no safe mapping | Keep Unclassified, show sources checked |

**These are design placeholders:** calibrate against a diverse operator-reviewed test corpus before promoting thresholds to a live rule. No false numerical precision. Some albums legitimately belong to several genres; require evidence per tag and distinguish broad parent genres from independently supported subgenres.

## Proposed workflow mapping

Actual OSCAR settings are `identification_mode=best_guess|semi_automatic|secure` and `secure_review_level=on_ambiguity|before_archive|every_step`. Documentation may call these Best Guess / Semi Secure / Secure, but do not invent a second product mode. Genre assurance does not upgrade or bypass physical-release identification gates.

- **Best Guess**: with explicit web-genre opt-in, a new tagged copy may receive a web genre automatically when the approved policy can verify an explicit field or an unambiguous link between the term and this album. Model scope alone is insufficient. Record the automatic decision and evidence. Continue with existing provider genres when web evidence is missing, unavailable or ambiguous.
- **Semi Automatic**: show the excerpt and URL for each proposed web genre and require explicit selection before tagging. Persist the accepted set and evidence snapshot.
- **Secure**: respect existing exact-release/physical-medium and `secure_review_level` gates. Require explicit reviewer assent for genre tagging before archiving until a separate operator-approved secure policy is defined. No unapproved provider claim can become definitive. Secure indicates conservative review policy, **not a claim that music genre has been objectively proven**.
- All modes: changes to already-published FLACs continue to require explicit versioned metadata revision with originals retained, never in-place rewriting.

## Web search and local model Tower pilot

**Status:** Standalone scripts validated the services on Tower. OSCAR now offers an [on-demand read-only preview](GENRE_EVIDENCE_V1.md#optional-web-evidence-preview) through the metadata UI and API, with integrated Tower acceptance pending. Approval, automatic tagging and archive publishing remain open.

- The OSCAR container queried SearXNG on `http://searxng:8080/search` for JSON results from DuckDuckGo, then sent the excerpts to `http://ollama:11434/api/chat`. The containers share the private Docker network `oscar-ai` with SearXNG reachable by container name. Ollama ran `ministral-3:3b` on Tower's CPU with `OLLAMA_NO_CLOUD=1`.
- Mistral Conversations with `mistral-small-2603` and the `web_search` tool was tested separately as a possible hosted opt-in provider.
- Search needs only public release identifiers such as artist, album title, year or catalog number. The configured search engine receives the query and Tower's outbound IP. Ollama processes excerpts locally. Omit ripped audio, logs, archive paths and credentials from search queries and analysis payloads.

| Trial | Observed result |
| --- | --- |
| Lower Class Brats — *The New Seditionaries* | The first end-to-end run took 27.9 s. It found Punknews but treated the band's street-punk history as an album claim and changed quote punctuation. |
| Tony Iommi — *From the Dark* | The 32.9 s run gave unsupported Heavy Metal, Hard Rock and Doom Metal proposals from the shown excerpts. The sentence describing the album as his heaviest does not supply a genre. A different excerpt supports broad Metal for review. |
| Flotsam and Jetsam — *Rats in the Temple* | Audio Ink Radio explicitly describes album-level Thrash Metal. Sonic Perspectives describes the band's power/thrash history. The 35.1 s run added Aggressive Metal without literal support. The evidence-ID run took 22.1 s and retained a band claim. The 6.9 s test with predefined candidates inverted the album and band scopes. |
| Nessa Barrett — *Tough Love* | Album of the Year labels the album Alt-Pop. The 49.6 s run added Markdown to the copied quote. The 20.6 s evidence-ID run missed the claim, and the 7.1 s predefined-candidate test recovered it. Dark romantic described aesthetics. |
| Mahler — *Symphonie No. 6*, Boulez / Wiener Philharmoniker, DG `445 835-2` | The review excerpt identified the recording and supplied no genre. The run returned an empty claims list in 10.5 s. “Classical Music” was a site name. |

Use the local vocabulary to discover genre names in excerpts without per-album keywords. The model can also suggest previously unknown terms for review. Return evidence IDs and have OSCAR retrieve the original excerpt. Confirm the raw term appears in the evidence before normalizing it. Preserve the distinction between album, artist, track and mood. The model's classification can guide review. Automatic Best Guess requires an independent check of the album link. Preserve existing provider genres when the optional search service fails or finds no usable evidence.

## Provenance storage and SOURCES.txt

For each applied web genre, include the original term, normalized tag, short verbatim excerpt, source URL and the automatic Best Guess or explicit approval decision. Bind this record to the published metadata snapshot. The proof-of-concept scripts did not write genre tags or provenance.

Published `SOURCES.txt` and the existing manifest fields provide a baseline for this design. A complete, archived snapshot of all provider claims and approvals remains open. Revision verification protects the original non-audio evidence and requires explicit authorization for permitted differences.

Proposed:
1. Store canonical `genre_evidence` payload in the archive **manifest** and local Collection (or a SHA-256-bound additional JSON evidence sidecar), including `model_version`/policy version, normalized tags, source URLs/IDs, original claims, vote counts, query timestamp, source match and independence assessment, agreement fractions, confidence category, operator action, reviewed timestamp and exact publication/proposal fingerprint. No credentials or authorization tokens.
2. Render a concise, auditable **Genre provenance** section in `SOURCES.txt`, e.g.:

   `Genre: Jazz | assurance: medium | decision: operator_approved | sources: MB(release:none), Discogs(release:Jazz), Qobuz(album:Jazz) | checked_at: ...`

   Use complete citations/IDs in structured manifest, not misleading abbreviations as the sole record. Record independently sampled sources and abstentions.
3. **Do not silently modify SOURCES.txt or append sidecars in an existing published generation.** Add these only in a newly staged and verified generation after operator approval. Change the metadata-only migration's evidence verifier to allow a **strict, fingerprinted, journal-approved difference only in genre provenance fields/SOURCES**, preserving CUE/logs/artwork/extraction evidence byte for byte. Existing legacy revisions' historical verification must remain compatible with unchanged SOURCES; any unexpected non-audio edit still fails. Provenance-only updates must also be versioned.
4. `GENRE` in FLAC remains one Vorbis value per genre; no fake confidence value inside `GENRE`. Confidence/provenance may optionally be exposed via separately named tags in a future decision, but canonical evidence lives in manifest + SOURCES.
5. Changes to confidence or provider votes cannot retroactively alter archived decisions. Refresh creates a new evidence snapshot and review, never rewriting historical manifests.

## Proposed acceptance milestones

1. Extend the existing evidence model and normalizer with human-reviewed cases (Anastacia/Pop, Carmen Gomes/unknown or Jazz with evidence, Baroque broad-vs-style, electronic/hardcore, mixed compilations), explicit conflicting and duplicated-source tests.
2. Review the existing MusicBrainz and Discogs adapters on Tower and record representative provider responses. Consider an opt-in Qobuz adapter only after API and terms verification.
3. Extend the existing comparison UI with durable review and confirmation. Distinguish Best Guess/Semi Automatic/Secure settings, while keeping physical identity gates.
4. Persist provenance in new-rip `manifest.json` + `SOURCES.txt`, with SHA integrity and stable format version.
5. Add approved versioned provenance+genre revisions to existing single-CD / coordinated boxset, with full negative integrity tests, double-revision historical lineage and read-only Unraid acceptance.
6. Calibration: count editor disagreements/false positives and review ambiguous examples before enabling any automatic high-confidence tagging policy.

**Non-goal:** automatically adding crowd-sourced genres to MusicBrainz or Discogs; physical archive splitting; scraping sites without permission; claiming 3/5 consensus is a statistically calibrated probability.
