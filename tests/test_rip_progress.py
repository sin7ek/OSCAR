"""Read-only live rip progress, approximate ETA, and safe dashboard UI."""
import json
import time

from fastapi.testclient import TestClient
from oscar import ripping
from oscar.api import app


JOB = "a" * 32


def prepare(tmp_path, monkeypatch, *, total=5, started=1000):
    root = tmp_path / "staging"
    job = root / ("oscar-" + JOB)
    audio = job / "audio"
    audio.mkdir(parents=True)
    (job / "plan.json").write_text(json.dumps({"track_count": total}))
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(root))
    return audio, {"id": JOB, "status": "running", "started_at": started}


def test_no_track_output_has_0_and_no_eta(tmp_path, monkeypatch):
    _, job = prepare(tmp_path, monkeypatch, total=5)
    data = ripping._progress(job, now=1010)
    assert data["percent"] == 0
    assert data["total_tracks"] == 5
    assert data["completed_tracks"] == 0
    assert data["eta_seconds"] is None
    assert data["elapsed_seconds"] == 10


def test_active_flac_never_counted_finished(tmp_path, monkeypatch):
    audio, job = prepare(tmp_path, monkeypatch, total=5)
    (audio / "01 - First.flac").write_bytes(b"actively writing")
    report = ripping._progress(job, now=1020)
    assert report["completed_tracks"] == 0
    assert report["current_track"] == 1
    assert report["percent"] == 0
    (audio / "02 - Second.flac").write_bytes(b"actively writing")
    report = ripping._progress(job, now=1040)
    assert report["completed_tracks"] == 1
    assert report["percent"] == 20
    assert report["eta_kind"] == "unavailable"
    (audio / "03 - Third.flac").write_bytes(b"actively writing")
    report = ripping._progress(job, now=1060)
    assert report["completed_tracks"] == 2
    assert report["percent"] == 40
    assert report["eta_kind"] == "rough_track_average"
    assert report["eta_seconds"] == 90


def test_no_false_progress_from_gaps_symlink_or_wrong_extension(tmp_path, monkeypatch):
    audio, job = prepare(tmp_path, monkeypatch, total=4)
    (audio / "03 - Not yet started.flac").write_bytes(b"not contiguous")
    (audio / "02 - Wrong.txt").write_bytes(b"")
    (audio / "01 - Link.flac").symlink_to(audio / "03 - Not yet started.flac")
    report = ripping._progress(job, now=1200)
    assert report["completed_tracks"] == 0
    assert report["eta_seconds"] is None
    assert report["percent"] == 0


def test_progress_never_claims_100_before_rip_finishes(tmp_path, monkeypatch):
    audio, job = prepare(tmp_path, monkeypatch, total=3)
    for i in range(1, 4):
        (audio / f"{i:02d} - Track.flac").write_bytes(b"x")
    report = ripping._progress(job, now=1300)
    assert report["completed_tracks"] == 2
    assert report["percent"] < 100
    job["status"] = "needs_verification"
    assert ripping._progress(job, now=1400) is None


def test_invalid_staging_plan_fails_without_leaking_or_mutation(tmp_path, monkeypatch):
    audio, job = prepare(tmp_path, monkeypatch)
    plan = audio.parent / "plan.json"
    plan.write_text('{"track_count":5000}')
    assert ripping._progress(job, now=1100)["percent"] is None
    plan.unlink()
    plan.symlink_to(tmp_path / "absent")
    assert ripping._progress(job, now=1100)["percent"] is None
    job["id"] = "../unsafe"
    assert ripping._progress(job, now=1100) is None


def test_dashboard_attaches_progress_to_only_active_jobs(tmp_path, monkeypatch):
    audio, job = prepare(tmp_path, monkeypatch)
    (audio / "01 - One.flac").write_bytes(b"")
    (audio / "02 - Two.flac").write_bytes(b"")
    job.update({"stable_id": "drive-a", "created_at": time.time()})
    monkeypatch.setattr(ripping, "_JOBS", {JOB: job})
    monkeypatch.setattr(ripping, "_ACTIVE", {"drive-a"})
    from types import SimpleNamespace
    monkeypatch.setattr(ripping, "discover_settings",
                        lambda: SimpleNamespace(drives=[
                            SimpleNamespace(stable_id="drive-a", label="Drive A",
                                            enabled=True, offset_samples=6)]))
    monkeypatch.setattr(ripping, "inspect_drives",
                        lambda: [{"stable_id": "drive-a", "device": "/dev/sr0"}])
    result = ripping.dashboard()
    assert result["drives"][0]["job"]["progress"]["completed_tracks"] == 1
    assert result["drives"][0]["status"] == "ripping"


def test_html_progress_and_polling_available_without_new_routes():
    html = TestClient(app).get("/").text
    assert "appendGoRipProgress(card,drive)" in html
    assert "Extraction progress" in html
    assert "rough_track_average" in html
    assert "scheduleGoDashboardRefresh()" in html
