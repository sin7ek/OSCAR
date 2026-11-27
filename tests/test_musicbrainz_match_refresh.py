"""Read-only regression checks for a new MusicBrainz Disc ID association."""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from oscar import match_refresh
from oscar.api import musicbrainz_refresh_accepted_match
from oscar.web import PAGE

JOB = "b68488f667cc492d8dd94f90717cdb28"
DISC = "VxfLacbEsNFCv5Ua4bvIeBIQ3jQ-"
RELEASE = "fa89edc1-32f9-4290-8788-bbac2e366a46"
TOC = "1 12 251219 150 24080 45782 68279 94060 110749 132469 152116 171031 192808 211313 231287"


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    from oscar import verification
    saved = {
        "identification_mode": "semi_automatic",
        "accepted_release_id": RELEASE,
        "release_match_status": "INFERRED_OPERATOR_ACCEPTED",
    }
    folder = tmp_path / JOB
    folder.mkdir()
    plan = folder / "plan.json"
    plan.write_text(json.dumps({"disc_id": DISC, "toc_string": TOC}))
    report = {
        "job_id": JOB, "status": "checks_passed", "expected_tracks": 12,
        "tracks": [{"checks_passed": True} for _ in range(12)],
    }
    monkeypatch.setattr(match_refresh.musicbrainz, "lookup_enabled", lambda: True)
    monkeypatch.setattr(match_refresh.workflow_ledger, "refresh", lambda job: saved)
    monkeypatch.setattr(verification, "_safe_job", lambda job: folder)
    monkeypatch.setattr(verification, "_load_job", lambda root, job: {"disc_id": DISC})
    monkeypatch.setattr(verification, "report", lambda job: report)
    return saved, report, plan


def mb_result(attached=True, *, status=None):
    return {
        "release_id": RELEASE,
        "status": status or ("exact_disc_id_and_track_count" if attached else "no_exact_medium_match"),
        "matched_media": ([{"position": 1, "format": "CD", "disc_id_attached": True,
                           "track_count_matches": True}] if attached else []),
    }


def test_fresh_disc_id_match_retains_historical_status(evidence):
    saved, report, plan = evidence
    before = plan.read_bytes()
    result = match_refresh.refresh_accepted_match(JOB, lookup=lambda *args: mb_result())
    assert result["lookup_status"] == "disc_id_now_attached"
    assert result["matched_medium_position"] == 1
    assert result["historical_release_match_status"] == "INFERRED_OPERATOR_ACCEPTED"
    assert result["physical_edition_verified"] is False
    assert result["persisted_provenance_unchanged"] is True
    assert plan.read_bytes() == before
    assert saved["release_match_status"] == "INFERRED_OPERATOR_ACCEPTED"
    assert len(report["tracks"]) == 12


def test_missing_or_ambiguous_match_never_upgrades_provenance(evidence):
    for current, expected in [
        (mb_result(False), "disc_id_not_attached"),
        (mb_result(True, status="review_disc_id_or_count_ambiguity"), "ambiguous_or_incompatible"),
    ]:
        result = match_refresh.refresh_accepted_match(JOB, lookup=lambda *args: current)
        assert result["lookup_status"] == expected
        assert result["physical_edition_verified"] is False


def test_incomplete_verification_blocks_network_lookup(evidence):
    _, report, _ = evidence
    report["tracks"][0]["checks_passed"] = False
    called = []
    with pytest.raises(ValueError, match="Complete verified"):
        match_refresh.refresh_accepted_match(JOB, lookup=lambda *args: called.append(args))
    assert called == []


def test_wrong_disc_id_or_inferred_status_blocks(evidence):
    saved, _, plan = evidence
    saved["accepted_release_id"] = ""
    with pytest.raises(ValueError, match="accepted"):
        match_refresh.refresh_accepted_match(JOB)
    saved["accepted_release_id"] = RELEASE
    plan.write_text(json.dumps({"disc_id": "wrong", "toc_string": TOC}))
    with pytest.raises(ValueError, match="Disc ID"):
        match_refresh.refresh_accepted_match(JOB)


def test_gui_offer_is_separate_from_go_advance():
    assert "Refresh MusicBrainz match (read-only)" in PAGE
    assert "/musicbrainz/refresh-match" in PAGE
    assert "Historical status:" in PAGE
    assert "Choose the physical CD" in PAGE


def test_refresh_endpoint_requires_rip_auth(monkeypatch):
    import oscar.api as api
    monkeypatch.setattr(api, "_rip_auth", lambda *args: (_ for _ in ()).throw(
        HTTPException(status_code=403, detail="Not authorized")))
    with pytest.raises(HTTPException) as exc:
        musicbrainz_refresh_accepted_match(JOB, object())
    assert exc.value.status_code == 403

def test_disc_two_is_the_only_compatible_candidate(evidence):
    media = [{"position": 1, "format": "CD", "track_count": 10},
             {"position": 2, "format": "CD", "track_count": 12,
              "tracks": [{"length_ms": 1000}]}]
    current = dict(mb_result(False), all_media=media, total_media=2)
    result = match_refresh.refresh_accepted_match(JOB, lookup=lambda *args: current)
    assert [m["position"] for m in result["media"] if m["compatible"]] == [2]
    assert result["media"][1]["duration_differences"] == [
        {"track": 1, "rip_ms": 319067, "musicbrainz_ms": 1000}]
    assert "toc=" + TOC.replace(" ", "+") in result["musicbrainz_attach_url"]


def test_missing_compatible_medium_explains_track_counts(evidence):
    current = dict(mb_result(False), total_media=2, all_media=[
        {"position": 1, "format": "CD", "track_count": 10},
        {"position": 2, "format": "CD", "track_count": 11}])
    result = match_refresh.refresh_accepted_match(JOB, lookup=lambda *args: current)
    assert [item["track_count"] for item in result["media"]] == [10, 11]
    assert result["musicbrainz_attach_url"] is None
