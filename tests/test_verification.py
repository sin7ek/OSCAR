"""Offline verification using cyanrip 0.9.3-style log fragments (no disc needed)."""
import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oscar.api import app
from oscar import verification, ripping

JOB = "f41806152a614b1a9006b10456b9bbd4"
TOKEN = "0123456789abcdef0123456789abcdef"


def log_track(n, match=True):
    status = "accurately ripped" if match else "not accurately ripped"
    return f"""Track {n}
  EAC CRC32:     6067096C
  Accurip:       disc found in database (max confidence: 48)
    Accurip v1:  E5AAA4FA ({status}, confidence 26)
    Accurip v2:  66B67734 ({status}, confidence 48)

  Metadata:
    track:         {n}
    tracktotal:    2
    discid:        ROkQlooU5tDdgVZOkfXXTy.S4oU-

  File(s):
    audio/{n:02d} - Unknown track.flac

"""


@pytest.fixture
def stage(tmp_path, monkeypatch):
    root = tmp_path / "stage"
    root.mkdir()
    directory = root / ("oscar-" + JOB)
    directory.mkdir()
    audio = directory / "audio"
    audio.mkdir()
    hashes = {}
    for n in (1, 2):
        path = audio / f"{n:02d} - Unknown track.flac"
        path.write_bytes(("FLAC " + str(n)).encode())
        hashes[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (audio / "Unknown disc.cue").write_text(
        'FILE "01 - Unknown track.flac" WAVE\n'
        '  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n'
        'FILE "02 - Unknown track.flac" WAVE\n'
        '  TRACK 02 AUDIO\n    INDEX 01 00:00:00\n')
    (directory / "cyanrip-console.log").write_text(log_track(1) + log_track(2) + "Ripping errors: 0\n")
    (directory / "plan.json").write_text(json.dumps({"track_count": 2}))
    (directory / "state.json").write_text(json.dumps({
        "id": JOB, "returncode": 0, "status": "needs_verification", "files_sha256": hashes}))
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(root))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.setattr(verification, "_RUNNING", set())
    return directory


def mock_flac(args, **kwargs):
    assert args[:3] == ["flac", "-t", "--silent"]
    return SimpleNamespace(returncode=0)


def test_log_parser_identifies_track_and_confidence():
    record = verification.parse_cyanrip_log(log_track(1))[1]
    assert record["eac_crc32"] == "6067096C"
    assert record["accuraterip"]["v1"]["confidence"] == 26
    assert record["accuraterip"]["v2"]["confidence"] == 48


def test_report_full_success_and_source_files_unchanged(stage):
    before = {f.name: f.read_bytes() for f in (stage / "audio").iterdir()}
    report = verification._verify(stage, JOB, runner=mock_flac)
    assert report["status"] == "checks_passed"
    assert report["cue"]["references_match"]
    assert len(report["tracks"]) == 2
    assert report["tracks"][1]["accuraterip"]["v2"]["status"] == "accurately_ripped"
    assert before == {f.name: f.read_bytes() for f in (stage / "audio").iterdir()}


def test_mismatch_or_missing_ar_never_passes(stage):
    log = stage / "cyanrip-console.log"
    log.write_text(log_track(1) + log_track(2, match=False) + "Ripping errors: 0\n")
    report = verification._verify(stage, JOB, runner=mock_flac)
    assert report["status"] == "review_required"
    assert not report["tracks"][1]["checks_passed"]


def test_sha256_mismatch_not_missed(stage):
    (stage / "audio" / "01 - Unknown track.flac").write_bytes(b"CHANGED")
    report = verification._verify(stage, JOB, runner=mock_flac)
    assert report["status"] == "review_required"
    assert not report["tracks"][0]["sha256_matches"]


def test_cue_missing_track_requires_review(stage):
    cue = stage / "audio" / "Unknown disc.cue"
    cue.write_text('FILE "01 - Unknown track.flac" WAVE\n')
    report = verification._verify(stage, JOB, runner=mock_flac)
    assert report["status"] == "review_required"


def test_missing_verification_not_marked_completed(stage):
    assert verification.report(JOB)["status"] == "not_started"


def test_api_token_required(stage):
    client = TestClient(app)
    path = f"/api/rip/jobs/{JOB}/verification"
    assert client.post(path).status_code == 403
    assert client.get(path).status_code == 403
    assert client.get(path, headers={"X-OSCAR-RIP-TOKEN": TOKEN}).json()["status"] == "not_started"


def test_cannot_verify_running_or_failed_job(stage):
    state = stage / "state.json"
    value = json.loads(state.read_text())
    value["status"] = "running"
    state.write_text(json.dumps(value))
    with pytest.raises(ripping.RipError, match="Only a successfully completed"):
        verification.start(JOB)


def test_rejects_path_traversal(stage):
    with pytest.raises(ripping.RipError, match="Invalid job ID"):
        verification.report("../etc/passwd")


def test_frontend_has_verification_panel():
    html = TestClient(app).get("/").text
    assert "Verify staged rip" in html
    assert "AccurateRip" in html


def test_progress_heavy_log_over_6mb_still_verifies(stage):
    logfile = stage / "cyanrip-console.log"
    progress = b"Ripping and encoding track 1, progress - 71.22%, ETA " + b"x"*512 + b"\r"
    # Bigger than old 6 MB ceiling; content is bounded to relevant lines.
    with logfile.open("wb") as output:
        output.write(progress * 12500)
        output.write((log_track(1) + log_track(2) + "Ripping errors: 0\n").encode())
    assert logfile.stat().st_size > 6_000_000
    filtered = verification.read_cyanrip_evidence(logfile)
    assert len(filtered) < 2000
    report = verification._verify(stage, JOB, runner=mock_flac)
    assert report["status"] == "checks_passed"


def test_retry_preserves_failed_report_and_creates_new_one(stage, monkeypatch):
    original = {"job_id": JOB, "status": "review_required",
                "error": "RipError: Rip log too large for automatic verification"}
    (stage / "verification-report.json").write_text(json.dumps(original))
    monkeypatch.setattr(verification, "_verify", lambda path, jobid: {
        "job_id": jobid, "status": "checks_passed", "tracks": []})
    result = verification.start(JOB)
    assert result["status"] == "running"
    for _ in range(200):
        current = verification.report(JOB)
        if current["status"] != "running":
            break
        time.sleep(.01)
    assert current["status"] == "checks_passed"
    backups = list(stage.glob("verification-report-previous-*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == original


def test_successful_report_is_not_overwritten(stage):
    old = {"job_id": JOB, "status": "checks_passed"}
    (stage / "verification-report.json").write_text(json.dumps(old))
    assert verification.start(JOB) == old


def test_v2_only_confirmed_is_not_a_rip_failure(stage):
    def v2only(n):
        return f"""Track {n}
  EAC CRC32:     6067096C
  Accurip:       disc found in database (max confidence: 4)
    Accurip v2:  66B67734 (accurately ripped, confidence 4)

  Metadata:
    track:         {n}
    tracktotal:    2
    discid:        ROkQlooU5tDdgVZOkfXXTy.S4oU-

  File(s):
    audio/{n:02d} - Unknown track.flac

"""
    (stage / "cyanrip-console.log").write_text(v2only(1)+v2only(2)+"Ripping errors: 0\n")
    report=verification._verify(stage,JOB,runner=mock_flac)
    assert report["status"]=="checks_passed"
    assert report["accuraterip_coverage"]=="single_version_on_some_tracks"
    assert report["single_version_tracks"]==[1,2]
    assert all(t["accuraterip_assessment"]["absent_versions"]==["v1"] for t in report["tracks"])
    assert all(t["accuraterip"]["v2"]["confidence"]==4 for t in report["tracks"])


def test_explicit_v1_mismatch_with_v2_match_still_requires_review(stage):
    (stage / "cyanrip-console.log").write_text(
        log_track(1,match=True).replace(
            "Accurip v1:  E5AAA4FA (accurately ripped, confidence 26)",
            "Accurip v1:  E5AAA4FA (not accurately ripped, confidence 0)")
        +log_track(2)+"Ripping errors: 0\n")
    report=verification._verify(stage,JOB,runner=mock_flac)
    assert report["status"]=="review_required"
    assert report["tracks"][0]["accuraterip_assessment"]["status"]=="review_required"
    assert not report["tracks"][0]["checks_passed"]


def test_missing_both_accuraterip_versions_requires_review(stage):
    log = log_track(1)+log_track(2)
    log = "\n".join(line for line in log.splitlines()
                    if "Accurip v1:" not in line and "Accurip v2:" not in line)
    (stage / "cyanrip-console.log").write_text(log+"\nRipping errors: 0\n")
    result=verification._verify(stage,JOB,runner=mock_flac)
    assert result["status"]=="review_required"
    assert all(t["accuraterip_assessment"]["status"]=="no_confirmed_match" for t in result["tracks"])


def test_unpadded_cyanrip_tracks_pass_strict_checks_without_modifying_source(stage):
    """Cyanrip 0.9.3 can output '1 - Unknown track.flac', not only '01 - ...'."""
    audio = stage / "audio"
    for n in (1, 2):
        (audio / f"{n:02d} - Unknown track.flac").rename(
            audio / f"{n} - Unknown track.flac")
    hashes = {}
    for n in (1, 2):
        path = audio / f"{n} - Unknown track.flac"
        hashes[f"audio/{path.name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
    state_path = stage / "state.json"
    state = json.loads(state_path.read_text())
    state["files_sha256"] = hashes
    state_path.write_text(json.dumps(state))
    cue = next(audio.glob("*.cue"))
    cue.write_text(cue.read_text().replace("01 - Unknown", "1 - Unknown")
                   .replace("02 - Unknown", "2 - Unknown"))
    log = stage / "cyanrip-console.log"
    log.write_text(log_track(1).replace("audio/01 -", "audio/1 -") +
                   log_track(2).replace("audio/02 -", "audio/2 -") +
                   "Ripping errors: 0\\n")
    before = {p.name: p.read_bytes() for p in audio.iterdir()}
    result = verification._verify(stage, JOB, runner=mock_flac)
    assert result["status"] == "checks_passed"
    assert result["cue"]["references_match"]
    assert [track["file"] for track in result["tracks"]] == [
        "audio/1 - Unknown track.flac", "audio/2 - Unknown track.flac"]
    assert all(track["accuraterip_assessment"]["status"] == "both_versions_matched"
               for track in result["tracks"])
    assert before == {p.name: p.read_bytes() for p in audio.iterdir()}


@pytest.mark.parametrize("bad", [
    "audio/0 - Unknown track.flac", "audio/000 - Unknown track.flac",
    "audio/1 - ../escape.flac", "audio/1 - bad\\\\name.flac",
    "audio/subfolder/1 - Unknown track.flac", "../audio/1 - Unknown track.flac",
])
def test_unpadded_track_parser_still_rejects_unsafe_or_noncanonical_paths(bad):
    assert verification._AUDIO_NAME.fullmatch(bad) is None
