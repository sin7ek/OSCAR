"""Read-only external split-track CD verification (experimental CLI)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime, timezone
from xml.etree import ElementTree

from mutagen.flac import FLAC
from oscar.ctdb_verification import parse_result


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(album):
    album = Path(album).absolute()
    if not album.is_dir() or album.resolve() != album:
        raise ValueError("Unsafe album path")
    discs = {}
    for path in sorted(album.rglob("*")):
        if path.is_symlink():
            raise ValueError("Symlink in album")
        if not path.is_file() or path.suffix.lower() != ".flac":
            continue
        audio = FLAC(path)
        def number(tag):
            values = audio.get(tag, [])
            if len(values) != 1 or not values[0].isascii() or not values[0].isdigit():
                raise ValueError(f"Missing or ambiguous {tag}: {path.name}")
            return int(values[0])
        disc, track = number("discnumber"), number("tracknumber")
        total, totaldiscs = number("totaltracks"), number("totaldiscs")
        if not (1 <= disc <= totaldiscs <= 99 and 1 <= track <= total <= 99):
            raise ValueError("Invalid disc or track numbering")
        discs.setdefault(disc, []).append((track, total, totaldiscs, path, audio.info))
    if not discs or sorted(discs) != list(range(1, len(discs) + 1)):
        raise ValueError("Missing discs")
    for tracks in discs.values():
        tracks.sort(key=lambda item: item[0])
        if ([t[0] for t in tracks] != list(range(1, len(tracks) + 1))
                or any(t[1] != len(tracks) or t[2] != len(discs) for t in tracks)):
            raise ValueError("Incomplete or inconsistent disc")
    return album, discs


def candidate_toc(samples):
    if not samples or any(type(n) is not int or n <= 0 or n % 588 for n in samples):
        raise ValueError("Tracks are not CD-sector aligned")
    offsets = []
    cursor = 150
    for n in samples:
        offsets.append(cursor)
        cursor += n // 588
    return [1, len(samples), cursor, *offsets]


def verify(album, *, executable=None, runner=subprocess.run):
    album, discs = inventory(album)
    executable = executable or os.environ.get("OSCAR_CTDB_EXECUTABLE", "")
    reports = []
    for disc, tracks in sorted(discs.items()):
        manifest = {str(t[3].relative_to(album)): digest(t[3]) for t in tracks}
        record = {"disc": disc, "files_sha256": manifest,
                  "layout": "inferred_contiguous_index01_no_hidden_audio",
                  "accuraterip": {"status": "not_performed"},
                  "integrity": "passed", "ctdb": {"status": "not_performed"}}
        for _, _, _, path, _ in tracks:
            proc = runner(["flac", "-t", "--silent", str(path)],
                          capture_output=True, timeout=180, check=False)
            if proc.returncode:
                record["integrity"] = "failed"
        if record["integrity"] == "passed":
            try:
                if any((t[4].sample_rate, t[4].channels, t[4].bits_per_sample)
                       != (44100, 2, 16) for t in tracks):
                    raise ValueError("Not CD PCM")
                record["candidate_toc"] = candidate_toc([t[4].total_samples for t in tracks])
            except ValueError as exc:
                record["ctdb"] = {"status": "unsupported", "message": str(exc)}
            else:
                if not executable or not Path(executable).is_absolute():
                    record["ctdb"] = {"status": "unavailable"}
                else:
                    with tempfile.TemporaryDirectory(prefix="oscar-external-") as tmp:
                        folder = Path(tmp)
                        lines = []
                        for track, _, _, path, _ in tracks:
                            name = f"{track:02d}.flac"
                            (folder / name).symlink_to(path)
                            lines.extend([f'FILE "{name}" WAVE', f"  TRACK {track:02d} AUDIO",
                                          "    INDEX 01 00:00:00"])
                        cue = folder / "disc.cue"
                        cue.write_text("\n".join(lines) + "\n", encoding="utf-8")
                        try:
                            proc = runner([executable, "--xml", "verify", str(cue)],
                                          cwd=folder, capture_output=True, timeout=180, check=False)
                            if proc.returncode or b"shorter than TOC" in proc.stderr:
                                raise ValueError("Verifier failed")
                            record["ctdb"] = parse_result(proc.stdout)
                        except (OSError, ValueError, KeyError, ElementTree.ParseError,
                                subprocess.TimeoutExpired):
                            record["ctdb"] = {"status": "lookup_failed"}
        if any(digest(album / rel) != sha for rel, sha in manifest.items()):
            raise ValueError("Source changed during verification")
        reports.append(record)
    return {"source_type": "external", "checked_at": datetime.now(timezone.utc).isoformat(),
            "discs": reports,
            "status": ("database_matched_candidate_layout" if all(
                r["ctdb"]["status"] == "matched" for r in reports) else
                "integrity_failed" if any(r["integrity"] == "failed" for r in reports) else
                "integrity_passed"),
            "note": "Inferred layout; physical pressing and extraction provenance not established."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("album", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.album), indent=2))


if __name__ == "__main__":
    main()
