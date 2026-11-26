# External verification (experimental)

Related: #183. This read-only CLI does not create a rip job or publish an album.

Run `python -m oscar.external_verification /path/to/album` in an OSCAR environment with a read-only album mount. Redirect stdout to a report outside the album. Set `OSCAR_CTDB_EXECUTABLE` to the existing absolute CTDB verifier path. Each FLAC must have numeric DISCNUMBER, TOTALDISCS, TRACKNUMBER and TOTALTRACKS (per disc). Each disc must be complete and CD PCM (44.1 kHz, 16-bit stereo, 588 samples per sector) to attempt CTDB.

The temporary CUE assumes consecutive split tracks at INDEX 01, no hidden audio or omitted pregaps. This is a candidate layout, not physical TOC evidence. A database match is scoped to that candidate and does not establish physical pressing, ownership or original ripping method. No match does not prove a bad rip. AccurateRip is explicitly not performed. Existing CUE evidence, alternative layouts, per-track database results, UI, persisted evidence and archive publishing are follow-up work. Do not overwrite existing SOURCES.txt or promote physical rip status based on this CLI. Run unit tests and validate against known real discs before production adoption.
