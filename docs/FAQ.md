# OSCAR — Frequently Asked Questions (FAQ)

Questions from users and the community about **OSCAR — Open Source CD Archiving & Ripping**.

> OSCAR is in active alpha development. Features described as goals or plans are not necessarily available in the current build. See the [README](../README.md) and [project status](PROJECT_STATUS.md) for current capabilities.

## 1. Does OSCAR automatically detect, rip, tag and organize CDs?

**Community question — lemmeinpls:**

> Just one question about OSCAR, how does it work exactly? Does it detect when a CD is read by the PC and automatically start ripping? Then it sorts it all in? If so I think the sorting will be the most powerful feature.

**Answer:**

That's pretty much exactly the idea! 😄

The ultimate goal for OSCAR is a simple **insert CD → rip → identify → organize** workflow.

OSCAR is intended to detect an inserted audio CD, identify the specific release using sources such as MusicBrainz, securely rip the audio to FLAC, verify the rip where possible, retrieve and enrich metadata, and organize the result into properly named folders with accurate tags and artwork.

And I agree: **sorting and metadata handling could become one of its most powerful features**, especially for compilations, classical music and releases where existing metadata is incomplete or inconsistent.

OSCAR offers three operating modes:

- **Best Guess:** inferred metadata selection, with explicitly opted-in archive automation behind strict safety gates.
- **Semi Automatic:** rip and verify, then explicitly approve inferred release and final archive publication as separate decisions.
- **Secure:** evidence-first identification and configurable strict review.

All modes retain the same audio integrity requirements; differing release certainty must be labelled accurately.

**One important design principle: OSCAR should never sacrifice accuracy for automation.** If release identification or metadata is uncertain, OSCAR should flag the result for review instead of blindly applying potentially incorrect tags or folder structures. The goal is a fully automated workflow you can actually trust.

**Current development status (2026-11-20):** OSCAR has a user-tested Go! path for extraction, verification, operator release selection, isolated tagged metadata copy, explicit archive publication and local Collection indexing (including two discs from one Boulez boxset). An opt-in Best Guess auto-publish path is gated separately and does not prove physical edition identity. Unattended insertion-triggered ripping, durable automatic orchestration and cleanup/recovery remain incomplete.

---

## 2. Can OSCAR help add missing Disc IDs to MusicBrainz?

Yes, for an operator-accepted, fully verified single-CD release. OSCAR uses the original physical disc TOC saved from libdiscid and prepares a MusicBrainz attachment page with the already accepted release as a filter. The operator chooses and confirms the correct medium on the MusicBrainz website. OSCAR never submits that external edit automatically. An exact Disc ID match still does not independently prove physical pressing identity.

## 3. Can OSCAR manage MusicBrainz and Discogs collections?

OSCAR already indexes locally published archives and supports initial read-only Discogs collection discovery via `OSCAR_DISCOGS_PAK`. MusicBrainz OAuth collections and cross-platform inventory comparison are **planned, not yet implemented**. Reserved MusicBrainz OAuth environment names are `OSCAR_MUSICBRAINZ_ID` (client ID) and `OSCAR_MUSICBRAINZ_CS` (client secret). Configuring them does not by itself enable a MusicBrainz account connection. A future deterministic, user-reviewed edit-note generator will use known TOC and physical evidence, without requiring external AI.

---

Have another question? Open an issue or discussion in the [OSCAR GitHub repository](https://github.com/sin7ek/OSCAR).
