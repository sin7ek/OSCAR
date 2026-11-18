"""Explicit MusicBrainz work hierarchy, kept separate from display-title heuristics.

Only an explicit work-to-work 'parts' relationship supports a parent grouping.
No parsing of punctuation, opus numbers or roman numerals into inferred works.
"""
from collections import defaultdict


def parent_works(work: dict) -> list[dict]:
    """Get parent works from relations on the *child* work."""
    result = []
    for rel in work.get("relations") or []:
        if not isinstance(rel, dict) or rel.get("target-type") != "work":
            continue
        relationship = rel.get("type")
        direction = rel.get("direction")
        # MusicBrainz 'parts' relation is child -> parent when backward.
        if not (relationship == "parts" and direction == "backward"):
            continue
        target = rel.get("work") or {}
        if not isinstance(target, dict) or not target.get("id"):
            continue
        parent = {
            "id": target["id"],
            "title": target.get("title"),
            "source": "musicbrainz_work_relation",
        }
        if parent not in result:
            result.append(parent)
    return result


def work_details(recording: dict) -> list[dict]:
    """Preserve exactly linked work plus verified parent links."""
    works = []
    for rel in recording.get("relations") or []:
        if not isinstance(rel, dict) or rel.get("target-type") != "work":
            continue
        if rel.get("type") not in {"performance", "recording of"}:
            continue
        child = rel.get("work") or {}
        if not isinstance(child, dict) or not child.get("id"):
            continue
        obj = {
            "id": child["id"],
            "title": child.get("title"),
            "relationship": rel.get("type"),
            "parents": parent_works(child),
        }
        if obj not in works:
            works.append(obj)
    return works


def group_tracks(tracks: list[dict]) -> list[dict]:
    """Group contiguous tracks sharing an explicitly linked parent work MBID.

    A multi-work recording, missing relationship, or discontinuous group stays
    separate to avoid silently merging independent compositions.
    """
    sections: list[dict] = []
    for track in tracks:
        works = track.get("work_details") or []
        key = None
        title = None
        if len(works) == 1 and len(works[0].get("parents") or []) == 1:
            parent = works[0]["parents"][0]
            key = parent["id"]
            title = parent.get("title")
        if key and sections and sections[-1]["parent_work_id"] == key:
            sections[-1]["tracks"].append(track["number"])
            sections[-1]["track_titles"].append(track.get("title"))
            continue
        sections.append({
            "parent_work_id": key,
            "parent_work_title": title,
            "source": "musicbrainz_work_relation" if key else "ungrouped",
            "tracks": [track["number"]],
            "track_titles": [track.get("title")],
        })
    return sections
