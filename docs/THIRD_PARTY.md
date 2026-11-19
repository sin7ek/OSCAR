# Third-party projects, acknowledgements and licensing

OSCAR (Open Source CD Archiving & Ripping) would not exist without the work of other open-source developers, maintainers and volunteer music-data contributors. **Thank you.** This document credits the projects actually used by the current prototype, while distinguishing services, inspiration and future work.

**Important:** OSCAR's own source code currently declares the MIT licence in [LICENSE](../LICENSE). That declaration does **not** replace or override the licences of dependencies, standalone command-line tools, Debian packages, hosted databases or cover images. This is an acknowledgment and an initial inventory, **not** a complete legal compliance audit. Verify licences and accompanying notice/source obligations for the exact versions included in every distributed image.

## Core upstream projects currently used

| Project | OSCAR usage | Upstream | Upstream licensing information |
| --- | --- | --- | --- |
| **cyanrip**, by cyanreg and contributors | Secure CD extraction, original CUE/log, AccurateRip v1/v2 checksum evidence and FLAC output; run as a separate command-line program | [github.com/cyanreg/cyanrip](https://github.com/cyanreg/cyanrip) | [Upstream license](https://github.com/cyanreg/cyanrip/blob/master/LICENSE.md): LGPL-2.1; verify the exact installed Debian package |
| **FLAC**, maintained by Xiph.Org and contributors | The Free Lossless Audio Codec; OSCAR invokes the standalone `flac -t` tool to test FLAC integrity | [github.com/xiph/flac](https://github.com/xiph/flac) · [official licensing](https://xiph.org/flac/license.html) | Different components have different licences: libFLAC libraries are Xiph/BSD-like; official command-line tools have been distributed under GPL terms. Check the exact package notices |
| **libdiscid**, maintained by MetaBrainz contributors | Read CD table of contents and generate MusicBrainz Disc IDs | [github.com/metabrainz/libdiscid](https://github.com/metabrainz/libdiscid) · [documentation](https://musicbrainz.org/doc/libdiscid) | LGPL-2.1-or-later |
| **Mutagen**, by the Quod Libet team and contributors | Read and write Vorbis comments in staged FLAC copies; inspect stored tags and audio STREAMINFO MD5 | [github.com/quodlibet/mutagen](https://github.com/quodlibet/mutagen) | [GPL-2.0-or-later](https://github.com/quodlibet/mutagen/blob/main/pyproject.toml) — **requires a packaging/distribution compliance review** |
| **FastAPI**, by Sebastián Ramírez and contributors | OSCAR's HTTP API and browser backend | [github.com/fastapi/fastapi](https://github.com/fastapi/fastapi) | MIT |
| **Uvicorn**, by its maintainers and contributors | OSCAR's ASGI HTTP application server | [github.com/Kludex/uvicorn](https://github.com/Kludex/uvicorn) | BSD-3-Clause |
| **Pydantic**, by its maintainers and contributors | API request validation and configuration data models | [github.com/pydantic/pydantic](https://github.com/pydantic/pydantic) | [Upstream license](https://github.com/pydantic/pydantic/blob/main/LICENSE): MIT (review installed version and transitive dependencies) |
| **Python**, Python Software Foundation and contributors | Primary application language/runtime | [python.org](https://www.python.org/) | [PSF licence](https://docs.python.org/3/license.html) |
| **Debian**, its maintainers and package communities | Base operating system and packaged audio tools inside the current Docker image | [debian.org](https://www.debian.org/) | Each distributed Debian package has its own licence, copyright and notice terms |

The exact currently declared Python dependencies are in [pyproject.toml](../pyproject.toml), and the container's Debian packages are specified in [Dockerfile](../Dockerfile). This list covers **direct** dependencies and the most visible upstream tools, not every transitive package automatically installed by `pip` or `apt`.

## Public music-data and artwork services

These are external services and data sources, **not OSCAR's bundled libraries**:

- **[MusicBrainz](https://musicbrainz.org/)** and the **[MetaBrainz Foundation](https://metabrainz.org/)**: artists, releases, recordings, composition works, relationships, aliases and MusicBrainz IDs. Thanks to the maintainers and volunteer editors. [MusicBrainz data licensing](https://musicbrainz.org/doc/About/Data_License) distinguishes core data (mostly CC0) from supplementary content with different conditions, including CC BY-NC-SA. A web API being accessible does not mean all data has one uniform licence.
- **[Cover Art Archive](https://coverartarchive.org/)**, a collaboration between **[MusicBrainz](https://musicbrainz.org/)** and the **[Internet Archive](https://archive.org/)**: candidates for the front cover of the exact physical CD release. Artwork images can remain copyrighted by their respective rights holders; a visible candidate is not automatically licensed for redistribution or embedding.
- **[AccurateRip](http://www.accuraterip.com/)**: independent crowd-sourced reference checksums accessed **through cyanrip** in the present prototype. OSCAR parses the results reported in the original cyanrip log; it does not yet implement independent AccurateRip lookups. AccurateRip is credited as an external verification service, **not described as an OSCAR-bundled open-source component**.
- **[CTDB / CUETools Database](http://db.cuetools.net/)**: targeted for future independent verification, **not integrated in the current prototype**.

## Inspiration and related tools (not currently incorporated into OSCAR)

- **[Automatic Ripping Machine (ARM)](https://github.com/automatic-ripping-machine/automatic-ripping-machine)**: inspiration and a previously tried automatic CD ripping workflow; **not** an incorporated OSCAR module.
- **[MusicBrainz Picard](https://picard.musicbrainz.org/)**: an important open-source reference for metadata review and tagging, but **not** currently embedded in OSCAR.
- **[beets](https://beets.io/)**: a separate open-source music library manager in the broader user workflow. OSCAR is **not** using beets as its rip or tagging engine.
- **[Chromaprint](https://acoustid.org/chromaprint)** and **[AcoustID](https://acoustid.org/)**: potential future audio-fingerprint assistance; **not yet integrated**.

We should not imply affiliation, endorsement, sponsorship, or that the named maintainers contributed code to OSCAR directly. Credits describe dependencies, public-service data or inspiration, as indicated.

## Obligations before a stable public release

1. **Audit the actual Docker image**, not only the top-level package manifest: record each `pip` dependency and Debian/OS library/tool, exact package version, SPDX licence, upstream URL and whether it is embedded, dynamically linked, or invoked as a separate executable.
2. **Review Mutagen GPL compatibility and the packaging model** for OSCAR's MIT-labelled application, and review cyanrip/libdiscid LGPL and FLAC command-line licences. The way software is combined and distributed matters; consult competent licensing guidance if needed. Do not assume that listing the credits cures possible licence noncompliance.
3. Include any required **copyright notices, complete applicable licence texts, source-code availability or redistribution notices** with release packages/container images. Maintain a versioned third-party notices inventory or generated SBOM (SPDX/CycloneDX) as the project matures.
4. Keep **MusicBrainz data rights and cover-image copyright** separate from software licences; do not silently treat retrieved cover artwork as CC0.
5. Update this document each time we add a rip engine, verification backend, audio-fingerprint library, service or major dependency, and provide proper acknowledgements in release notes when appropriate.
6. Keep OSCAR's own source code and external upstream provenance clearly distinguishable.

*OSCAR preserves music using technology built by many people. Giving them credit is part of preserving that heritage.*
