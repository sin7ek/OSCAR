"""Read-only evidence comparison must not mistake a matching Disc ID for edition proof."""
import json
from fastapi.testclient import TestClient
import pytest

from oscar import physical_release
from oscar.api import app

JOB = "a"*32
RELEASE = "4b370e6c-e6d2-36a5-8c47-5337a2d77d69"
DISC = "fHRjyL_F16yLkOO1ddr2Hedl0A0-"


@pytest.fixture
def staged(tmp_path, monkeypatch):
    root = tmp_path / "staging"
    root.mkdir()
    folder = root / ("oscar-" + JOB)
    folder.mkdir()
    (folder / "state.json").write_text(json.dumps({
        "id": JOB, "status": "needs_verification", "returncode": 0, "disc_id": DISC
    }))
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(root))
    monkeypatch.setattr(physical_release.verification, "report",
                        lambda job: {"status": "checks_passed", "expected_tracks": 12})
    return folder


def fake_release(release_id, disc_id, count):
    assert release_id == RELEASE
    assert disc_id == DISC
    assert count == 12
    return {
        "release_title": "Freak of Nature", "album_artist": "Anastacia",
        "date": "2001-11-26", "barcode": "5099750475720",
        "label_info": [{"name": "Epic", "catalog_number": "504757 2"}],
        "total_media": 1,
        "all_media_summary": [{
            "position": 1, "track_count": 12, "disc_id_attached": False
        }]
    }


def test_correct_physical_edition_without_disc_id_is_review_not_approved(staged):
    result = physical_release.compare(
        JOB, RELEASE, catalog_number="504757 2",
        barcode="5099750475720", lookup=fake_release
    )
    assert result["status"] == "review_required"
    assert result["physical_evidence"]["catalog_number_matches"] is True
    assert result["physical_evidence"]["disc_id_attached_to_matching_medium"] is False
    assert result["physical_evidence"]["track_count_present_on_release"] is True
    assert not result["tagging_eligible"]
    assert not result["physical_edition_approved"]
    assert [x["code"] for x in result["observations"]] == ["disc_id_not_attached"]


def test_wrong_catalog_is_flagged_even_if_disc_id_matches(staged):
    def linked(*args):
        value = fake_release(*args)
        value["all_media_summary"][0]["disc_id_attached"] = True
        return value
    result = physical_release.compare(
        JOB, RELEASE, catalog_number="EPC 513365 9", lookup=linked)
    assert result["status"] == "review_required"
    assert result["physical_evidence"]["disc_id_attached_to_matching_medium"]
    assert not result["physical_evidence"]["catalog_number_matches"]
    assert not result["physical_edition_approved"]
    assert "catalog_number_differs" in [x["code"] for x in result["observations"]]


def test_catalog_formatting_ignored_but_digits_respected(staged):
    result = physical_release.compare(
        JOB, RELEASE, catalog_number="504757-2", lookup=fake_release)
    assert result["physical_evidence"]["catalog_number_matches"]


def test_invalid_barcode_or_release_id_rejected(staged):
    with pytest.raises(physical_release.PhysicalReleaseError, match="Barcode"):
        physical_release.compare(JOB, RELEASE, catalog_number="504757 2",
                                 barcode="not a barcode", lookup=fake_release)
    with pytest.raises(physical_release.PhysicalReleaseError, match="release UUID"):
        physical_release.compare(JOB, "not-a-uuid", catalog_number="504757 2",
                                 lookup=fake_release)


def test_verification_required_before_comparison(staged, monkeypatch):
    monkeypatch.setattr(physical_release.verification, "report",
                        lambda job: {"status": "review_required", "expected_tracks": 12})
    with pytest.raises(physical_release.PhysicalReleaseError, match="Verify"):
        physical_release.compare(JOB, RELEASE, catalog_number="504757 2",
                                 lookup=fake_release)


def test_physical_comparison_ui_present():
    html = TestClient(app).get("/").text
    assert "Physical release comparison (read-only)" in html
    assert "physical-compare-btn" in html
    assert "physical-catalog" in html


def test_disc_candidate_gate_single_candidate_is_read_only_automatic_inspection():
    from oscar.musicbrainz import assess_disc_candidates
    candidates = {"disc_id": DISC, "releases": [
        {"id": RELEASE, "labels": [{"catalog_number": "504757 2"}]}
    ]}
    result = assess_disc_candidates(candidates)
    gate = result["edition_gate"]
    assert gate["status"] == "single_candidate"
    assert gate["can_inspect_automatically"]
    assert not gate["catalog_prompt_recommended"]
    assert not gate["physical_edition_approved"]
    assert result["releases"][0]["printed_catalog_matches"] is None


def test_disc_candidate_gate_ambiguity_prompts_for_catalog():
    from oscar.musicbrainz import assess_disc_candidates
    candidates = {"releases": [
        {"id": RELEASE, "labels": [{"catalog_number": "ES 99220"}]},
        {"id": "09fe4a40-7d2b-400e-b3de-b148f55fbcad",
         "labels": [{"catalog_number": "E 8512"}]},
    ]}
    result = assess_disc_candidates(candidates)
    assert result["edition_gate"]["status"] == "ambiguous_disc_id"
    assert result["edition_gate"]["catalog_prompt_recommended"]
    result = assess_disc_candidates(candidates, "E-8512")
    assert result["edition_gate"]["status"] == "catalog_candidate"
    assert result["edition_gate"]["catalog_match_count"] == 1
    assert not result["releases"][0]["printed_catalog_matches"]
    assert result["releases"][1]["printed_catalog_matches"]


def test_disc_candidate_gate_missing_unlinked_edition_is_not_approved():
    from oscar.musicbrainz import assess_disc_candidates
    candidates = {"releases": [
        {"id": RELEASE, "labels": [{"catalog_number": "ES 99220"}]}
    ]}
    result = assess_disc_candidates(candidates, "E 8512")
    assert result["edition_gate"]["status"] == "catalog_conflict"
    assert result["edition_gate"]["catalog_prompt_recommended"]
    assert not result["edition_gate"]["can_inspect_automatically"]
    assert not result["edition_gate"]["physical_edition_approved"]


def test_disc_candidate_gate_no_results_and_invalid_catalog():
    from oscar.musicbrainz import MusicBrainzError, assess_disc_candidates
    result = assess_disc_candidates({"releases": []})
    assert result["edition_gate"]["status"] == "no_disc_candidates"
    with pytest.raises(MusicBrainzError, match="catalog"):
        assess_disc_candidates({"releases": []}, " - / ")


def test_disc_candidate_gate_does_not_mutate_provider_response():
    from oscar.musicbrainz import assess_disc_candidates
    original = {"releases": [{"id": RELEASE, "labels": [{"catalog_number": "504757 2"}]}]}
    result = assess_disc_candidates(original, "504757-2")
    assert result["edition_gate"]["status"] == "catalog_candidate"
    assert "printed_catalog_matches" not in original["releases"][0]


def test_disc_candidate_gate_ui_present():
    html = TestClient(app).get("/").text
    assert "Compare printed catalog number" in html
    assert "single_candidate" in html
    assert "Search MusicBrainz independently by catalog number" in html
