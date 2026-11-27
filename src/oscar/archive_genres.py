"""Conservative genre vocabulary for local Collection discovery only.

Never derive genres from artist, composer or album title. MusicBrainz genre
suggestions are not automatically approved. No archive/FLAC tag mutation.
"""
from __future__ import annotations

import re

# A deliberately small editorial vocabulary; expand through reviewed changes.
_CANONICAL = {
    "classical": "Classical", "classical music": "Classical",
    "baroque": "Baroque", "romantic": "Romantic",
    "romantic era": "Romantic", "modern classical": "Modern Classical",
    "contemporary classical": "Contemporary Classical",
    "electronic": "Electronic", "electronic music": "Electronic",
    "hardcore": "Hardcore", "gabber": "Gabber", "techno": "Techno",
    "house": "House", "trance": "Trance", "drum and bass": "Drum and Bass",
    "ambient": "Ambient",
    "pop": "Pop", "pop music": "Pop",
    "rock": "Rock", "alternative rock": "Alternative Rock",
    "punk rock": "Punk Rock", "metal": "Metal",
    "jazz": "Jazz", "blues": "Blues", "folk": "Folk",
    "hip hop": "Hip-Hop", "hip-hop": "Hip-Hop",
    "reggae": "Reggae", "soul": "Soul", "funk": "Funk",
    "country": "Country", "soundtrack": "Soundtrack",
}
_CLASSICAL = frozenset({"Classical", "Baroque", "Romantic", "Modern Classical",
                       "Contemporary Classical"})
_PREFERRED = (
    "Classical", "Baroque", "Romantic", "Modern Classical", "Contemporary Classical",
    "Electronic", "Hardcore", "Gabber", "Techno", "House", "Trance", "Drum and Bass",
    "Ambient", "Pop", "Rock", "Alternative Rock", "Punk Rock", "Metal", "Jazz",
    "Blues", "Folk", "Hip-Hop", "Reggae", "Soul", "Funk", "Country", "Soundtrack",
)


def classify(raw_genres, *, profile=None):
    """Return normalized searchable genres + logical section from explicit evidence.

    Only recognizes approved-style literal names already present in FLAC tags.
    A classical processing profile licenses the broad Classical grouping, NOT
    a historical period such as Baroque or Romantic.
    """
    recognized = set()
    for raw in raw_genres:
        if not isinstance(raw, str):
            continue
        for token in re.split(r";|\s*/\s*", raw)[:16]:
            name = _CANONICAL.get(token.casefold().strip())
            if name:
                recognized.add(name)
    if profile == "classical" or recognized.intersection(_CLASSICAL):
        section = "Classical"
        recognized.add("Classical")
    elif recognized:
        section = "Popular"
    else:
        section = "Unclassified"
    values = [name for name in _PREFERRED if name in recognized][:8]
    return {"genres": "; ".join(values), "library_section": section}


def normalize_genres(values):
    """Curated independent Vorbis GENRE values, never combined with semicolons.

    Reject unsupported/freetext styles rather than write them into FLAC.
    The section parent Classical is explicitly included for Baroque/Romantic.
    """
    if not isinstance(values, list) or len(values) > 40:
        raise ValueError("Invalid genre list")
    result = classify(values)["genres"]
    return result.split("; ") if result else []


def musicbrainz_genres(payload):
    """Normalize only official MusicBrainz genres with positive vote counts.

    Never use unrestricted 'tags', artists or work-level tags as release genres.
    """
    if not isinstance(payload, dict):
        return []
    options = payload.get("genres") or []
    if not isinstance(options, list):
        return []
    return normalize_genres([
        item["name"] for item in options[:80]
        if isinstance(item, dict) and isinstance(item.get("name"), str)
        and type(item.get("count")) is int and item["count"] > 0
    ][:40])
