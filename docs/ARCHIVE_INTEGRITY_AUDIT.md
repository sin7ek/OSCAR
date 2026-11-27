# Read-only archive integrity auditor (PR #52)

Run against a **dedicated OSCAR archive mount** with archive data available read-only:

```bash
python -m oscar.archive_audit /archive
python -m oscar.archive_audit /archive --json > audit-report.json
```

This is a diagnostic command, **not** a repair tool and not a background task.

Checks:
- Discover album directories containing top-level FLACs or manifests.
- Decode every active FLAC with `flac -t`; detect unreadable/empty audio and duplicate numbered tracks.
- Rehash each archived FLAC against the publishing manifest's SHA-256 and check the active file set.
- Check published CUE references stay inside the album and cover the album FLAC set; verify manifest CUE SHA-256.
- Rehash embedded `ExtractionEvidence/` files when listed in the manifest.
- Interpret explicit `SOURCE_TYPE` values from `SOURCES.txt`; for legacy OSCAR publisher manifests with published job/copy IDs, infer physical rip, otherwise UNKNOWN.
- Digital acquisitions do **not** need EAC logs or a CUE.
- Exclude `Verification/FailedAttempts` and `ExtractionEvidence` from active album discovery.
- Report PASS, PASS_WITH_WARNINGS or FAIL and JSON output.

Safety:
- **Never** alters or deletes original or archived audio, provenance, logs or manifests.
- This auditor does **not** conduct an independent AccurateRip or CTDB lookup. FLAC decoding alone is not proof of AccurateRip verification.
- Unknown provenance is reported explicitly rather than inferred from a CUE or a .accurip extension.
- A legacy archive without a manifest cannot have its original bytes independently corroborated, so it receives a documentation warning.
- The standalone CLI does not yet provide a web UI, scheduled runs, a persistent audit history, or clean-up.
- A published `SOURCE_TYPE: DIGITAL_ACQUISITION` release can achieve PASS if it has valid audio and a complete manifest despite lacking CUE/EAC logs.

Existing published directories are never migrated or overwritten. The auditor includes the already-published Anastacia release, but it has no embedded extraction evidence because it predates PR #51; this is a warning, not an excuse to change old archives.

Review `docs/ARCHITECTURE.md` and `docs/PROJECT_STATUS.md` for planned independent verification, operator workflows and integration.

The archive-wide audit reports audio held as loose playable files under `Verification`, `FailedAttempts` or `ExtractionEvidence` as `PLAYABLE_EVIDENCE` warnings. The audit leaves existing archives untouched.
