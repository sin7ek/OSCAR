"""Read-only CTDB verification of existing split-track FLAC albums."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from mutagen import MutagenError
from mutagen.flac import FLAC

from oscar.ctdb_verification import parse_result

_MAX_TRACKS = 99
_MAX_SECTORS = 450_000
_TIMEOUT = 180


@dataclass(frozen=True)
class Track:
    path: Path
    number: int
    total: int | None
    disc: int | None
    disc_total: int | None
    samples: int
    pcm: tuple[int, int, int]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _numbering(tags, path, field, total_fields):
    values = tags.get(field, [])
    if not values:
        number = None
        totals = []
    elif len(values) != 1 or not (match := re.fullmatch(r"([0-9]{1,4})(?:/([0-9]{1,4}))?", values[0].strip())):
        raise ValueError(f"Invalid or ambiguous {field.upper()}: {path.name}")
    else:
        number = int(match[1])
        totals = [match[2]] if match[2] else []
    for key in total_fields:
        totals.extend(value.strip() for value in tags.get(key, []))
    if any(not re.fullmatch(r"[0-9]{1,4}", value) for value in totals):
        raise ValueError(f"Invalid {field.upper()} total: {path.name}")
    declared = {int(value) for value in totals}
    if len(declared) > 1 or any(not 1 <= value <= _MAX_TRACKS for value in declared):
        raise ValueError(f"Inconsistent {field.upper()} total: {path.name}")
    if number is not None and not 1 <= number <= _MAX_TRACKS:
        raise ValueError(f"Invalid {field.upper()}: {path.name}")
    return number, next(iter(declared), None)


def _flac_paths(album):
    paths = []
    for root, dirs, files in os.walk(album, onerror=_raise_walk_error):
        folder = Path(root)
        if any((folder / name).is_symlink() for name in (*dirs, *files)):
            raise ValueError(f"Symlink in album: {folder.relative_to(album)}")
        for name in files:
            path = folder / name
            if path.suffix.lower() == ".flac":
                if not path.is_file():
                    raise ValueError(f"Not a regular FLAC file: {path.relative_to(album)}")
                paths.append(path)
    return sorted(paths)


def _raise_walk_error(error):
    raise error


def inventory(album):
    album = Path(album).absolute()
    if not album.is_dir() or album.resolve() != album:
        raise ValueError("Use an existing album directory without symlinks")
    paths = _flac_paths(album)
    if not paths:
        raise ValueError("No FLAC files found in the album")
    hashes = {path: digest(path) for path in paths}
    discs = {}
    missing_disc_numbers = False
    explicit_disc_numbers = False
    for path in paths:
        audio = FLAC(path)
        number, total = _numbering(audio, path, "tracknumber", ("totaltracks", "tracktotal"))
        disc, disc_total = _numbering(audio, path, "discnumber", ("totaldiscs", "disctotal"))
        if number is None:
            raise ValueError(f"Missing TRACKNUMBER: {path.name}")
        missing_disc_numbers |= disc is None
        explicit_disc_numbers |= disc is not None
        info = audio.info
        track = Track(path, number, total, disc, disc_total, info.total_samples,
                      (info.sample_rate, info.channels, info.bits_per_sample))
        discs.setdefault(disc or 1, []).append(track)

    disc_count = len(discs)
    if sorted(discs) != list(range(1, disc_count + 1)):
        raise ValueError("Disc numbering is not consecutive from 1")
    if missing_disc_numbers and explicit_disc_numbers:
        raise ValueError("Mixed tagged and untagged disc numbers")
    for disc, tracks in discs.items():
        tracks.sort(key=lambda track: track.number)
        track_count = len(tracks)
        if ([track.number for track in tracks] != list(range(1, track_count + 1))
                or any(track.total not in (None, track_count)
                       or track.disc_total not in (None, disc_count) for track in tracks)):
            raise ValueError(f"Missing, duplicate or inconsistent track/disc numbering on disc {disc}")
    return album, discs, hashes


def candidate_toc(samples):
    """Return MusicBrainz-style offsets, including the 150-sector lead-in."""
    if (not 1 <= len(samples) <= _MAX_TRACKS
            or any(type(n) is not int or n <= 0 or n % 588 for n in samples)):
        raise ValueError("Tracks are not CD-sector aligned")
    offsets = []
    cursor = 150
    for samples_in_track in samples:
        offsets.append(cursor)
        cursor += samples_in_track // 588
    if cursor - 150 > _MAX_SECTORS:
        raise ValueError("Audio exceeds the supported CD length")
    return [1, len(samples), cursor, *offsets]


def _test_flac(path, runner):
    try:
        process = runner(["flac", "-t", "--silent", str(path)],
                         capture_output=True, timeout=_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    return "failed" if process.returncode else "passed"


def _verify_ctdb(tracks, toc, executable, runner):
    if not Path(executable).is_absolute():
        return {"status": "unavailable", "message": "Configure the absolute path to OSCAR's ctdb-cli"}
    # ctdb-cli reports zero-based INDEX 01 offsets followed by the lead-out.
    expected_toc = ":".join(str(offset - 150) for offset in [*toc[3:], toc[2]])
    with tempfile.TemporaryDirectory(prefix="oscar-external-") as temp:
        folder = Path(temp)
        lines = []
        for track in tracks:
            name = f"{track.number:02d}.flac"
            (folder / name).symlink_to(track.path)
            lines.extend([f'FILE "{name}" WAVE', f"  TRACK {track.number:02d} AUDIO",
                          "    INDEX 01 00:00:00"])
        cue = folder / "disc.cue"
        cue.write_text("\n".join(lines) + "\n", encoding="ascii")
        try:
            process = runner([executable, "--xml", "verify", str(cue)], cwd=folder,
                             capture_output=True, timeout=_TIMEOUT, check=False)
            if process.returncode or b"shorter than TOC" in process.stderr:
                raise ValueError("Verifier failed")
            expected_line = f"CTDB request TOC: {expected_toc}".encode("ascii")
            if expected_line not in process.stderr.splitlines():
                return {"status": "lookup_failed", "message": "Verifier did not confirm the inferred TOC"}
            return parse_result(process.stdout)
        except FileNotFoundError:
            return {"status": "unavailable", "message": "Configured CTDB verifier was not found"}
        except (OSError, ValueError, KeyError, ElementTree.ParseError, subprocess.TimeoutExpired):
            return {"status": "lookup_failed", "message": "CTDB verifier did not return a usable result"}


def _verify_disc(album, disc, tracks, hashes, executable, runner):
    files = {str(track.path.relative_to(album)): _test_flac(track.path, runner) for track in tracks}
    checks = set(files.values())
    integrity = "failed" if "failed" in checks else "unavailable" if "unavailable" in checks else "passed"
    report = {
        "disc": disc,
        "files_sha256": {str(track.path.relative_to(album)): hashes[track.path] for track in tracks},
        "file_integrity": files,
        "layout": "inferred_contiguous_index01_no_hidden_audio",
        "track_total_declared": any(track.total is not None for track in tracks),
        "accuraterip": {"status": "not_performed"},
        "integrity": integrity,
        "ctdb": {"status": "not_performed"},
    }
    if integrity == "passed":
        try:
            if any(track.pcm != (44100, 2, 16) for track in tracks):
                raise ValueError("Not 44.1 kHz, 16-bit stereo CD audio")
            toc = candidate_toc([track.samples for track in tracks])
        except ValueError as error:
            report["ctdb"] = {"status": "unsupported", "message": str(error)}
        else:
            report["candidate_toc"] = toc
            report["ctdb"] = _verify_ctdb(tracks, toc, executable, runner)
    return report


def verify(album, *, executable=None, runner=subprocess.run):
    album, discs, hashes = inventory(album)
    executable = str(executable or os.getenv("OSCAR_CTDB_EXECUTABLE", "")).strip()
    reports = [_verify_disc(album, disc, tracks, hashes, executable, runner)
               for disc, tracks in sorted(discs.items())]
    if set(_flac_paths(album)) != hashes.keys() or any(digest(path) != sha for path, sha in hashes.items()):
        raise ValueError("Source FLACs changed during verification")
    if any(report["integrity"] == "failed" for report in reports):
        status = "integrity_failed"
    elif any(report["integrity"] == "unavailable" for report in reports):
        status = "integrity_unavailable"
    elif all(report["ctdb"]["status"] == "matched" for report in reports):
        status = "database_matched_candidate_layout"
    else:
        status = "integrity_passed"
    return {
        "source_type": "external",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "disc_total_declared": any(track.disc_total is not None for tracks in discs.values() for track in tracks),
        "assumed_single_disc": all(track.disc is None for tracks in discs.values() for track in tracks),
        "discs": reports,
        "status": status,
        "note": "Inferred layout; physical pressing and extraction provenance are unverified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("album", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.album)
    except (OSError, ValueError, MutagenError) as error:
        parser.exit(2, f"External verification: {error}\n")
    print(json.dumps(report, indent=2))
    return 1 if report["status"] in {"integrity_failed", "integrity_unavailable"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
