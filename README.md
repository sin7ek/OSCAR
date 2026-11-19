# OSCAR
**Open Source CD Archiving & Ripping**

*Preserve every note.*

Automated, archival-grade CD ripping with AccurateRip/CTDB verification, MusicBrainz metadata, FLAC, CUE sheets, and classical music support.

> Dedicated to Oscar, whose love of music inspired this project.

## The Story Behind OSCAR

My dad, Oscar, passed away on November 19, 2021, at the age of 64. Throughout his life, he faced many challenges, including bipolar disorder, brainstem infarcts, and ultimately glioblastoma, an aggressive brain tumour.

But there was so much more to him than his illnesses.

Besides his love for us, his children, one of his greatest passions was music. His taste was wonderfully eclectic, ranging from Eurodance to Anastacia and Roxy Music. But his greatest musical love was classical music.

At his funeral, we listened to the full 27:34 minute *Adagio* from Bruckner's Ninth Symphony, performed by the Royal Concertgebouw Orchestra under Riccardo Chailly. And because this was Oscar, we played it through **his own amplifier and loudspeakers**, which we had brought to the funeral home. It felt only right.

After his passing, he left me something else: **more than 1,000 CDs** - and I had absolutely no idea what to do with them.

I couldn't bring myself to get rid of them, but manually ripping a thousand CDs wasn't particularly appealing either. I experimented with Automatic Ripping Machine, but even that required more manual work than I could put in.

So, naturally, I did what any reasonable person would do: **I spent five years not solving the problem.**

Eventually, with a little help from ChatGPT, I started building something of my own: **OSCAR — Open Source CD Archiving & Ripping**. An open-source project dedicated to preserving music collections like my father's, automatically, accurately, and with the care they deserve.

On November 19, 2026, exactly five years after my dad passed away, OSCAR successfully ripped and AccurateRip-verified its very first audio track.

Five years, still thousand CDs to go, and quite a few lines of code later, OSCAR was finally ripping music again. Something my dad always enjoyed doing.

**OSCAR lives on.**

*For my dad. Preserve every note.*

### OSCAR's first CD — November 19, 2026

The first CD OSCAR ripped in full was **George Frideric Handel — [Water Music / Music for the Royal Fireworks](https://musicbrainz.org/release/4a8cbc25-21a0-4a24-8bb8-2f388164d544)**, performed by **Le Concert des Nations** under **Jordi Savall**.

It was the 1999 **Astrée Auvidis** CD, catalogue number **ES 99220**, with 28 tracks ([MusicBrainz Disc ID](https://musicbrainz.org/cdtoc/ROkQlooU5tDdgVZOkfXXTy.S4oU-): `ROkQlooU5tDdgVZOkfXXTy.S4oU-`).

All **28 tracks** were extracted to FLAC without reported ripping errors. Cyanrip reported **AccurateRip v1 and v2 matches for every track** (28/28 for both), and every FLAC passed a decode-integrity test. The original CUE and rip logs were retained in staging.

This was OSCAR's **first successful complete real-world rip**, exactly five years after Oscar's death. It was not yet an automatically tagged or published archive, and OSCAR's independent verification engine is still being developed.

## Status
**v0.1.0-alpha: read-only metadata scaffold plus an opt-in experimental cyanrip staging rip.** This prototype can extract a test CD only after explicit configuration and confirmation, into a newly created staging directory. No independently verified archive, publishing, or cleanup is implemented. AccurateRip/CTDB evidence must be proven on hardware before claims of verified operation.

## Goals
- Detect audio CDs, record drive identity, read offset and table of contents (including pregaps and HTOA capability).
- Rip lossless FLAC using a proven secure ripping engine (cyanrip is a candidate).
- Verify audio using AccurateRip v1/v2, CTDB (tooling feasibility to be established on Linux), FLAC decoding, hashes and rip logs.
- Identify the **specific physical release** using MusicBrainz disc IDs, barcode, label/catalog numbers and artwork.
- Support classical works, movements, composers, conductors, orchestras, performers and multidisc boxsets.
- Produce preserved original CUE information, usable FLAC CUE sheets, `SOURCES.txt` and structured `manifest.json`.
- Stage, review, archive and clean up without ever risking an existing collection.

## Safety principles
1. Keep source audio and original logs immutable; metadata edits occur only on staged copies.
2. Audio-verification status and physical-release identification status are independent.
3. No AccurateRip/CTDB entry is **unverified**, not a mismatch.
4. A database match does not prove a particular physical release.
5. Do not publish ambiguous metadata or failed rips automatically.
6. No destructive cleanup without confirmed archival integrity; cleanup is initially disabled.
7. Never automatically move or rewrite an existing Archive.

## Development
Python 3.11+:
```bash
python -m pip install -e '.[dev]'
python -m pytest -q
uvicorn oscar.api:app --host 127.0.0.1 --port 8080
```
The `/health` endpoint reports **scaffold status only**; it does not detect discs.

For common community questions, see the **[Frequently Asked Questions (FAQ)](docs/FAQ.md)**.

For a new development session, start with [Project status and handoff](docs/PROJECT_STATUS.md), then [Architecture](docs/ARCHITECTURE.md), [Metadata retry queue](docs/METADATA_QUEUE.md), [First experimental rip](docs/FIRST_RIP_STAGING.md), and [Milestone 01](docs/MILESTONE_01.md).

For completed staging jobs, [Staging verification](docs/STAGING_VERIFICATION.md) explains how OSCAR checks FLAC decoding, SHA-256 and cyanrip's logged AccurateRip results without modifying the original rip or claiming independent CTDB verification.

After a report passes, [Reviewed metadata and tagged staging copies](docs/METADATA_STAGING.md) describes selecting the exact MusicBrainz release, previewing classical relationships, and making separately tagged FLAC copies without changing the original rip or publishing an archive.

## Experimental rip token (Unraid / Portainer)

The experimental cyanrip staging rip requires an explicitly configured secret
token. Generate one on the Unraid host with:

```bash
openssl rand -hex 32
```

This produces 32 random bytes as 64 hexadecimal characters. Store the result
as the `OSCAR_RIP_TOKEN` stack environment variable in Portainer. Reference
the variable in the existing compose definition without committing the secret:

```yaml
environment:
  OSCAR_ENABLE_RIPPING: "1"
  OSCAR_RIP_ROOT: /staging
  OSCAR_RIP_TOKEN: ${OSCAR_RIP_TOKEN}
```

These lines illustrate the relevant settings, not a replacement stack.
Keep your existing configuration, persistent `/config`, device mappings,
and the isolated `/mnt/user/ai-workspace:/staging:rw` mount.
The token is requested by the test-rip UI and is not a hash of a password.
Environment values can be read by people with Docker/Portainer admin access;
do not paste the token into GitHub, issue reports or screenshots. The app has
no built-in user login, so restrict network access as well.

See [First experimental rip](docs/FIRST_RIP_STAGING.md) for prerequisites,
permissions, logging, and safe staged output.

## Target archive layout
```text
Archive/<label>/[catalog] <release title> (<year>)/
  *.flac
  album.cue
  original-ripper.cue
  folder.jpg
  SOURCES.txt
  manifest.json
  Verification/
```
This is a proposed layout, not a deployed configuration.

## Credits & acknowledgements

OSCAR stands on the shoulders of remarkable open-source projects and communities. **Thank you to the developers, maintainers and contributors whose work makes OSCAR possible.**

The core CD-ripping engine is **[cyanrip](https://github.com/cyanreg/cyanrip)**. Other essential building blocks include **[FLAC](https://xiph.org/flac/)**, **[libdiscid](https://github.com/metabrainz/libdiscid)**, **[Mutagen](https://github.com/quodlibet/mutagen)**, **[FastAPI](https://github.com/fastapi/fastapi)**, **[Uvicorn](https://github.com/Kludex/uvicorn)** and **[Pydantic](https://github.com/pydantic/pydantic)**. We also thank the **[MusicBrainz / MetaBrainz](https://musicbrainz.org/)** community and the **[Cover Art Archive](https://coverartarchive.org/)** collaboration with the **[Internet Archive](https://archive.org/)** for the metadata and cover-art ecosystem, and acknowledge **[AccurateRip](http://www.accuraterip.com/)** for its checksum reference service used by cyanrip.

See **[Third-party projects & acknowledgements](docs/THIRD_PARTY.md)** for links, roles, relevant licences, and a clear distinction between bundled components, external services, inspiration and planned integrations.

## License
OSCAR's own code is currently declared **MIT** — see [LICENSE](LICENSE). Third-party components and data retain their respective licences and rights. The project's Docker distribution still needs a full dependency/notice and licence-compatibility review before a stable public release; see [Third-party projects & acknowledgements](docs/THIRD_PARTY.md).

## Classical metadata review

[Classical Metadata v2](docs/CLASSICAL_METADATA_V2.md) separates operator-reviewed sections of the physical CD from MusicBrainz's canonical work/parent relationships. The review can optionally add explicitly checked movements and cached English aliases. After confirmation it creates only separate new FLAC copies in staging, without altering the first rip or previous copies.

## Archive review, cover art, CUE and multiple drives

[Archive review & multidrive](docs/ARCHIVE_REVIEW_AND_MULTIDRIVE.md) adds a read-only metadata consistency checker (MusicBrainz Work vs Recording, potential duplicate links, available track durations), exact physical-release Cover Art Archive candidate, original-index-preserving CUE preview and responsive mobile track cards. Ordinary pop, house, compilations and mixed-genre releases use the original tagging pathway, without requiring Classical v2. Multiple configured optical drives already have independent running jobs; an optional `OSCAR_MAX_CONCURRENT_RIPS` safety cap (default 3, range 1–16) and parallel-drive dashboard are available. No automatic archive publishing or persistent job queue yet.
