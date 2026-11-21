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
