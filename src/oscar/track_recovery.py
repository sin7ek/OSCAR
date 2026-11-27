"""Non-destructive recovery of a complete CD from independently verified track rips.

Only named staging jobs under OSCAR_RIP_ROOT may contribute. A recovered job
contains real copied FLACs (never symlinks); all source audio and logs remain
unchanged. Each track must be confirmed by an independent whole-disc
trackverify -R run before the job can join the manual Go release-review path.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from oscar import ripping, verification, workflow_ledger

_ID = re.compile(r"[a-f0-9]{32}\Z")
_AUDIO = re.compile(r"audio/((?:0?[1-9]|[1-9]\d{1,2})) - [^/\\]+\.flac\Z")
_TABLE = re.compile(
    r"(?m)^\s*.*?/audio/(\d{1,3}) - [^\n]+?\.flac\s+"
    r"(\d+)\s+(-?\d+)\s+([0-9A-Fa-f]{8})\s+"
    r"(\d+)\s+(-?\d+)\s+([0-9A-Fa-f]{8})\s*$"
)
_RUN_LOCK = threading.Lock()
_RUNNING: set[str] = set()


class RecoveryError(RuntimeError):
    pass


def _job(job_id: str):
    if not isinstance(job_id, str) or not _ID.fullmatch(job_id):
        raise RecoveryError("Invalid source job ID")
    return verification._safe_job(job_id)


def _load(directory: Path, job_id: str, status: str):
    for filename in ("plan.json", "state.json"):
        path = directory / filename
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 500_000:
            raise RecoveryError("Missing or unsafe source " + filename)
    plan = json.loads((directory / "plan.json").read_text(encoding="utf-8"))
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    if state.get("id") != job_id or state.get("status") != status:
        raise RecoveryError("Source rip does not have expected completed status")
    if status == "needs_verification" and state.get("returncode") != 0:
        raise RecoveryError("Original full-disc extraction was not successful")
    if status == "partial_diagnostic" and state.get("returncode") != 0:
        raise RecoveryError("Replacement diagnostic extraction was not successful")
    if plan.get("disc_id") != state.get("disc_id"):
        raise RecoveryError("Source plan and state Disc IDs disagree")
    return plan, state


def _tracks(directory: Path, state: dict, expected: set[int]):
    manifest = state.get("files_sha256")
    if not isinstance(manifest, dict) or len(manifest) != len(expected):
        raise RecoveryError("Source SHA-256 manifest does not match track selection")
    audio = directory / "audio"
    if not audio.is_dir() or audio.is_symlink():
        raise RecoveryError("Invalid source audio directory")
    files = {}
    actual = [p for p in audio.iterdir() if p.suffix.lower() == ".flac"]
    if len(actual) != len(expected):
        raise RecoveryError("Source audio has unexpected FLAC files")
    for relative, sha in manifest.items():
        if not isinstance(relative, str) or not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha):
            raise RecoveryError("Invalid source hash record")
        match = _AUDIO.fullmatch(relative)
        if not match or int(match.group(1)) in files:
            raise RecoveryError("Noncanonical or duplicate source track")
        number = int(match.group(1))
        file = verification._file_readonly(directory, relative)
        if verification._digest(file).lower() != sha.lower():
            raise RecoveryError("Source track hash changed: " + str(number))
        files[number] = (file, relative, sha.lower())
    if set(files) != expected:
        raise RecoveryError("Missing, extra or incorrect source tracks")
    return files


def _preflight(original_id: str, diagnostic_id: str, selected: list[int]):
    if original_id == diagnostic_id:
        raise RecoveryError("Original and replacement jobs must differ")
    original_dir = _job(original_id)
    diagnostic_dir = _job(diagnostic_id)
    old_plan, old_state = _load(original_dir, original_id, "needs_verification")
    new_plan, new_state = _load(diagnostic_dir, diagnostic_id, "partial_diagnostic")
    count = old_plan.get("track_count")
    if type(count) is not int or not 1 <= count <= 99:
        raise RecoveryError("Invalid original CD track count")
    if (not isinstance(selected, list) or not selected or len(selected) >= count or
            any(type(n) is not int or not 1 <= n <= count for n in selected) or
            len(set(selected)) != len(selected)):
        raise RecoveryError("Select unique replacement track numbers (not the entire CD)")
    selected = sorted(selected)
    if new_plan.get("selected_tracks") != selected:
        raise RecoveryError("Selected tracks differ from diagnostic rip plan")
    if (old_plan.get("disc_id") != new_plan.get("disc_id") or
            old_plan.get("track_count") != new_plan.get("track_count")):
        raise RecoveryError("Original and diagnostic Disc ID or track count differ")
    if old_plan.get("toc_string") and new_plan.get("toc_string") and old_plan["toc_string"] != new_plan["toc_string"]:
        raise RecoveryError("Saved physical CD TOCs differ")
    original = _tracks(original_dir, old_state, set(range(1, count + 1)))
    diagnostic = _tracks(diagnostic_dir, new_state, set(selected))
    # The original CUE must have exactly one FILE reference per track in order.
    cues = list((original_dir / "audio").glob("*.cue"))
    if len(cues) != 1 or cues[0].is_symlink() or not cues[0].is_file():
        raise RecoveryError("Expected exactly one safe original CUE in audio/")
    if cues[0].stat().st_size > 500_000:
        raise RecoveryError("CUE exceeds safety limit")
    cue = cues[0].read_text(encoding="utf-8", errors="replace")
    refs = verification._cue_refs(cue)
    if refs != [Path(original[n][1]).name for n in range(1, count + 1)]:
        raise RecoveryError("Original CUE does not exactly match ordered source FLACs")
    # Require valid prior cyanrip evidence for the retained tracks, not merely
    # FLAC decoding. Independent verification of the final copy follows.
    prior = verification.report(original_id)
    reports = prior.get("tracks") or []
    by_number = {t.get("number"): t for t in reports if isinstance(t, dict)}
    if (len(reports) != count or set(by_number) != set(range(1, count + 1)) or
            prior.get("ripping_errors") != 0 or
            any(not by_number[n].get("checks_passed") for n in range(1, count + 1) if n not in selected)):
        raise RecoveryError("Unreplaced tracks lack complete saved positive verification evidence")
    # For the diagnostic, verify the same saved cyanrip log, with no read errors.
    log_path = verification._file_readonly(diagnostic_dir, "cyanrip-console.log")
    evidence_text = verification.read_cyanrip_evidence(log_path)
    evidence = verification.parse_cyanrip_log(evidence_text)
    error_lines = re.findall(r"(?im)^\s*Ripping errors:\s*(\d+)\s*$", evidence_text)
    if len(evidence) != len(selected) or not error_lines or int(error_lines[-1]) != 0:
        raise RecoveryError("Diagnostic cyanrip log has missing tracks or reported errors")
    for number in selected:
        record = evidence.get(number)
        if not record or verification.accuraterip_assessment(record["accuraterip"])["status"] not in (
                "both_versions_matched", "single_version_matched"):
            raise RecoveryError("Replacement track lacks a full AccurateRip match")
    return {
        "original_dir": original_dir, "diagnostic_dir": diagnostic_dir,
        "original_plan": old_plan, "diagnostic_plan": new_plan,
        "original": original, "diagnostic": diagnostic, "original_verification": by_number,
        "selected": selected, "count": count, "cue_text": cue,
        "cue_name": cues[0].name, "evidence": evidence,
    }


def preview(original_id: str, diagnostic_id: str, selected: list[int]):
    info = _preflight(original_id, diagnostic_id, selected)
    return {
        "original_job_id": original_id, "diagnostic_job_id": diagnostic_id,
        "disc_id": info["original_plan"]["disc_id"], "track_count": info["count"],
        "replacement_tracks": info["selected"],
        "sources": [{"track": n,
                     "source_job_id": diagnostic_id if n in info["selected"] else original_id}
                    for n in range(1, info["count"] + 1)],
        "eligible": True,
        "warning": "Creates a new independent staging job; no source or archive files are modified. "
                   "Whole-disc independent AccurateRip must pass before manual Go review.",
    }


def _parse_trackverify(text: str, count: int):
    """Require explicit nonzero v1+v2 confidence, zero offset, unique rows."""
    results = {}
    for hit in _TABLE.finditer(text):
        number = int(hit.group(1))
        if number in results or number < 1 or number > count:
            raise RecoveryError("Unexpected duplicate or invalid trackverify result")
        c1, o1, checksum1, c2, o2, checksum2 = hit.groups()[1:]
        if int(c1) <= 0 or int(c2) <= 0 or int(o1) != 0 or int(o2) != 0:
            raise RecoveryError("Independent AccurateRip match/offset is insufficient on track " + str(number))
        results[number] = {
            "v1": {"crc": checksum1.upper(), "status": "accurately_ripped", "confidence": int(c1)},
            "v2": {"crc": checksum2.upper(), "status": "accurately_ripped", "confidence": int(c2)},
            "v1_offset": int(o1), "v2_offset": int(o2),
        }
    if set(results) != set(range(1, count + 1)):
        raise RecoveryError("Independent trackverify output lacks complete v1+v2 result rows")
    # Require the explicit per-file success lines as well as result table.
    for n in range(1, count + 1):
        if not re.search(
            r"(?im)^\s*\[\s*" + str(n) + r"/" + str(count) +
            r"\]\s+.*?/audio/\d{1,3} - [^\n]+?\.flac\s*:\s*found\s*\(confidence\s+\d+\)\s*$",
            text):
            raise RecoveryError("Trackverify did not explicitly report a match for item " + str(n))
    return results


def _rip_attempt(job_id, plan, source_file, report):
    _, relative, source_hash = source_file
    return {
        "source_type": "physical_cd_rip",
        "job_id": job_id,
        "file": relative,
        "sha256": source_hash,
        "drive_id": plan.get("stable_id"),
        "read_offset_samples": plan.get("offset_samples"),
        "verification_source": report.get("evidence_source") or "cyanrip",
        "eac_crc32": report.get("eac_crc32"),
        "accuraterip": report.get("accuraterip") or {},
        "checks_passed": report.get("checks_passed"),
    }


def _run(job_id: str, original_id: str, diagnostic_id: str, selected: list[int], *, runner=subprocess.run):
    directory = ripping.staging_root() / ("oscar-" + job_id)
    try:
        info = _preflight(original_id, diagnostic_id, selected)
        audio = directory / "audio"
        audio.mkdir(mode=0o700)
        hashes = {}
        provenance = []
        paths = []
        for n in range(1, info["count"] + 1):
            recover = n in info["selected"]
            source, relative, source_hash = (
                info["diagnostic"][n] if recover else info["original"][n])
            # A canonical original filename is preserved for exact CUE references.
            target_relative = info["original"][n][1]
            target = directory / target_relative
            with source.open("rb") as inp, target.open("xb") as out:
                shutil.copyfileobj(inp, out, length=1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
            copied_hash = verification._digest(target)
            if copied_hash != source_hash:
                raise RecoveryError("Copied track differs from source SHA-256: " + str(n))
            test = runner(["flac", "-t", "--silent", str(target)],
                          capture_output=True, timeout=180, check=False)
            if test.returncode:
                raise RecoveryError("FLAC decode failed on copied track " + str(n))
            paths.append(str(target))
            hashes[target_relative] = copied_hash
            track_source = {
                "track": n, "source_job_id": diagnostic_id if recover else original_id,
                "source_path": relative, "source_sha256": source_hash,
                "recovered_sha256": copied_hash,
                "selected_attempt": (
                    _rip_attempt(diagnostic_id, info["diagnostic_plan"], info["diagnostic"][n], info["evidence"][n])
                    if recover else
                    _rip_attempt(original_id, info["original_plan"], info["original"][n],
                                 info["original_verification"][n])
                ),
            }
            if recover:
                track_source["excluded_attempt"] = _rip_attempt(
                    original_id, info["original_plan"], info["original"][n], info["original_verification"][n])
            provenance.append(track_source)
        cue_file = audio / info["cue_name"]
        cue_file.write_text(info["cue_text"], encoding="utf-8")
        if verification._cue_refs(cue_file.read_text(encoding="utf-8")) != [
                Path(info["original"][n][1]).name for n in range(1, info["count"] + 1)]:
            raise RecoveryError("Copied CUE references are invalid")
        completed = runner(["trackverify", "-R", "-V", "normal", *paths],
                           capture_output=True, text=True, timeout=1800, check=False)
        text = (completed.stdout or "") + "\n" + (completed.stderr or "")
        # Keep the original independent verifier transcript for future audits,
        # including failure diagnostics. Never modify any source-job log.
        with (directory / "trackverify-console.log").open("x", encoding="utf-8") as record:
            record.write(text[:2_000_000])
            record.flush()
            os.fsync(record.fileno())
        if completed.returncode != 0:
            raise RecoveryError("Independent trackverify failed; see recovery log")
        ar = _parse_trackverify(text, info["count"])
        ripping._atomic_json(directory / "recovery-sources.json", {
            "format": "OSCAR_TRACK_RECOVERY_V1", "original_job_id": original_id,
            "diagnostic_job_id": diagnostic_id, "disc_id": info["original_plan"]["disc_id"],
            "track_count": info["count"], "tracks": provenance,
        })
        state = {
            "id": job_id, "stable_id": "recovery", "disc_id": info["original_plan"]["disc_id"],
            "status": "needs_verification", "returncode": 0,
            "flac_count": info["count"], "files_sha256": hashes,
            "warning": "Recovered full CD: independent trackverify; operator edition review required.",
            "created_at": time.time(),
        }
        ripping._atomic_json(directory / "state.json", state)
        report_tracks = []
        for item in provenance:
            n = item["track"]
            result = {
                "number": n, "file": info["original"][n][1],
                "sha256_matches": True, "flac_decodes": True,
                "eac_crc32": None, "accuraterip": {v: ar[n][v] for v in ("v1", "v2")},
                "accuraterip_assessment": verification.accuraterip_assessment(ar[n]),
                "evidence_source": "independent_trackverify_R",
                "checks_passed": True, "source_job_id": item["source_job_id"],
            }
            report_tracks.append(result)
        report = {
            "job_id": job_id, "status": "checks_passed", "checked_at": time.time(),
            "verification_method": "independent_trackverify_R_v1_v2",
            "accuraterip_coverage": "both_versions", "single_version_tracks": [],
            "expected_tracks": info["count"], "flac_count": info["count"],
            "cue": {"found": 1, "references_match": True, "track_references": info["count"]},
            "ripping_errors": 0, "tracks": report_tracks,
            "recovery_sources": {"original_job_id": original_id, "diagnostic_job_id": diagnostic_id},
            "notes": [
                "Verified using independent audiotools trackverify -R; both AR versions with offset zero.",
                "Individual source SHA-256 compared with independent recovered FLAC copies.",
                "This does not establish physical MusicBrainz release edition or CTDB.",
                "Source jobs, original FLAC/CUE/logs and archive remain unchanged.",
            ],
        }
        ripping._atomic_json(directory / "verification-report.json", report)
        # Recovery ALWAYS goes to operator-review mode even if Best Guess auto
        # publication is enabled in global settings.
        workflow_ledger.register_recovery(job_id)
    except Exception as exc:
        existing = directory / "state.json"
        state = (json.loads(existing.read_text()) if existing.is_file() else
                 {"id": job_id, "disc_id": "", "stable_id": "recovery"})
        state["status"] = "recovery_failed"
        state["error"] = f"{type(exc).__name__}: {exc}"[:500]
        ripping._atomic_json(directory / "state.json", state)
    finally:
        with _RUN_LOCK:
            _RUNNING.discard(job_id)


def start(original_id: str, diagnostic_id: str, selected: list[int], confirmation: str):
    if confirmation != "CREATE_RECOVERED_STAGING":
        raise RecoveryError("Explicit recovery confirmation required")
    if not ripping.enabled():
        raise RecoveryError("Experimental ripping disabled")
    info = _preflight(original_id, diagnostic_id, selected)
    if shutil.which("flac") is None or shutil.which("trackverify") is None:
        raise RecoveryError("Recovery requires flac and audiotools trackverify in OSCAR image")
    job_id = uuid.uuid4().hex
    directory = ripping.staging_root() / ("oscar-" + job_id)
    directory.mkdir(mode=0o700)
    plan = dict(info["original_plan"])
    plan["recovery"] = {
        "format": "OSCAR_TRACK_RECOVERY_V1", "original_job_id": original_id,
        "diagnostic_job_id": diagnostic_id, "selected_tracks": info["selected"],
    }
    plan["warning"] = "Reconstructed full CD; independent AccurateRip and manual release review required."
    ripping._atomic_json(directory / "plan.json", plan)
    ripping._atomic_json(directory / "state.json", {
        "id": job_id, "stable_id": "recovery", "disc_id": plan["disc_id"],
        "status": "recovery_running", "created_at": time.time(),
    })
    with _RUN_LOCK:
        _RUNNING.add(job_id)
    threading.Thread(target=_run,
                     args=(job_id, original_id, diagnostic_id, info["selected"]),
                     daemon=True, name="oscar-recover-" + job_id[:8]).start()
    return {"job_id": job_id, "status": "recovery_running",
            "message": "New independent staging copy started; source jobs untouched."}


def status(job_id: str):
    directory = _job(job_id)
    state_path = directory / "state.json"
    if state_path.is_symlink() or not state_path.is_file():
        raise RecoveryError("Recovery state unavailable")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    plan_path = directory / "plan.json"
    if plan_path.is_symlink() or not plan_path.is_file():
        raise RecoveryError("Recovery plan unavailable")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    recovery = plan.get("recovery")
    if not isinstance(recovery, dict) or recovery.get("format") != "OSCAR_TRACK_RECOVERY_V1":
        raise RecoveryError("Not a Track Recovery staging job")
    with _RUN_LOCK:
        active = job_id in _RUNNING
    phase = state.get("status")
    if phase == "recovery_running" and not active:
        phase = "interrupted"
    report = verification.report(job_id) if phase == "needs_verification" else None
    return {
        "job_id": job_id, "status": phase, "error": state.get("error"),
        "original_job_id": recovery["original_job_id"],
        "diagnostic_job_id": recovery["diagnostic_job_id"],
        "replacement_tracks": recovery["selected_tracks"],
        "verification": report,
        "message": ("Complete independent AR confirmation; review physical release in Go."
                    if report and report.get("status") == "checks_passed"
                    else "Staging retained; no automatic publishing or cleanup."),
    }
