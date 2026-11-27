"""Locate retained revision generations inside or outside the media library."""
import os
import errno
from pathlib import Path
import re

LEGACY = ".oscar-archive-versions"


def root(archive):
    configured = os.environ.get("OSCAR_ARCHIVE_HISTORY_ROOT")
    if not configured:
        return archive / LEGACY
    path = Path(configured)
    if (not path.is_absolute() or path == Path("/") or path.resolve() != path
            or path.is_relative_to(archive) or archive.is_relative_to(path)):
        raise ValueError("Archive history must be a dedicated path outside the live archive")
    if not path.parent.is_dir() or (path.exists() and not path.is_dir()):
        raise ValueError("Archive history needs an existing parent directory")
    return path


def retained(archive, publication, leaf, *, recorded=None):
    if not re.fullmatch(r"[a-f0-9]{32}", publication) or not re.fullmatch(
            r"[a-f0-9]{32}(?:-disc-\d{2})?", leaf):
        raise ValueError("Invalid archive history identity")
    legacy = archive / LEGACY / publication / leaf
    external = root(archive) / publication / leaf
    chosen = external
    if recorded is not None:
        recorded = Path(recorded)
        if recorded not in {external, legacy}:
            raise ValueError("History journal path is outside configured storage")
        if recorded == legacy and (legacy.exists() or not external.exists()):
            chosen = legacy
        if legacy != external and legacy.exists() and external.exists():
            raise ValueError("History generation exists in both locations")
    if chosen.resolve() != chosen:
        raise ValueError("Symbolic links in archive history path")
    return chosen


def move(archive, source, destination):
    """Promote via the shared-parent view when Archive is also a bind mount."""
    from oscar.archive_publish import _rename_noreplace

    alias_value = os.environ.get("OSCAR_ARCHIVE_HISTORY_SHARED_ARCHIVE")
    if alias_value and root(archive) != archive / LEGACY:
        alias = Path(alias_value)
        if (not alias.is_absolute() or alias.resolve() != alias or
                not alias.is_dir() or not alias.samefile(archive)):
            raise ValueError("Shared archive path must refer to the same live Archive directory")
        source = alias / source.relative_to(archive) if source.is_relative_to(archive) else source
        destination = alias / destination.relative_to(archive) if destination.is_relative_to(archive) else destination
    try:
        _rename_noreplace(source, destination)
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            raise ValueError("Archive and history need a shared parent mount for atomic moves") from exc
        raise
