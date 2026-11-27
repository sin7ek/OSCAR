"""Conservative, post-rip staged verification. No writes to audio/CUE/log.

AccurateRip CRCs come from cyanrip's captured log. A validated CD-Extra can
receive an independent database lookup. A passing report is not CTDB confirmation
or archive approval.
"""
import hashlib
import shutil
import uuid
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from oscar import ripping

_MAX_LOG = 512_000_000
_MAX_EVIDENCE = 2_000_000
_MAX_TRACKS = 150
_RUNNING = set()
_LOCK = threading.Lock()
_AUDIO_NAME = re.compile(r"^audio/((?:[1-9]\d{0,2}|0[1-9]\d?|00[1-9])) - [^/\\]+\.flac$")
_LOG_RECORD = re.compile(
    r"(?ims)^\s*EAC CRC32:\s*([0-9a-f]{8})\s*$"
    r".*?^\s*Accurip:\s*([^\n]*)\n"
    r"(.*?)^\s*Metadata:\s*\n"
    r"(.*?)^\s*File\(s\):\s*\n\s*audio/((?:[1-9]\d{0,2}|0[1-9]\d?|00[1-9]))\s*-\s*[^\n]+\.flac\s*$"
)
_AR = re.compile(
    r"(?im)^\s*Accurip v([12]):\s*([0-9A-F]{8})\s*"
    r"\((accurately ripped|[^,\)]+)(?:,\s*confidence\s*(\d+))?\)"
)
_AR_BARE = re.compile(r"(?im)^[ \t]*Accurip v([12]):[ \t]*([0-9a-f]{8})[ \t]*$")



_EVIDENCE_LINE = re.compile(
    rb"(?i)^\s*(?:EAC CRC32:|Accurip(?::| v[12]:)|Metadata:|track:|File\(s\):|audio/(?:[1-9]\d{0,2}|0[1-9]\d?|00[1-9])\s*-|Ripping errors:)"
)


def read_cyanrip_evidence(path, *, pattern=_EVIDENCE_LINE):
    """Stream-filter CR/LF-delimited cyanrip output, ignoring bulky progress spam."""
    evidence = bytearray()
    current = bytearray()
    total = 0

    def consume(line):
        if len(line) <= 4096 and pattern.match(line):
            if len(evidence) + len(line) + 1 > _MAX_EVIDENCE:
                raise ripping.RipError("Too many verification records in rip log")
            evidence.extend(line)
            evidence.append(10)

    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            total += len(chunk)
            if total > _MAX_LOG:
                raise ripping.RipError("Rip log exceeds safety limit")
            for byte in chunk:
                if byte in (10, 13):
                    consume(current)
                    current.clear()
                elif len(current) < 4097:
                    current.append(byte)
        if current:
            consume(current)
    return evidence.decode("utf-8", errors="replace")


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
            "database_missing": header.strip().lower() == "not found",
            "accuraterip": ar,
            "calculated_crcs": {"v" + version: value.upper()
                                for version, value in _AR_BARE.findall(accurip)},
        }
    return records


def _extra_accuraterip(job_id, directory, evidence, expected):
    """Only recover absent cyanrip lookups for a validated complete CD-Extra."""
    if (set(evidence) != set(range(1, expected + 1)) or
            any(not record["database_missing"] or record["accuraterip"] or
                set(record["calculated_crcs"]) != {"v1", "v2"}
                for record in evidence.values())):
        return None, {}
    from oscar import ctdb_verification, cd_extra_accuraterip
    try:
        _, _, _, _, _, disc_toc = ctdb_verification._inputs(job_id, directory)
    except (ripping.RipError, OSError, ValueError):
        return None, {}
    if not disc_toc:
        return None, {}
    return cd_extra_accuraterip.lookup(
        disc_toc, {number: record["calculated_crcs"] for number, record in evidence.items()})



def accuraterip_assessment(versions):
    """Treat absent evidence differently from an explicit negative result.

    At least one positively confirmed AccurateRip version is necessary. Any
    explicitly reported failed version requires review instead of being hidden.
    """
    statuses = {version: (versions.get(version) or {}).get("status")
                for version in ("v1", "v2")}
    confirmed = [v for v, status in statuses.items() if status == "accurately_ripped"]
    contradicted = [v for v, status in statuses.items()
                    if status is not None and status != "accurately_ripped"]
    if contradicted:
        status = "review_required"
    elif len(confirmed) == 2:
        status = "both_versions_matched"
    elif len(confirmed) == 1:
        status = "single_version_matched"
    else:
        status = "no_confirmed_match"
    return {
        "status": status,
        "matched_versions": confirmed,
        "absent_versions": [v for v, state in statuses.items() if state is None],
        "unconfirmed_versions": contradicted,
    }


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
    log = read_cyanrip_evidence(logfile)
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
    extra_lookup, extra_matches = _extra_accuraterip(job_id, directory, evidence, expected)
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
        if extra_lookup and extra_lookup["status"] == "found":
            result["accuraterip"] = extra_matches[number]
            result["calculated_accuraterip_crcs"] = parsed["calculated_crcs"]
            result["evidence_source"] = "cyanrip-console.log + full-disc AccurateRip database lookup"
        result["accuraterip_assessment"] = accuraterip_assessment(result["accuraterip"])
        result["checks_passed"] = (
            result["sha256_matches"] and result["flac_decodes"] and
            result["accuraterip_assessment"]["status"] in
                ("both_versions_matched", "single_version_matched"))
        tracks.append(result)
    all_passed = (len(files) == expected == len(manifest) == len(evidence)
                  and all(track["checks_passed"] for track in tracks)
                  and cue_ok and ripping_errors == 0
                  and not other_files)
    single_version = [
        track["number"] for track in tracks
        if track["accuraterip_assessment"]["status"] == "single_version_matched"
    ]
    report = {
        "job_id": job_id,
        "status": "checks_passed" if all_passed else "review_required",
        "accuraterip_coverage": (
            "both_versions" if all_passed and not single_version
            else "single_version_on_some_tracks" if all_passed
            else "requires_review"
        ),
        "single_version_tracks": single_version,
        "checked_at": time.time(),
        "expected_tracks": expected,
        "flac_count": len(files),
        "cue": cue_details,
        "ripping_errors": ripping_errors,
        "tracks": tracks,
        "notes": [
            "AccurateRip v1/v2 results are transcribed from cyanrip, not independently checked by OSCAR.",
            "An absent AccurateRip version does not negate a positive match in another version; any explicitly negative version still requires review.",
            "Check accuraterip_coverage and single_version_tracks. Confidence reflects reported reference matches; no unverified database entries were inferred.",
            "FLAC -t validates each encoded stream; saved SHA-256 checks detect changes since extraction.",
            "CTDB is checked separately from this report. No archive publication or automatic cleanup.",
            "A passing report never authorizes publishing or deleting staged audio."
        ],
    }
    if extra_lookup:
        report["accuraterip_lookup"] = extra_lookup
        if extra_lookup["status"] == "found":
            report["verification_method"] = "cyanrip_cd_extra_accuraterip_lookup"
            report["notes"][0] = (
                "OSCAR compared cyanrip's calculated CRCs with AccurateRip using the full CD-Extra TOC. "
                "The audio CRC values come from the original extraction log; FLAC integrity and saved hashes were checked separately.")
        else:
            report["notes"].insert(1, "Full CD-Extra AccurateRip lookup: " + extra_lookup["status"])
    return report


def report(job_id):
    directory = _safe_job(job_id)
    destination = directory / "verification-report.json"
    if destination.is_symlink():
        raise ripping.RipError("Unsafe verification report")
    with _LOCK:
        running = job_id in _RUNNING
    if running:
        return {"job_id": job_id, "status": "running"}
    if destination.is_file():
        result = json.loads(destination.read_text(encoding="utf-8"))
        from oscar import ctdb_verification
        try:
            ctdb = ctdb_verification.saved_evidence(job_id, directory)
        except (ripping.RipError, OSError, ValueError):
            ctdb = None
        if ctdb:
            result["ctdb"] = ctdb[0]
        return result
    return {"job_id": job_id, "status": "not_started"}


def start(job_id):
    directory = _safe_job(job_id)
    _load_job(directory, job_id)
    with _LOCK:
        if job_id in _RUNNING:
            return {"job_id": job_id, "status": "running"}
        prior = directory / "verification-report.json"
        if prior.is_symlink():
            raise ripping.RipError("Unsafe verification report")
        if prior.is_file():
            previous = json.loads(prior.read_text(encoding="utf-8"))
            if previous.get("status") == "checks_passed":
                return previous
        _RUNNING.add(job_id)
    def work():
        try:
            from oscar import ctdb_verification
            ctdb_verification.automatic(job_id, directory)
            result = _verify(directory, job_id)
        except Exception as exc:
            result = {"job_id": job_id, "status": "review_required",
                      "error": f"{type(exc).__name__}: {exc}"[:400],
                      "notes": ["Verification was not completed; do not publish or delete files."]}
        # Preserve failed reports, while replacing only the report pointer.
        destination = directory / "verification-report.json"
        tmp = directory / ("verification-" + uuid.uuid4().hex + ".tmp")
        try:
            if destination.is_symlink():
                raise ripping.RipError("Unsafe verification report")
            with tmp.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if destination.exists():
                backup = directory / ("verification-report-previous-" + uuid.uuid4().hex + ".json")
                with destination.open("rb") as source, backup.open("xb") as output:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
            os.replace(tmp, destination)
            try:
                from oscar.drivefit_history import record_verification
                record_verification(job_id, result)
            except Exception:
                pass  # No verification verdict depends on DriveFit availability.
        except OSError:
            pass
        finally:
            with _LOCK:
                _RUNNING.discard(job_id)
    threading.Thread(target=work, daemon=True, name="oscar-verify-" + job_id[:8]).start()
    return {"job_id": job_id, "status": "running"}
