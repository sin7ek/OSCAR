"""Read-only physical-release evidence comparison for existing verified staging jobs.

A matching Disc ID alone cannot prove that a release matches the physical
packaging. This module never writes to MusicBrainz, FLACs or archive targets.
"""
import json
import re

from oscar import verification
from oscar.boxsets import RELEASE_ID, lookup_release_medium


class PhysicalReleaseError(RuntimeError):
    pass


def _normalized_catalog(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def compare(job_id, release_id, *, catalog_number, barcode=None, lookup=lookup_release_medium):
    if not RELEASE_ID.fullmatch(release_id):
        raise PhysicalReleaseError("Enter a valid MusicBrainz release UUID, not a release-group ID")
    catalog_number = str(catalog_number or "").strip()
    if not 1 <= len(catalog_number) <= 100:
        raise PhysicalReleaseError("Enter the catalog number printed on the physical CD")
    if barcode is not None and (not isinstance(barcode, str) or not re.fullmatch(r"[0-9]{8,14}", barcode)):
        raise PhysicalReleaseError("Barcode must contain 8–14 digits when provided")
    root = verification._safe_job(job_id)
    statefile = root / "state.json"
    if statefile.is_symlink() or not statefile.is_file():
        raise PhysicalReleaseError("Rip evidence missing or unsafe")
    state = json.loads(statefile.read_text(encoding="utf-8"))
    if state.get("id") != job_id or state.get("status") != "needs_verification" or state.get("returncode") != 0:
        raise PhysicalReleaseError("The source rip must have completed successfully")
    report = verification.report(job_id)
    if report.get("status") != "checks_passed":
        raise PhysicalReleaseError("Verify the staging rip successfully before comparing releases")
    disc_id = state.get("disc_id")
    count = report.get("expected_tracks")
    if not isinstance(disc_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{28}", disc_id):
        raise PhysicalReleaseError("Missing valid saved MusicBrainz Disc ID")
    if not isinstance(count, int) or not 1 <= count <= 99:
        raise PhysicalReleaseError("Missing verified track count")
    info = lookup(release_id, disc_id, count)
    labels = info.get("label_info") or []
    catalog_matches = [x for x in labels
                       if _normalized_catalog(x.get("catalog_number")) == _normalized_catalog(catalog_number)]
    actual_barcode = re.sub(r"[^0-9]", "", str(info.get("barcode") or ""))
    barcode_status = ("not_entered" if not barcode else
                      "matches" if barcode == actual_barcode else "differs")
    media = info.get("all_media_summary") or []
    exact = [m for m in media if m.get("disc_id_attached") and m.get("track_count") == count]
    same_count = [m for m in media if m.get("track_count") == count]
    observations = []
    if not catalog_matches:
        observations.append({"code": "catalog_number_differs",
                             "message": "The printed catalog number is not listed on this MusicBrainz release. Do not select this edition without further evidence."})
    if barcode_status == "differs":
        observations.append({"code": "barcode_differs",
                             "message": "The printed barcode does not match this MusicBrainz release."})
    if not exact:
        observations.append({"code": "disc_id_not_attached",
                             "message": "This Disc ID is not attached to a matching medium on the selected release. The release cannot yet be used by OSCAR's exact-match tagging workflow."})
    if not same_count:
        observations.append({"code": "track_count_differs",
                             "message": "No medium on this release has the verified track count."})
    return {
        "status": "evidence_consistent_review_required" if not observations else "review_required",
        "job_id": job_id, "release_id": release_id, "disc_id": disc_id,
        "verified_tracks": count,
        "release": {"title": info.get("release_title"), "artist": info.get("album_artist"),
                    "date": info.get("date"), "barcode": info.get("barcode"),
                    "labels": labels, "total_media": info.get("total_media")},
        "physical_evidence": {
            "catalog_number_entered": catalog_number,
            "catalog_number_matches": bool(catalog_matches),
            "barcode_entered": barcode,
            "barcode_status": barcode_status,
            "disc_id_attached_to_matching_medium": bool(exact),
            "track_count_present_on_release": bool(same_count),
        },
        "media": media,
        "observations": observations,
        "tagging_eligible": bool(exact),
        "physical_edition_approved": False,
        "notes": [
            "This read-only comparison cannot authenticate the physical pressing, and matching catalog/barcode is not automatic approval.",
            "A Disc ID may match multiple editions. Never assume that the first MusicBrainz candidate is the correct physical release.",
            "If the intended release is not in MusicBrainz or lacks this Disc ID, review and correct MusicBrainz externally; OSCAR will not invent an edition or attach an ID.",
            "Nothing is tagged, moved, renamed, archived or deleted.",
        ],
    }
