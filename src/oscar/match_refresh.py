"""Read-only fresh MusicBrainz matching for previously accepted physical CD jobs.

A newly attached Disc ID is updated external evidence, never a retroactive
upgrade of the persisted operator-accepted provenance or proof of pressing.
"""
import json
import re

from oscar import musicbrainz, verification, workflow_ledger
from oscar.boxsets import lookup_release_medium

_DISC_ID = re.compile(r"[A-Za-z0-9._-]{28}\Z")
_TOC = re.compile(r"[0-9]+(?: [0-9]+){3,101}\Z")


def refresh_accepted_match(job_id: str, *, lookup=None) -> dict:
    """Query the accepted release's current MusicBrainz media without writes.

    No new release is selected, no ledger evidence is rewritten and no archive,
    metadata copy or staged audio is touched.
    """
    if not musicbrainz.lookup_enabled():
        raise ValueError("MusicBrainz lookup is disabled")
    workflow = workflow_ledger.refresh(job_id)
    release_id = workflow.get("accepted_release_id")
    if (workflow.get("identification_mode") != "semi_automatic"
            or not release_id
            or workflow.get("release_match_status") != "INFERRED_OPERATOR_ACCEPTED"):
        raise ValueError("An explicitly accepted Semi Automatic release is required")
    folder = verification._safe_job(job_id)
    planfile = folder / "plan.json"
    if planfile.is_symlink() or not planfile.is_file():
        raise ValueError("Original rip plan is missing or unsafe")
    plan = json.loads(planfile.read_text(encoding="utf-8"))
    state = verification._load_job(folder, job_id)
    report = verification.report(job_id)
    disc_id, toc = plan.get("disc_id"), plan.get("toc_string")
    if not isinstance(disc_id, str) or not _DISC_ID.fullmatch(disc_id):
        raise ValueError("Saved MusicBrainz Disc ID is invalid")
    if (disc_id != state.get("disc_id") or not isinstance(toc, str)
            or len(toc) > 1200 or not _TOC.fullmatch(toc)):
        raise ValueError("Original physical CD evidence is inconsistent")
    entries = [int(v) for v in toc.split()]
    first, last, leadout = entries[:3]
    starts = entries[3:]
    if (first != 1 or not 1 <= last <= 99 or len(starts) != last
            or any(s < 150 or s >= leadout for s in starts)
            or starts != sorted(set(starts))):
        raise ValueError("Saved CD TOC boundaries are invalid")
    tracks = report.get("tracks")
    if (report.get("job_id") != job_id or report.get("status") != "checks_passed"
            or report.get("expected_tracks") != last
            or not isinstance(tracks, list) or len(tracks) != last
            or not all(isinstance(t, dict) and t.get("checks_passed") is True for t in tracks)):
        raise ValueError("Complete verified physical CD staging evidence is required")
    resolver = lookup or lookup_release_medium
    current = resolver(release_id, disc_id, last)
    if current.get("release_id", "").lower() != release_id.lower():
        raise ValueError("MusicBrainz returned a different release")
    matching = [m for m in current.get("matched_media", [])
                if m.get("disc_id_attached") is True
                and m.get("track_count_matches") is True
                and m.get("format") == "CD"]
    if current.get("status") == "exact_disc_id_and_track_count" and len(matching) == 1:
        outcome = "disc_id_now_attached"
    elif current.get("status") == "no_exact_medium_match":
        outcome = "disc_id_not_attached"
    else:
        outcome = "ambiguous_or_incompatible"
    return {
        "job_id": job_id,
        "accepted_release_id": release_id,
        "disc_id": disc_id,
        "track_count": last,
        "lookup_status": outcome,
        "musicbrainz_status": current.get("status"),
        "matched_medium_position": matching[0].get("position") if outcome == "disc_id_now_attached" else None,
        "release_url": "https://musicbrainz.org/release/" + release_id,
        "historical_release_match_status": workflow["release_match_status"],
        "physical_edition_verified": False,
        "persisted_provenance_unchanged": True,
        "warning": ("A fresh MusicBrainz Disc ID association is not proof of an exact "
                    "physical pressing. Historical operator approval remains unchanged; "
                    "no tags, rip files, workflow evidence or archive files were modified."),
    }
