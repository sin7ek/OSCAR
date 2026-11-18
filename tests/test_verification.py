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
