# Citycat Club — Essential Dance Traxx (1997): missing MusicBrainz physical release

**Status (2026-11-19):** OSCAR's new MusicBrainz catalog-number search for `CCC 97001` returned **zero candidates** in the user's live Unraid test. The user's screenshot shows both search fields populated, but the visible "0 candidate(s)" result is **not enough to establish that the title search was also run**: those buttons initiate separate searches. Search the title separately before entering a new release, and check alternate spellings. Public MusicBrainz web searches did not identify a matching physical release at research time.

## Exact hardware evidence, preserve without modifications

- Original physical CD: **Various Artists — Essential Dance Traxx**; label **Citycat Club**; printed catalog number **CCC 97001**; 1997, Europe; single CD, compilation, 14 audio tracks.
- Original rip/staging job: `95dbf0da233d4a3887800a517a149b3c`
- MusicBrainz Disc ID from the original drive/TOC: `UNzDV9I7c4DxDxpasZu014z4sQs-`
- Hardware checks: 14/14 FLAC decoding and staged hashes passed; 14/14 cyanrip-reported AccurateRip v2 confidence 4; no v1 evidence. CUE/source audio remain untouched.
- The same Disc ID is also associated with **Ibiza Party**, a separate, **incorrect** physical release. That association is NOT evidence for the Citycat CD and must not be used to tag this job. A Disc ID may legitimately attach to more than one distinct release.
- **Unknown until verified from actual packaging:** barcode, exact label and distributor credits, release group/series association, physical cover and final track versions and printed spellings. Do **not** invent barcode, existing MusicBrainz track/recording/work IDs, or assign unrelated recordings just because title matches.

## Independent candidate tracklist (secondary source, not yet verified against physical CD)

An external resale listing explicitly states `Citycat Club – CCC 97001`, single CD compilation, 1997, Europe, and provides the following tracklist: https://www.2dehands.be/v/cd-s-en-dvd-s/cd-s-dance-en-house/m1966118971-cd-audio-essential-dance-traxx

1. Gala — Freed From Desire (Short Mix) — 3:31
2. Hole In One — Life's Too Short (Live At Paleis Soestdijk Mix) — 5:59
3. Party Cruiser — This Record Is Being Played In Clubs, Discolounges, House- Basement- Or Blockparties — 5:32
4. Flamman & Abraxas feat. MC Remsy — Good To Go (Radio Mix) — 3:31
5. Chestnut — Pot Of Gold (Subsonik Mix) — 5:22
6. Partision — Breathin' In — 6:43
7. Quadripart — Joy (Interpretations Of Joy By Secret Cinema) — 5:23
8. Diva Convention — Give It Love — 6:37
9. Secret Cinema — Timeless Altitude — 6:11
10. DJ Luciano — Funki — 6:12
11. Quadripart — (Make) Love (Remy & Gregor Sex Mix) (Edit) — 4:48
12. Paradise Club — Harmonix — 5:29
13. Ambergriz — Chase (Theme From Midnight Express) — 3:58
14. Brothers In Crime — Forever (Radio Edit) — 3:42

These titles/versions/durations are **reported by a reseller** and have NOT been checked against the physical disc/booklet or FLAC measured durations. Source spelling may differ from MusicBrainz capitalization and should be reviewed before submission. The listing mentions a Dance Traxx (3) series relationship; treat the relation as tentative until corroborated.

## Next safe steps (for user and next OSCAR chat)

1. In updated OSCAR, separately click **Search by title** for `Essential Dance Traxx`. The screenshot currently only demonstrates one of two independent queries returned zero; verify the title path.
2. Compare above 14 candidate tracks, mix titles, physical label, and any printed barcode with the user's CD and audio staging. Obtain actual measured track lengths from the staged rip before entering durations; don't treat reseller times as exact.
3. If no exact physical MusicBrainz release exists, use **MusicBrainz → Add Various Artists release** (https://musicbrainz.org/release/add), or **submit CD TOC / Add release** from a MusicBrainz disc-ID submission seeded from the actual CD. Enter media type CD, 14 tracks, printed catalog, documented 1997 release date (only precision supported by packaging/source), country/region when documented, and per-track primary artists. Preserve the true 14-track order; no guessed ISRC, barcode, MusicBrainz recording/work IDs.
4. If the MusicBrainz editor offers an **Add release from this CD TOC** action, use it: the real Disc ID/TOC can be attached on creation. Otherwise attach the CD TOC explicitly to the newly created release via a MusicBrainz Disc ID submission/Picard. Check that it is linked to the exact physical medium; do not remove the association from unrelated Ibiza Party solely because the TOC happens to match.
5. Add the evidence link and a concise edit note explaining physical ownership and source-vs-unverified details. Review MusicBrainz before submitting, avoid false recording relationships.
6. Once the correct MusicBrainz release UUID exists **and** the disc ID/14-track medium is linked, use OSCAR's Physical Release Comparison with original job `95dbf0da233d4a3887800a517a149b3c` and printed catalog `CCC 97001`. Proceed to **original MusicBrainz tagging** (standard/compilation policy), inspect the actual tagged FLACs, then Archive Review. No Classical v2.
7. Follow-up engineering in issue #40: Discogs/GnuDB fallback adapters and a first-class **missing-release review/submit** assistant with safe candidate evidence pack (never automatically publish unverified MusicBrainz metadata). Final archive publisher issue #39 remains unimplemented.

## MusicBrainz suggested edit note

> Adding the original 1997 CD compilation *Essential Dance Traxx*, Citycat Club, catalog CCC 97001, based on the physical CD in my collection and its independently ripped 14-track TOC. The release was not present in the MusicBrainz release searches by catalog number; a separate release with the same Disc ID/TOC is not this physical edition. Secondary tracklist source: https://www.2dehands.be/v/cd-s-en-dvd-s/cd-s-dance-en-house/m1966118971-cd-audio-essential-dance-traxx . Tracks, mixes, barcode and credits will be checked against the physical packaging before submission. No existing recordings/works are assigned unless positively verified.

References:
- https://musicbrainz.org/doc/How_to_Add_a_Release
- https://picard-docs.musicbrainz.org/en/v2.13/usage/attach_disc_id.html

**Status:** Recovery evidence prepared. No MusicBrainz release was created by OSCAR/ChatGPT, no tags written and no archive published.
