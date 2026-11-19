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

We also plan three operating modes:

- **Full Automatic:** Insert a CD and let OSCAR handle the entire workflow, with uncertain results safely held for review.
- **Semi-Automatic:** Choose which steps run automatically and which require your approval.
- **Full Manual:** Retain control over every step.

**One important design principle: OSCAR should never sacrifice accuracy for automation.** If release identification or metadata is uncertain, OSCAR should flag the result for review instead of blindly applying potentially incorrect tags or folder structures. The goal is a fully automated workflow you can actually trust.

**Current development status:** OSCAR already has an experimental, explicitly triggered CD-ripping workflow into staging, alongside metadata review and tagging features. However, automatic CD-insertion detection and the full unattended detect-to-archive workflow are **not yet implemented**. Automatic archive publishing is also not available yet. These are development goals, not current capabilities.

---

Have another question? Open an issue or discussion in the [OSCAR GitHub repository](https://github.com/sin7ek/OSCAR).
