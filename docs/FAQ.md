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

Yes, for an operator-accepted release with a fully verified staged rip. For a multidisc set, select the compatible physical disc in Review if more than one matches. OSCAR uses the original physical disc TOC saved from libdiscid and prepares a MusicBrainz attachment page with the already accepted release as a filter. The operator chooses and confirms the correct medium on the MusicBrainz website. OSCAR never submits that external edit automatically. An exact Disc ID match still does not independently prove physical pressing identity.

## 3. Can OSCAR manage MusicBrainz and Discogs collections?

OSCAR already indexes locally published archives and supports initial read-only Discogs collection discovery via `OSCAR_DISCOGS_PAK`. MusicBrainz OAuth collections and cross-platform inventory comparison are **planned, not yet implemented**. Reserved MusicBrainz OAuth environment names are `OSCAR_MUSICBRAINZ_ID` (client ID) and `OSCAR_MUSICBRAINZ_CS` (client secret). Configuring them does not by itself enable a MusicBrainz account connection. A future deterministic, user-reviewed edit-note generator will use known TOC and physical evidence, without requiring external AI.


## 4. What should I do if a CD behaves unexpectedly during batch ripping?

Start each disc with **Go!**. You can rip on multiple configured drives and review earlier jobs later. Keep the original staging files and logs until you have checked the published copy.

| What happened? | What to do |
| --- | --- |
| One track stalls or reports read errors | Keep the first job and its log. Try the affected track on another drive. Where supported, use Track Recovery to compare or replace the affected track in a separate candidate and independently verify the result. |
| AccurateRip or CTDB has no reference | Keep the rip in staging for review. A missing reference leaves the audio unconfirmed by that database. For an explicit mismatch, try another read, preferably on another drive. |
| Audio matches but the edition looks wrong | Defer publication of that job. Compare the physical catalog number, barcode or matrix/runout with the release candidates. Audio verification and edition identification are separate checks. |
| CD-Extra, hidden audio before track 1 or an unexpected track count | Check the disc layout and CUE. Verify that any hidden audio or data session you intend to preserve was actually captured. Published audio checks cover the audio that was extracted. |
| A drive disconnects or slows down during parallel rips | Keep the interrupted job and try the disc on another drive. If the slowdown occurs only with concurrent jobs, compare one active rip with several active rips. |
| A boxset is incomplete or the disc is assigned to the wrong edition | Before publication, check the release, physical disc number and total discs. Keep ambiguous jobs in staging until you can identify the physical disc. |

Set aside discs that need another read or a metadata decision and continue with the next disc. See [staging verification](STAGING_VERIFICATION.md), [archive publishing and CD-Extra](ARCHIVE_PUBLISHER.md) and the [automation roadmap](AUTOMATION_ROADMAP.md).

---

Have another question? Open an issue or discussion in the [OSCAR GitHub repository](https://github.com/sin7ek/OSCAR).
