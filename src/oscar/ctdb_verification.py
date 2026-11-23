"""Independent CTDB verification of completed staging rips."""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

from oscar import ripping, verification

REPORT = "ctdb-report.json"
_NAMESPACE = "http://db.cuetools.net/ns/mmd-1.0#"


def parse_result(output):
    if len(output) > 1_000_000 or b"<!DOCTYPE" in output.upper():
        raise ValueError("Unexpected CTDB output")
    root = ElementTree.fromstring(output)
    result = root.find("verify_result")
    if root.tag != f"{{{_NAMESPACE}}}ctdb" or result is None:
        raise ValueError("No CTDB verification result")
    status = result.get("status")
    if status == "not_found":
        return {"status": "not_found"}
    if status != "found":
        return {"status": "lookup_failed", "message": result.get("message", "")[:250]}
    confidence = int(result.attrib["confidence"])
    total = int(result.attrib["total_entries"])
    if not 0 <= confidence <= total or total < 1:
        raise ValueError("Invalid CTDB confidence")
    return {"status": "matched" if confidence else "no_audio_match",
            "confidence": confidence, "total": total, "toc": result.get("toc")}


def _inputs(job_id, directory):
    state = verification._load_job(directory, job_id)
    manifest = state.get("files_sha256") or {}
    plan = json.loads(verification._file_readonly(directory, "plan.json").read_text())
    count = plan.get("track_count")
    if type(count) is not int or not 1 <= count <= 99 or len(manifest) != count:
        raise ripping.RipError("CTDB requires a complete saved disc")
    audio = directory / "audio"
    if audio.is_symlink() or not audio.is_dir():
        raise ripping.RipError("Unsafe audio folder")
    cues = list(audio.glob("*.cue"))
    if len(cues) != 1:
        raise ripping.RipError("CTDB requires one saved CUE")
    cue = verification._file_readonly(directory, "audio/" + cues[0].name)
    contents = cue.read_text(encoding="utf-8")
    refs = verification._cue_refs(contents)
    file_lines = re.split(r"(?im)^\s*FILE\b", contents)[1:]
    tracks = re.findall(r"(?im)^\s*TRACK\s+(\d+)\s+AUDIO\s*$", contents)
    track_lines = re.findall(r"(?im)^\s*TRACK\b", contents)
    if (len(refs) != count or len(file_lines) != count or len(track_lines) != count
            or [int(x) for x in tracks] != list(range(1, count + 1))
            or any(len(re.findall(r"(?im)^\s*TRACK\b", block)) != 1
                   or len(re.findall(r"(?im)^\s*INDEX\s+01\s+\d\d:\d\d:\d\d\s*$", block)) != 1
                   for block in file_lines)):
        raise ripping.RipError("CTDB requires an ordered full-disc audio CUE")
    for number, ref in enumerate(refs, 1):
        relative = "audio/" + ref
        if (Path(ref).name != ref or "\\" in ref or relative not in manifest
                or not re.fullmatch(rf"0*{number} - .+\.flac", ref)):
            raise ripping.RipError("CUE files differ from the saved disc layout")
    return cue, manifest


def automatic(job_id, directory):
    """Complete one automatic attempt for a new rip; older jobs remain manual."""
    try:
        state = verification._load_job(directory, job_id)
        if state.get("ctdb_automatic") is True:
            _run(job_id, directory, automatic=True, runner=subprocess.run)
    except (ripping.RipError, OSError, ValueError):
        # A malformed CUE or changed audio is ineligible for CTDB evidence.
        # CTDB diagnostics never change an extraction or AccurateRip verdict.
        return


def verify(job_id, *, runner=None):
    return _run(job_id, verification._safe_job(job_id), automatic=False,
                runner=runner or subprocess.run)


def _run(job_id, directory, *, automatic, runner):
    fd = os.open(directory / ".ctdb.lock", os.O_CREAT | os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = saved_evidence(job_id, directory)
        if automatic and previous:
            return previous[0]
        return _verify(job_id, directory, previous=previous, automatic=automatic, runner=runner)


def _verify(job_id, directory, *, previous, automatic, runner):
    executable = os.environ.get("OSCAR_CTDB_EXECUTABLE", "").strip()
    cue, manifest = _inputs(job_id, directory)
    cue_hash = verification._digest(cue)
    for relative, digest in manifest.items():
        if verification._digest(verification._file_readonly(directory, relative)) != digest:
            raise ripping.RipError("Staged audio differs from its original SHA-256")
    if not executable or not Path(executable).is_absolute():
        if not automatic:
            raise ripping.RipError("Set OSCAR_CTDB_EXECUTABLE to the absolute path of ctdb-cli")
        result = {"status": "unavailable", "message": "CTDB verifier is not configured"}
    else:
        try:
            process = runner([executable, "--xml", "verify", str(cue)], cwd=cue.parent,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=180, check=False)
            if process.returncode or b"shorter than TOC" in process.stderr:
                raise ValueError("CTDB verifier exited with an error")
            result = parse_result(process.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, ElementTree.ParseError):
            result = {"status": "lookup_failed", "message": "CTDB verifier did not return a usable result"}
    if verification._digest(cue) != cue_hash or any(
        verification._digest(verification._file_readonly(directory, rel)) != digest
        for rel, digest in manifest.items()
    ):
        raise ripping.RipError("Staging changed during CTDB verification")
    record = {**result, "job_id": job_id, "method": "ctdb-cli verify",
              "trigger": "automatic" if automatic else "manual",
              "cue_sha256": cue_hash, "files_sha256": manifest,
              "checked_at": datetime.now(timezone.utc).isoformat()}
    destination = directory / REPORT
    # A failed retry does not overwrite previously obtained database evidence.
    if not previous or result["status"] not in {"lookup_failed", "unavailable"}:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                         prefix=".ctdb-", delete=False) as stream:
            try:
                json.dump(record, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(stream.name, destination)
            finally:
                Path(stream.name).unlink(missing_ok=True)
    return result


def saved_evidence(job_id, directory):
    path = directory / REPORT
    if not path.exists() and not path.is_symlink():
        return None
    path = verification._file_readonly(directory, REPORT)
    raw = path.read_bytes()
    value = json.loads(raw)
    try:
        cue, manifest = _inputs(job_id, directory)
    except ripping.RipError:
        return None
    if (value.get("job_id") != job_id or value.get("files_sha256") != manifest
            or value.get("cue_sha256") != verification._digest(cue)):
        return None
    result = {key: value[key] for key in ("status", "method", "confidence", "total", "toc", "trigger", "message")
              if key in value}
    return result, hashlib.sha256(raw).hexdigest()
