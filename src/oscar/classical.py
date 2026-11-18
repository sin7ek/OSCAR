"""Interpret explicit MusicBrainz recording/work relationships for classical music.

Track/recording artist credit is not a performer or composer role.
Roles are only emitted when backed by relationship data; missing means unknown.
"""

_PERFORMER_TYPES = {
    "performer", "instrument", "vocal", "conductor", "performing orchestra",
    "orchestra", "choir", "chorus master", "concertmaster", "solo", "voice actor",
}
_COMPOSER_TYPES = {"composer", "additional composer"}
_WORK_TYPES = {"performance", "recording of"}
_WORK_HIERARCHY = {"parts", "part of"}


def _add(roles: list[dict], rel: dict):
    artist = rel.get("artist") or {}
    name = artist.get("name")
    if not name:
        return
    attributes = rel.get("attributes") or []
    role = str(rel.get("type") or "")
    item = {
        "name": name, "artist_id": artist.get("id"),
        "role": role, "attributes": attributes if isinstance(attributes, list) else [],
    }
    if item not in roles:
        roles.append(item)


def recording_roles(recording: dict) -> dict:
    """Extract performers and credited musical works, without guessing roles."""
    performers: list[dict] = []
    composers: list[dict] = []
    works: list[dict] = []
    for relation in recording.get("relations") or []:
        if not isinstance(relation, dict):
            continue
        role = relation.get("type")
        if relation.get("target-type") == "artist" and role in _PERFORMER_TYPES:
            _add(performers, relation)
        if relation.get("target-type") != "work" or role not in _WORK_TYPES:
            continue
        work = relation.get("work") or {}
        if not isinstance(work, dict) or not work.get("id"):
            continue
        item = {"id": work["id"], "title": work.get("title"), "relationship": role}
        if item not in works:
            works.append(item)
        for work_relation in work.get("relations") or []:
            if isinstance(work_relation, dict) and (
                work_relation.get("target-type") == "artist"
                and work_relation.get("type") in _COMPOSER_TYPES
            ):
                _add(composers, work_relation)
    return {
        "performers": performers,
        "composers": composers,
        "works": works,
        "performer_relationships_present": bool(performers),
        "composer_relationships_present": bool(composers),
    }
