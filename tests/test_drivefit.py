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
    assert result["version"] == 1 and result["mode"] == "read_only_retrospective"
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
    assert "DriveFit" in html and "Diagnostics" in html
