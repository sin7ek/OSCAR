"""RipReview only recommends actions using the evidence for this particular rip."""
import json

import pytest

from oscar import rip_review, ripping


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(tmp_path))
    job_id = "b" * 32
    directory = tmp_path / ("oscar-" + job_id)
    directory.mkdir()

    def save(name, **fields):
        (directory / name).write_text(json.dumps({"job_id": job_id, **fields}))

    save("state.json", id=job_id, status="needs_verification", stable_id="source",
         disc_id="d" * 28, files_sha256={"audio/file.flac": "test"})
    return job_id, save


def test_missing_reference_and_failed_track_have_different_routes(job):
    job_id, save = job
    track = {"number": 7, "sha256_matches": True, "flac_decodes": True,
             "accuraterip_assessment": {"status": "no_confirmed_match"}}
    report = {"status": "review_required", "tracks": [track], "ripping_errors": 0,
              "cue": {"references_match": True}, "expected_tracks": 2, "flac_count": 2}
    report["tracks"].append({**track, "number": 8})
    save("verification-report.json", **report)
    route = rip_review.next_step(job_id, "VERIFICATION_PENDING")
    assert route["group"] == "audio_review"
    assert "incomplete" in route["reason"]
    track["accuraterip_assessment"] = {"status": "review_required"}
    save("verification-report.json", **report)
    route = rip_review.next_step(job_id, "VERIFICATION_PENDING")
    assert (route["group"], route["tracks"], route["source_drive"]) == ("reread", [7], "source")


def test_completed_verification_routes_to_edition_even_before_ledger_refresh(job):
    job_id, save = job
    save("verification-report.json", status="checks_passed")
    assert rip_review.next_step(job_id, "RIP_IN_PROGRESS")["group"] == "edition"
    save("ctdb-report.json", status="no_audio_match",
         files_sha256={"audio/file.flac": "test"})
    assert rip_review.next_step(job_id, "RELEASE_REVIEW_PENDING")["group"] == "reread"
    assert rip_review.next_step(job_id, "ARCHIVE_PUBLISHED")["group"] == "done"


def test_interrupted_job_remains_in_worklist_after_restart(job):
    job_id, save = job
    save("state.json", id=job_id, status="running", stable_id="source")
    assert rip_review.next_step(job_id, "RIP_IN_PROGRESS")["group"] == "reread"


def test_diagnostic_declines_different_disc_before_reserving_drive(monkeypatch):
    monkeypatch.setattr(ripping, "plan", lambda *args, **kwargs: {"disc_id": "a" * 28})
    with pytest.raises(ripping.RipError, match="does not match"):
        ripping.start("drive", selected_tracks=[7], expected_disc_id="b" * 28)
    assert "drive" not in ripping._ACTIVE
