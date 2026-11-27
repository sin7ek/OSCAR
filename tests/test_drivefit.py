"""DriveFit must remain read-only and never label a drive defective."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from oscar import drivefit, ripping


def _write_job(root, number, drive, *, status="needs_verification",
               duration=120, verified="checks_passed", errors=0, count=12):
    job_id = f"{number:032x}"
    job = root / ("oscar-" + job_id)
    job.mkdir()
    (job / "state.json").write_text(json.dumps({
        "id": job_id, "stable_id": drive, "status": status,
        "started_at": 100000 + number * 1000,
        "finished_at": 100000 + number * 1000 + duration,
        "disc_id": "A" * 27 + "-",
    }))
    (job / "plan.json").write_text(json.dumps({
        "stable_id": drive, "track_count": count,
    }))
    if verified:
        (job / "verification-report.json").write_text(json.dumps({
            "job_id": job_id, "status": verified, "ripping_errors": errors,
        }))
    return job


@pytest.fixture
def history(tmp_path, monkeypatch):
    root = tmp_path / "staging"
    root.mkdir()
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(root))
    monkeypatch.setenv("OSCAR_CONFIG_PATH", str(tmp_path / "config" / "settings.json"))
    configured = SimpleNamespace(drives=[
        SimpleNamespace(stable_id="drive-lg", label="LG GH24NS95", enabled=True),
        SimpleNamespace(stable_id="drive-other", label="Optiarc", enabled=True),
    ])
    monkeypatch.setattr(drivefit, "discover_settings", lambda: configured)
    monkeypatch.setattr(drivefit, "inspect_drives", lambda: [
        {"stable_id": "drive-lg", "firmware": "1.00", "identity_persistent": True},
    ])
    return root


def test_drivefit_uses_only_saved_history_and_never_probes_disc(history, monkeypatch):
    for idx in range(5):
        _write_job(history, idx + 1, "drive-lg", duration=100 + idx * 10)
    _write_job(history, 10, "drive-lg", status="failed", duration=20,
               verified="review_required", errors=2)
    _write_job(history, 20, "drive-other", duration=55)
    monkeypatch.setattr(ripping, "read_toc", lambda *_: pytest.fail("Must not probe CD"))
    result = drivefit.report()
    assert result["version"] == 2 and result["mode"] == "read_only_retrospective"
    lg, other = result["drives"]
    assert lg["sample_count"] == 6
    assert lg["extractions_completed"] == 5
    assert lg["verified_jobs"] == 5
    assert lg["review_required_jobs"] == 1
    assert lg["failed_or_interrupted_jobs"] == 1
    assert lg["ripping_error_reports"] == 1
    assert lg["median_duration_seconds"] == 120
    assert lg["assessment"] == "observations_available"
    assert other["assessment"] == "insufficient_data"
    assert not other["present"]


def test_drivefit_ignores_tampered_symlink_and_unrelated_jobs(history, tmp_path):
    original = _write_job(history, 1, "drive-lg")
    _write_job(history, 2, "unconfigured")
    unsafe = history / ("oscar-" + "f" * 32)
    unsafe.symlink_to(original, target_is_directory=True)
    (original / "verification-report.json").unlink()
    (original / "verification-report.json").symlink_to(tmp_path / "not-a-report")
    result = drivefit.report()
    lg = result["drives"][0]
    assert lg["sample_count"] == 1
    assert lg["verified_jobs"] == 0
    assert lg["recent_jobs"][0]["verification_status"] == "not_available"
    assert lg["assessment"] == "insufficient_data"


def test_drivefit_does_not_label_accuraterip_absence_as_drive_failure(history):
    _write_job(history, 1, "drive-lg", verified="review_required", errors=0)
    result = drivefit.report()
    assert result["drives"][0]["review_required_jobs"] == 1
    assert result["drives"][0]["ripping_error_reports"] == 0
    assert "replacement verdict" in result["drives"][0]["note"]
    assert any("database coverage" in x for x in result["limitations"])


def test_drivefit_route_requires_auth_and_does_not_start_a_rip(history, monkeypatch):
    from fastapi.testclient import TestClient
    from oscar.api import app
    monkeypatch.setenv("OSCAR_RIP_TOKEN", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.delenv("OSCAR_TRUSTED_LOCAL_UI", raising=False)
    client = TestClient(app)
    assert client.get("/api/diagnostics/drivefit").status_code == 403
    response = client.get("/api/diagnostics/drivefit", headers={
        "X-OSCAR-RIP-TOKEN": "0123456789abcdef0123456789abcdef",
    })
    assert response.status_code == 200
    assert response.json()["mode"] == "read_only_retrospective"
    html = client.get("/").text
    assert "DriveFit" in html and "Verified recovery contributions" in html


def test_drivefit_history_survives_staging_cleanup(history, monkeypatch):
    import shutil
    from oscar import drivefit_history
    job_dir = _write_job(history, 42, "drive-lg", duration=444,
                         verified="checks_passed", errors=0, count=6)
    state = json.loads((job_dir / "state.json").read_text())
    assert drivefit_history.record_rip(state, 6)
    assert drivefit_history.record_verification(state["id"], {
        "job_id": state["id"], "status": "checks_passed", "ripping_errors": 0,
    })
    # Duplicate callbacks are idempotent and keep one history row.
    assert drivefit_history.record_rip(state, 6)
    before = drivefit.report()["drives"][0]
    assert before["sample_count"] == 1 and before["verified_jobs"] == 1
    shutil.rmtree(job_dir)  # Disposable fixture only, never real archive files.
    after = drivefit.report()["drives"][0]
    assert after["sample_count"] == 1
    assert after["verified_jobs"] == 1
    assert after["recent_jobs"][0]["duration_seconds"] == 444
    assert after["recent_jobs"][0]["tracks"] == 6
    assert after["recent_jobs"][0]["ripping_errors"] == 0


def test_drivefit_verification_requires_existing_rip_history(history):
    from oscar import drivefit_history
    assert not drivefit_history.record_verification("f" * 32, {
        "job_id": "f" * 32, "status": "checks_passed", "ripping_errors": 0,
    })
    assert drivefit_history.read_history({"drive-lg"}) == []


def test_speed_accuracy_and_reliability_use_only_appropriate_rips(history):
    for idx in range(1, 11):
        job = _write_job(history, idx, "drive-lg", duration=240, count=1)
        plan = job / "plan.json"
        plan.write_text(json.dumps({"stable_id": "drive-lg", "track_count": 1,
                                    "toc_string": "1 1 180150 150"}))
    _write_job(history, 11, "drive-lg", status="partial_diagnostic", duration=5, verified=None)
    _write_job(history, 12, "drive-lg", status="running", duration=5, verified=None)
    drive = drivefit.report()["drives"][0]
    assert drive["sample_count"] == 11
    assert drive["median_speed"] == 10
    assert drive["timed_verified_rips"] == 10
    assert drive["diagnostic_jobs"] == 1
    assert {tag["name"] for tag in drive["badges"]} == {"Accurate", "Reliable"}


def test_recovery_is_credited_only_to_verified_replacement_drive(history):
    original = _write_job(history, 1, "drive-other")
    diagnostic = _write_job(history, 2, "drive-lg", status="partial_diagnostic", verified=None)
    diagnostic_state = diagnostic / "state.json"
    state = json.loads(diagnostic_state.read_text())
    state["selected_tracks"] = [7, 8]
    diagnostic_state.write_text(json.dumps(state))
    recovered = _write_job(history, 3, "recovery")
    (recovered / "recovery-sources.json").write_text(json.dumps({
        "format": "OSCAR_TRACK_RECOVERY_V1", "original_job_id": original.name[6:],
        "diagnostic_job_id": diagnostic.name[6:],
        "tracks": [{"track": n, "source_job_id": diagnostic.name[6:]} for n in (7, 8)],
    }))
    result = {"status": "accurately_ripped", "confidence": 5}
    (recovered / "verification-report.json").write_text(json.dumps({
        "job_id": recovered.name[6:], "status": "checks_passed",
        "verification_method": "independent_trackverify_R_v1_v2",
        "tracks": [
            {"number": 7, "source_job_id": diagnostic.name[6:], "checks_passed": True,
             "accuraterip": {"v1": result, "v2": result}},
            {"number": 8, "source_job_id": diagnostic.name[6:], "checks_passed": True,
             "accuraterip": {"v1": result}},
        ],
    }))
    lg, optiarc = drivefit.report()["drives"]
    assert [row["track"] for row in lg["recovery_tracks"]] == [7]
    assert [tag["name"] for tag in lg["badges"]] == ["Recovery"]
    assert not optiarc["recovery_tracks"]


def test_history_keeps_toc_length_and_diagnostic_flag_for_usb_drive(history):
    from oscar import drivefit_history
    state = {"id": "a" * 32, "stable_id": "usb-lg-0:0", "status": "partial_diagnostic"}
    plan = {"selected_tracks": [7], "toc_string": "1 1 180150 150"}
    assert drivefit_history.record_rip(state, 1, plan=plan)
    [saved] = drivefit_history.read_history({"usb-lg-0:0"})
    assert saved["audio_seconds"] == 2400
    assert saved["diagnostic"]


def test_recovery_compares_difficult_cd_results_across_drives(history):
    for idx, drive, passing, errors in ((1, "drive-lg", 2, 0), (2, "drive-other", 1, 3)):
        job = _write_job(history, idx, drive, count=2, verified="review_required", errors=errors)
        report = job / "verification-report.json"
        data = json.loads(report.read_text())
        data["tracks"] = [{"number": number, "checks_passed": number <= passing} for number in (1, 2)]
        report.write_text(json.dumps(data))
    lg, optiarc = drivefit.report()["drives"]
    assert lg["difficult_disc_comparisons"][0]["verified_tracks"] == 2
    assert optiarc["difficult_disc_comparisons"][0]["ripping_errors"] == 3
    assert lg["difficult_disc_comparisons"][0]["strictly_best"]
    assert not optiarc["difficult_disc_comparisons"][0]["strictly_best"]
    assert [tag["name"] for tag in lg["badges"]] == ["Recovery"]
    assert not optiarc["badges"]



def test_relative_tags_rank_speed_and_errors_independently(history):
    # Lower extraction time wins after adjusting for audio duration, even if
    # that drive reported more errors overall.
    for idx in range(1, 6):
        for drive, duration, errors, number in (
            ("drive-lg", 600, 0, idx), ("drive-other", 300, 1, 10 + idx),
        ):
            if errors:
                _write_job(history, number + 20, drive, count=1, verified="review_required", errors=errors)
            job = _write_job(history, number, drive, duration=duration, count=1)
            (job / "plan.json").write_text(json.dumps({
                "stable_id": drive, "track_count": 1, "toc_string": "1 1 180150 150",
            }))
    result = drivefit.report()
    lg, other = result["drives"]
    assert [item["value"] for item in result["leaderboards"]["speed"]] == [8, 4]
    assert [item["value"] for item in result["leaderboards"]["errors"]] == [0, 0.5]
    assert {tag["name"] for tag in lg["badges"]} == {"Accurate", "Low errors"}
    assert {tag["name"] for tag in other["badges"]} == {"Fast"}
