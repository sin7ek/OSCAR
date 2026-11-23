"""Independent CTDB verification of completed staging rips."""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
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


_CUE_DIRECTIVE = re.compile(r"^[ \t]*(FILE|TRACK|INDEX|PREGAP|POSTGAP)\b", re.I)
_CUE_TRACK = re.compile(r"\s*TRACK[ \t]+([0-9]{1,2})[ \t]+AUDIO[ \t]*", re.I)
_CUE_INDEX = re.compile(r"\s*INDEX[ \t]+([0-9]{2})[ \t]+([0-9]{2,}):([0-5][0-9]):([0-7][0-9])[ \t]*", re.I)


def _cue_layout(contents, count):
    """Validate split-file audio layout and remove cyanrip's repeated TRACK headers."""
    lines = contents.splitlines(keepends=True)
    blocks = []
    for index, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        match = _CUE_DIRECTIVE.match(line)
        if not match:
            continue
        command = match[1].upper()
        if command == "FILE":
            blocks.append([])
        elif not blocks:
            raise ripping.RipError("CTDB found a track or index before the first CUE file")
        else:
            blocks[-1].append((command, line, index))

    def invalid():
        return ripping.RipError("CTDB requires an ordered full-disc audio CUE with intact track indexes")

    if len(blocks) != count:
        raise invalid()
    repeated = set()
    continued = False
    for number, block in enumerate(blocks, 1):
        tracks = [(line, index) for command, line, index in block if command == "TRACK"]
        if not 1 <= len(tracks) <= 2:
            raise invalid()
        markers = [_CUE_TRACK.fullmatch(line) for line, _ in tracks]
        if any(marker is None for marker in markers) or int(markers[0][1]) != number:
            raise invalid()
        head = tracks[0][1]
        tail = tracks[1][1] if len(tracks) == 2 else len(lines)
        indexes = {}
        for command, line, index in block:
            if command == "INDEX":
                marker = _CUE_INDEX.fullmatch(line)
                if not marker or int(marker[4]) >= 75 or index <= head:
                    raise invalid()
                indexes[index] = (int(marker[1]), tuple(map(int, marker.groups()[1:])))
        current = [value for index, value in indexes.items() if index < tail]
        if [n for n, _ in current].count(1) != 1:
            raise invalid()
        if continued:
            if current[0] != (1, (0, 0, 0)) or any(
                command == "PREGAP" and index < tail for command, _, index in block
            ):
                raise invalid()
            repeated.add(head)
        next_indexes = [value for index, value in indexes.items() if index > tail]
        continued = len(tracks) == 2
        if continued and (
            number >= count or int(markers[1][1]) != number + 1
            or [index for index, _ in next_indexes] != [0]
            or any(command in {"PREGAP", "POSTGAP"} and index > tail for command, _, index in block)
        ):
            raise invalid()
    if repeated:
        return "".join(line for index, line in enumerate(lines) if index not in repeated)


@contextmanager
def _verification_cue(directory, cue, normalized, manifest):
    if normalized is None:
        yield cue
        return
    with tempfile.TemporaryDirectory(dir=directory, prefix=".ctdb-cue-") as folder:
        temp = Path(folder)
        for relative in manifest:
            source = verification._file_readonly(directory, relative)
            (temp / source.name).symlink_to(source.resolve())
        compatible = temp / cue.name
        compatible.write_text(normalized, encoding="utf-8")
        yield compatible


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
    raw = cue.read_bytes()
    contents = raw.decode("utf-8-sig")
    refs = verification._cue_refs(contents)
    normalized = _cue_layout(contents, count)
    if len(refs) != count:
        raise ripping.RipError("CTDB requires exactly one WAVE file per saved audio track")
    for number, ref in enumerate(refs, 1):
        relative = "audio/" + ref
        if (Path(ref).name != ref or "\\" in ref or relative not in manifest
                or not re.fullmatch(rf"0*{number} - .+\.flac", ref)):
            raise ripping.RipError("CUE files differ from the saved disc layout")
    return cue, manifest, hashlib.sha256(raw).hexdigest(), normalized


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
    cue, manifest, cue_hash, normalized = _inputs(job_id, directory)
    for relative, digest in manifest.items():
        if verification._digest(verification._file_readonly(directory, relative)) != digest:
            raise ripping.RipError("Staged audio differs from its original SHA-256")
    if not executable or not Path(executable).is_absolute():
        if not automatic:
            raise ripping.RipError("Set OSCAR_CTDB_EXECUTABLE to the absolute path of ctdb-cli")
        result = {"status": "unavailable", "message": "CTDB verifier is not configured"}
    else:
        try:
            with _verification_cue(directory, cue, normalized, manifest) as compatible:
                process = runner([executable, "--xml", "verify", str(compatible)],
                                 cwd=compatible.parent, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=180, check=False)
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
    if normalized is not None:
        record["cue_layout"] = "cyanrip_split_pregaps"
        record["verifier_cue_sha256"] = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
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
        _, manifest, cue_hash, _ = _inputs(job_id, directory)
    except ripping.RipError:
        return None
    if (value.get("job_id") != job_id or value.get("files_sha256") != manifest
            or value.get("cue_sha256") != cue_hash):
        return None
    result = {key: value[key] for key in ("status", "method", "confidence", "total", "toc", "trigger", "message", "cue_layout", "verifier_cue_sha256")
              if key in value}
    return result, hashlib.sha256(raw).hexdigest()
