"""Preview-only archive naming; never create/move/rename files.

Names identify *physical releases*. Work/catalogue identifiers such as HWV and
op. numbers belong to composition metadata, not the release-catalogue prefix.
"""
import re
import unicodedata
from pathlib import PurePosixPath

PROFILES = ("album", "compilation", "classical")
_RESERVED = {".", "..", ""}
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


def safe_component(value, *, fallback="Unknown", max_length=120):
    """Normalize filesystem components without allowing path traversal."""
    text = unicodedata.normalize("NFC", str(value or ""))
    text = _WHITESPACE.sub(" ", _INVALID.sub(" ", text)).strip(" .")
    if text in _RESERVED:
        return fallback
    return text[:max_length].rstrip(" .") or fallback


def catalog_prefix(catalog_number):
    """No placeholder: omit bracketed catalog number when undocumented."""
    if not catalog_number:
        return ""
    item = safe_component(catalog_number, fallback="")
    return f"[{item}] " if item else ""


def archive_preview(*, profile, album_title, release_year=None,
                    catalog_number=None, album_artist=None, composers=None,
                    disc_number=1, track_number=1, track_title="Untitled",
                    track_artist=None, multi_disc=False):
    """Return a relative path preview only; no filesystem operations."""
    if profile not in PROFILES:
        raise ValueError("Unsupported naming profile")
    if not (1 <= disc_number <= 99 and 1 <= track_number <= 99):
        raise ValueError("Invalid disc/track number")
    composers = [safe_component(c) for c in (composers or []) if c]
    album = safe_component(album_title)
    year = str(release_year or "")
    if year and not re.fullmatch(r"\d{4}", year):
        raise ValueError("Release year must be four digits")
    edition = f"{catalog_prefix(catalog_number)}{album}" + (f" ({year})" if year else "")
    if profile == "classical":
        # Composer is never inferred from album artist or artist credit.
        composer_dir = composers[0] if len(set(composers)) == 1 else "Various Composers"
        parts = ("Classical", composer_dir, edition)
    elif profile == "compilation":
        parts = ("Various Artists", edition)
    else:
        parts = (safe_component(album_artist, fallback="Unknown Album Artist"), edition)
    index = f"{disc_number:02d}-{track_number:02d}"
    title = safe_component(track_title)
    if profile == "compilation" and track_artist:
        filename = f"{index} - {safe_component(track_artist)} - {title}.flac"
    else:
        filename = f"{index} - {title}.flac"
    relative = PurePosixPath(*parts, filename)
    return {"profile": profile, "directory": str(PurePosixPath(*parts)),
            "track_path": str(relative), "requires_release_review": True,
            "note": "Preview only: release-year, catalog number and composer must be verified; files are untouched."}
