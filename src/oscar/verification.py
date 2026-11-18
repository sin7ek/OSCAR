"""Conservative, post-rip staged verification. No writes to audio/CUE/log.

AccurateRip evidence is *parsed from cyanrip's captured log*, NOT independently
queried by OSCAR. A passing report is not CTDB confirmation or archive approval.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from oscar import ripping

_MAX_LOG = 6_000_000
_MAX_TRACKS = 150
_RUNNING = set()
_LOCK = threading.Lock()
_AUDIO_NAME = re.compile(r"^audio/(\d{2,3}) - [^/\\]+\.flac$")
_LOG_RECORD = re.compile(
    r"(?ims)^\s*EAC CRC32:\s*([0-9a-f]{8})\s*$"
    r".*?^\s*Accurip:\s*([^\n]*)\n"
    r"(.*?)^\s*Metadata:\s*\n"
    r"(.*?)^\s*File\(s\):\s*\n\s*audio/(\d{2,3})\s*-\s*[^\n]+\.flac\s*$"
)
_AR = re.compile(
    r"(?im)^\s*Accurip v([12]):\s*([0-9A-F]{8})\s*"
    r"\((accurately ripped|[^,\)]+)(?:,\s*confidence\s*(\d+))?\)"
)


def parse_cyanrip_log(contents):
    """Correlate each per-track checksum/AR section with its actual output name."""
    records = {}
    for match in _LOG_RECORD.finditer(contents):
        crc, header, accurip, metadata, filename_track = match.groups()
        num = int(filename_track)
        stated = re.search(r"(?im)^\s*track:\s*(\d+)\s*$", metadata)
        if not stated or int(stated.group(1)) != num or num in records:
            continue
        ar = {}
        for ar_match in _AR.finditer(accurip):
            version, crc_ar, result, confidence = ar_match.groups()
            ar["v" + version] = {
                "crc": crc_ar.upper(),
                "status": "accurately_ripped" if result.strip().lower() == "accurately ripped" else "not_confirmed",
                "confidence": int(confidence) if confidence else None,
            }
        records[num] = {
            "track": num,
            "eac_crc32": crc.upper(),
            "database_found": "disc found in database" in header.lower(),
            "accuraterip": ar,
        }
    return records


def _safe_job(job_id):
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ripping.RipError("Invalid job ID")
    root = ripping.staging_root()
    directory = root / ("oscar-" + job_id)
    if not directory.is_dir() or directory.is_symlink():
        raise ripping.RipError("Staging job not found")
    return directory


def _load_job(directory, job_id):
    record = directory / "state.json"
    if record.is_symlink() or not record.is_file():
        raise ripping.RipError("Missing or unsafe job state")
    state = json.loads(record.read_text(encoding="utf-8"))
    if state.get("id") != job_id or state.get("status") != "needs_verification" or state.get("returncode") != 0:
        raise ripping.RipError("Only a successfully completed staging rip can be verified")
    return state


def _file_readonly(directory, relative):
    candidate = directory / relative
    if candidate.is_symlink() or not candidate.is_file() or candidate.resolve().parent not in {
        directory.resolve(), (directory / "audio").resolve()}:
        raise ripping.RipError("Unsafe or missing staged file: " + relative)
    return candidate


def _digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _cue_refs(text):
    return re.findall(r'(?im)^FILE\s+"([^"\r\n]+)"\s+WAVE\s*$', text)


def _verify(directory, job_id, runner=subprocess.run):
    state = _load_job(directory, job_id)
    manifest = state.get("files_sha256") or {}
    if not isinstance(manifest, dict) or not (1 <= len(manifest) <= _MAX_TRACKS):
        raise ripping.RipError("Missing or invalid FLAC hash manifest")
    planned = directory / "plan.json"
    if planned.is_symlink():
        raise ripping.RipError("Unsafe rip plan")
    plan = json.loads(planned.read_text(encoding="utf-8"))
    expected = plan.get("track_count")
    if not isinstance(expected, int) or not 1 <= expected <= _MAX_TRACKS:
        raise ripping.RipError("Invalid track count in rip plan")
    logfile = _file_readonly(directory, "cyanrip-console.log")
    if logfile.stat().st_size > _MAX_LOG:
        raise ripping.RipError("Rip log too large for automatic verification")
    log = logfile.read_text(encoding="utf-8", errors="replace")
    evidence = parse_cyanrip_log(log)
    errors = re.findall(r"(?im)^\s*Ripping errors:\s*(\d+)\s*$", log)
    ripping_errors = int(errors[-1]) if errors else None
    audio = directory / "audio"
    if not audio.is_dir() or audio.is_symlink():
        raise ripping.RipError("Unsafe or missing audio staging folder")
    files = sorted(audio.glob("*.flac"))
    other_files = [p for p in audio.iterdir() if p.suffix.lower() == ".flac" and p.is_symlink()]
    # Do not silently pass extra files absent from the saved manifest.
    manifest_names = set(manifest)
    actual_names = {str(p.relative_to(directory)) for p in files}
    numbered = {}
    for name in manifest_names:
        match = _AUDIO_NAME.fullmatch(name)
        if not match:
            raise ripping.RipError("Unexpected FLAC path in manifest")
        number = int(match.group(1))
        if number in numbered:
            raise ripping.RipError("Duplicate track numbers in manifest")
        numbered[number] = name
    cue_files = sorted(audio.glob("*.cue"))
    cue_ok = False
    cue_details = {"found": len(cue_files), "references_match": False}
    if len(cue_files) == 1 and not cue_files[0].is_symlink():
        cue = cue_files[0].read_text(encoding="utf-8", errors="replace")
        refs = _cue_refs(cue)
        cue_ok = len(refs) == expected and set(refs) == {Path(n).name for n in manifest_names}
        cue_details["references_match"] = cue_ok
        cue_details["track_references"] = len(refs)
    tracks = []
    for number in range(1, expected + 1):
        relative = numbered.get(number)
        result = {"number": number, "file": relative, "sha256_matches": False,
                  "flac_decodes": False, "eac_crc32": None, "accuraterip": {},
                  "evidence_source": "cyanrip-console.log"}
        if relative and relative in actual_names and not other_files:
            path = _file_readonly(directory, relative)
            result["sha256_matches"] = _digest(path).lower() == str(manifest[relative]).lower()
            if result["sha256_matches"]:
                try:
                    proc = runner(["flac", "-t", "--silent", str(path)],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                  timeout=180, check=False)
                    result["flac_decodes"] = proc.returncode == 0
                except (OSError, subprocess.TimeoutExpired):
                    pass
        parsed = evidence.get(number)
        if parsed:
            result["eac_crc32"] = parsed["eac_crc32"]
            result["accuraterip"] = parsed["accuraterip"]
        result["checks_passed"] = (
            result["sha256_matches"] and result["flac_decodes"] and
            all(result["accuraterip"].get(v, {}).get("status") == "accurately_ripped"
                for v in ("v1", "v2")))
        tracks.append(result)
    all_passed = (len(files) == expected == len(manifest) == len(evidence)
                  and all(track["checks_passed"] for track in tracks)
                  and cue_ok and ripping_errors == 0
                  and not other_files)
    return {
        "job_id": job_id,
        "status": "checks_passed" if all_passed else "review_required",
        "checked_at": time.time(),
        "expected_tracks": expected,
        "flac_count": len(files),
        "cue": cue_details,
        "ripping_errors": ripping_errors,
        "tracks": tracks,
        "notes": [
            "AccurateRip v1/v2 results are transcribed from cyanrip, not independently checked by OSCAR.",
            "FLAC -t validates each encoded stream; saved SHA-256 checks detect changes since extraction.",
            "No CTDB verification; no archive publication or automatic cleanup.",
            "A passing report never authorizes publishing or deleting staged audio."
        ],
    }


def report(job_id):
    directory = _safe_job(job_id)
    destination = directory / "verification-report.json"
    if destination.is_symlink():
        raise ripping.RipError("Unsafe verification report")
    if destination.is_file():
        return json.loads(destination.read_text(encoding="utf-8"))
    with _LOCK:
        running = job_id in _RUNNING
    return {"job_id": job_id, "status": "running" if running else "not_started"}


def start(job_id):
    directory = _safe_job(job_id)
    _load_job(directory, job_id)
    with _LOCK:
        if job_id in _RUNNING:
            return {"job_id": job_id, "status": "running"}
        if (directory / "verification-report.json").exists():
            return report(job_id)
        _RUNNING.add(job_id)
    def work():
        try:
            result = _verify(directory, job_id)
        except Exception as exc:
            result = {"job_id": job_id, "status": "review_required",
                      "error": f"{type(exc).__name__}: {exc}"[:400],
                      "notes": ["Verification was not completed; do not publish or delete files."]}
        finally:
            with _LOCK:
                _RUNNING.discard(job_id)
        # Exclusive temporary output and atomic rename; never modify source.
        destination = directory / "verification-report.json"
        if not destination.exists():
            tmp = directory / ("verification-" + job_id + ".tmp")
            try:
                with tmp.open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp, destination)
            except OSError:
                # Avoid modifying staged evidence if report cannot be saved.
                pass
    threading.Thread(target=work, daemon=True, name="oscar-verify-" + job_id[:8]).start()
    return {"job_id": job_id, "status": "running"}
