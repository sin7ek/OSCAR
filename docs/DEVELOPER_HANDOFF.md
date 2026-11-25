# OSCAR — Developer handoff

Reconciled 2026-11-25 through [#172](https://github.com/sin7ek/OSCAR/pull/172). The [dashboard](PROGRESS.md) shows progress by area. The [work document](PROJECT_STATUS.md) holds deployment records, exact Tower fixtures, decisions and milestone history.

## Starting a session

1. Read this file from [GitHub main](https://github.com/sin7ek/OSCAR/blob/main/docs/DEVELOPER_HANDOFF.md), then the work document, dashboard and relevant technical guide. Check current main, recent PRs and workflow runs.
2. Develop on a branch with focused tests and a PR. For an OSCAR change requested for Tower, follow CI and merge when green. Check the Linux/amd64 OCI revision of `ghcr.io/sin7ek/oscar:main` against the merge before telling the operator to pull. For a PR-only request, keep it open.
3. Record implementation, CI, registry and Tower acceptance separately. Update the three current-state documents after a meaningful milestone. Require explicit operator permission for destructive operations on Tower.

## Current baseline

- **Cleanup** inventories verified duplicates, retired publications, retained revisions and tracked jobs. Retained history can live outside the music library. #172 puts checking, result and eligible deletion controls in the selected single-disc revision row. Danger Zone can directly delete selected cleanup folders. Use [Cleanup](CLEANUP.md) for the exact gates.
- **CD-Extra** uses the full physical TOC for audio verification. Raw Mode 1 capture requires two matching reads. A verified data supplement can be attached to a matching active audio publication. Use [archive publishing](ARCHIVE_PUBLISHER.md) for the verification and provenance contracts.
- **Review and tagging** support identifier comparison, user-guided MusicBrainz Disc ID attachment, reviewed cover artwork and proposed `SOURCES.txt`. A matching Disc ID and passing audio verification are separate from physical edition certainty.
- **Archives and Collection** support date/country corrections, metadata generations, coordinated boxset changes and distinct release editions. See [archive lifecycle](ARCHIVE_METADATA_LIFECYCLE.md) and [multidisc revisions](MULTIDISC_ARCHIVE_REVISION.md).

Tower accepted the inline result and chain-protection message on both Anastacia generations, automatic CTDB through publication for *Get the Hits 2* (45/46), and separate Collection rows for both Équinoxe editions. See the [Tower evidence](PROJECT_STATUS.md#tower-acceptance--2026-11-25).

Collection can propose an explicitly approved `GENRE=Classical` write from a verified classical publishing profile when provider genre evidence is absent. Bulk scans and coordinated previews reuse MusicBrainz responses per run. Tower acceptance should time a repeated archive-wide scan and preview the Boulez/Mahler GENRE additions. See [multidisc revisions](MULTIDISC_ARCHIVE_REVISION.md#missing-classical-tags-and-scan-performance).

## Next on Tower

| Priority | Test | Existing evidence |
| --- | --- | --- |
| 1 | Check the in-progress message on a slower revision. Use a disposable fixture for any approved deletion test. | Both Anastacia rows show successful verification and explain why they are protected. |
| 2 | Fresh full rip of Cenobite *Machines in Motion*. Check two-read raw capture, then review the data supplement for the existing archive. | Tower audio matched CTDB 5/5 and AccurateRip v2 on 15 tracks. Old job `385f8276c19543f3a5355660aad664d5` has an 8,475-byte BIN and no verified capture record. Expected new capture is 61,755 sectors, 145,247,760 bytes. |
| 3 | Check folder navigation for both Équinoxe rows. Revisit the date, country and Electronic genre candidate for catalog `800 025-2` when MusicBrainz exposes the reviewed corrections. | Tower identifier comparison showed Discogs 4709815, the matrix variant and the country disagreement. |
| 4 | Preview a coordinated GENRE revision if the operator wants the genre written into FLAC tags. Check country revision integrity separately if both generations are available. Separately validate Mahler Disc 11's proposed SOURCES.txt. | Boulez LABEL passed on Tower. Both boxsets have completed country revisions, with DE read back on all 153 tracks and no embedded GENRE. Mahler Disc 11 recovery matched 17/17 AccurateRip v1 and v2. Collection now shows all 11 Mahler and 6 Boulez discs published with Classical classification. |
| 5 | Exercise the remaining acceptance checks for guided Disc ID attachment, cover source selection and upload, automatic CTDB on additional layouts, and DriveFit with real drives. | Individual results and limitations are in the [work document](PROJECT_STATUS.md#next-acceptance-checks). |

For first-time installs, the current Compose example is a draft. The reviewed onboarding guide and a fresh storage-layout acceptance test remain open.
