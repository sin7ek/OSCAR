"""Read-only integrity audit for existing OSCAR archive publications.

Runs with: python -m oscar.archive_audit /path/to/archive [--json]
No source or archive writes. No network calls. No unsupported AccurateRip/CTDB claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

_CUE_FILE = re.compile(r'^\s*FILE\s+"([^"\r\n]+)"\s+WAVE\s*$', re.I)
_NUMBER = re.compile(r"^(\d{1,3})\s*[-.]\s*")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_file(base: Path, relative: str) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    candidate = Path(relative)
    if candidate.is_absolute() or any(p in {"..", "."} for p in candidate.parts):
        return None
    current = base
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            return None
    return current if current.is_file() else None


def _provenance(folder: Path, manifest: dict) -> str:
    source = folder / "SOURCES.txt"
    if source.is_file() and not source.is_symlink():
        try:
            content = source.read_text(encoding="utf-8")
            matches = re.findall(
                r"(?im)^\s*SOURCE_TYPE\s*:\s*(PHYSICAL_CD_RIP|DIGITAL_ACQUISITION|HYBRID_REPAIRED_CD_RIP)\s*$",
                content,
            )
            if len(set(matches)) == 1:
                return matches[0]
        except (OSError, UnicodeError):
            pass
    # OSCAR's own publisher only accepts a verified optical staging rip.
    if manifest.get("status") == "published_verified" and manifest.get("job_id") and manifest.get("copy_id"):
        return "PHYSICAL_CD_RIP"
    return "UNKNOWN"


def _issue(items: list, code: str, message: str) -> None:
    items.append({"code": code, "message": message})


def audit_release(folder: Path, *, timeout: int = 180) -> dict:
    """Validate file and evidence integrity without changing the release."""
    folder = Path(folder)
    errors: list[dict] = []
    warnings: list[dict] = []
    manifest_path = folder / "manifest.json"
    manifest = {}
    if manifest_path.is_symlink():
        _issue(errors, "UNSAFE_MANIFEST", "Manifest is a symlink")
    elif manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("Manifest is not a JSON object")
        except (OSError, ValueError, UnicodeError) as exc:
            _issue(errors, "BAD_MANIFEST", str(exc))
            manifest = {}
    else:
        _issue(warnings, "NO_MANIFEST", "No OSCAR manifest is present")
    provenance = _provenance(folder, manifest)
    if provenance == "UNKNOWN":
        _issue(warnings, "UNKNOWN_PROVENANCE", "Source type is not reliably documented")

    audio = sorted(folder.glob("*.flac"))
    if not audio:
        _issue(errors, "NO_AUDIO", "No active FLAC files found")
    numbers = {}
    for f in audio:
        if f.is_symlink() or not f.is_file():
            _issue(errors, "UNSAFE_AUDIO", f.name)
            continue
        if f.stat().st_size == 0:
            _issue(errors, "EMPTY_AUDIO", f.name)
            continue
        match = _NUMBER.match(f.name)
        if match:
            n = int(match.group(1))
            if n in numbers:
                _issue(errors, "DUPLICATE_TRACK_NUMBER", f"{numbers[n]} and {f.name}")
            numbers[n] = f.name
        try:
            completed = subprocess.run(["flac", "-t", "--silent", str(f)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       timeout=timeout, check=False)
            if completed.returncode:
                _issue(errors, "FLAC_DECODE_FAILED", f.name)
        except (OSError, subprocess.TimeoutExpired) as exc:
            _issue(errors, "FLAC_TEST_UNAVAILABLE", f"{f.name}: {exc}")

    expected = manifest.get("files")
    if isinstance(expected, list):
        published_names = set()
        for item in expected:
            if not isinstance(item, dict):
                _issue(errors, "BAD_FILE_RECORD", "Malformed manifest file entry")
                continue
            name, digest = item.get("filename"), item.get("sha256")
            path = _safe_file(folder, name)
            if name in published_names:
                _issue(errors, "DUPLICATE_MANIFEST_ENTRY", str(name))
            published_names.add(name)
            if not path or path.parent != folder or path.suffix.lower() != ".flac":
                _issue(errors, "MISSING_MANIFEST_FILE", str(name))
            elif not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                _issue(errors, "BAD_SHA256", str(name))
            elif _sha256(path) != digest:
                _issue(errors, "SHA256_MISMATCH", str(name))
        if published_names != {p.name for p in audio}:
            _issue(errors, "FILE_SET_MISMATCH", "Active FLACs differ from manifest")
    elif manifest:
        _issue(warnings, "NO_FILE_HASHES", "Manifest lacks a file hash list")

    cues = sorted(folder.glob("*.cue"))
    for cue in cues:
        if cue.is_symlink() or not cue.is_file():
            _issue(errors, "UNSAFE_CUE", cue.name)
            continue
        try:
            references = [m.group(1) for line in cue.read_text(encoding="utf-8-sig").splitlines()
                          if (m := _CUE_FILE.match(line))]
        except (OSError, UnicodeError):
            _issue(errors, "UNREADABLE_CUE", cue.name)
            continue
        for ref in references:
            path = _safe_file(folder, ref)
            if not path or path.parent != folder or path.suffix.lower() != ".flac":
                _issue(errors, "CUE_BAD_REFERENCE", f"{cue.name}: {ref}")
        if len(references) != len(audio) or set(references) != {p.name for p in audio}:
            _issue(errors, "CUE_TRACK_SET_MISMATCH", cue.name)
    if not cues and provenance != "DIGITAL_ACQUISITION":
        _issue(warnings, "MISSING_CUE", "No album CUE; check original source documentation")

    if isinstance(manifest.get("cue"), dict):
        item = manifest["cue"]
        name = item.get("filename")
        path = _safe_file(folder, name)
        if not path or path.parent != folder or not isinstance(item.get("sha256"), str):
            _issue(errors, "MISSING_CUE_MANIFEST", str(name))
        elif _sha256(path) != item["sha256"]:
            _issue(errors, "CUE_HASH_MISMATCH", str(name))

    evidence = manifest.get("source_evidence")
    if isinstance(evidence, list):
        for entry in evidence:
            if not isinstance(entry, dict):
                _issue(errors, "BAD_EVIDENCE_RECORD", "Invalid source evidence entry")
                continue
            name, sha = entry.get("filename"), entry.get("sha256")
            path = _safe_file(folder, name)
            if not path or not str(name).startswith("ExtractionEvidence/"):
                _issue(errors, "MISSING_EVIDENCE", str(name))
            elif not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{64}", sha):
                _issue(errors, "BAD_EVIDENCE_HASH", str(name))
            elif _sha256(path) != sha or path.stat().st_size != entry.get("size"):
                _issue(errors, "EVIDENCE_MISMATCH", str(name))
    elif provenance in {"PHYSICAL_CD_RIP", "HYBRID_REPAIRED_CD_RIP"}:
        _issue(warnings, "EVIDENCE_NOT_EMBEDDED", "Original extraction evidence is not embedded in this archive")

    from oscar import cd_extra
    try:
        cd_extra.check_archive(folder, manifest)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        _issue(errors, "CD_EXTRA_DATA_MISMATCH", str(exc))
    return {"release": str(folder), "source_type": provenance,
            "status": "FAIL" if errors else "PASS_WITH_WARNINGS" if warnings else "PASS",
            "active_flacs": len(audio), "errors": errors, "warnings": warnings,
            "verification": {"flac_decode": "checked",
                             "accuraterip": "NOT_INDEPENDENTLY_CHECKED",
                             "ctdb": "NOT_INDEPENDENTLY_CHECKED"}}


def audit_archive(root: Path) -> dict:
    """Find album leaves, excluding evidence, obsolete temporary and failure folders."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Archive root must be a real directory")
    albums = []
    for folder in root.rglob("*"):
        if not folder.is_dir() or folder.is_symlink():
            continue
        relative = folder.relative_to(root)
        if any(part.startswith(".oscar-unpublished-") or part in
               {"ExtractionEvidence", "FailedAttempts", "Verification", "Original", ".oscar-archive-versions",
                "old-publications"} for part in relative.parts):
            continue
        if any(folder.glob("*.flac")) or (folder / "manifest.json").exists():
            albums.append(folder)
    releases = [audit_release(folder) for folder in sorted(albums)]
    # Evidence folders are excluded from the album count, but a player may
    # still index their loose audio. Report it separately, never delete it.
    evidence_audio = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if not any(part in {"ExtractionEvidence", "FailedAttempts", "Verification", "Original"}
                   for part in relative.parts[:-1]):
            continue
        if path.is_file() and path.suffix.lower() in {".flac", ".wav", ".mp3", ".m4a", ".ogg", ".opus", ".aiff", ".aif", ".ape", ".wv", ".aac", ".alac", ".wma"}:
            evidence_audio.append(str(relative))
    evidence_audio.sort()
    return {
        "archive_root": str(root),
        "releases_examined": len(releases),
        "playable_evidence": evidence_audio,
        "active_flacs": sum(r["active_flacs"] for r in releases),
        "source_types": {source: sum(r["source_type"] == source for r in releases)
                         for source in ("PHYSICAL_CD_RIP", "DIGITAL_ACQUISITION",
                                        "HYBRID_REPAIRED_CD_RIP", "UNKNOWN")},
        "status": ("FAIL" if any(r["status"] == "FAIL" for r in releases)
                   else "PASS_WITH_WARNINGS" if evidence_audio or any(r["warnings"] for r in releases) else "PASS"),
        "releases": releases,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only OSCAR archive integrity audit")
    parser.add_argument("archive_root", type=Path)
    parser.add_argument("--json", action="store_true", help="Output JSON report to stdout")
    args = parser.parse_args(argv)
    try:
        result = audit_archive(args.archive_root)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"OSCAR archive audit: {result['status']} | {result['releases_examined']} releases | {result['active_flacs']} FLACs")
        for release in result["releases"]:
            print(f"{release['status']}: {release['release']} ({release['source_type']})")
            for issue in release["errors"]:
                print(f"  ERROR {issue['code']}: {issue['message']}")
            for issue in release["warnings"]:
                print(f"  WARN  {issue['code']}: {issue['message']}")
        for path in result["playable_evidence"]:
            print(f"  WARN PLAYABLE_EVIDENCE: {path}")
        print("AccurateRip/CTDB: not independently checked by this auditor.")
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
