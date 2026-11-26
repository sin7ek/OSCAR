"""Preserve a failed extraction byte-for-byte in a non-playable ZIP.

No source deletion. The caller must explicitly approve any later cleanup and
update provenance references. Intended for trusted local staging paths.
"""
from pathlib import Path
import hashlib
import os
import tempfile
import zipfile


def _digest(stream):
    return hashlib.file_digest(stream, "sha256").hexdigest()


def package(source, destination):
    source, destination = Path(source), Path(destination)
    if (source.is_symlink() or not source.is_file() or
            destination.suffix.lower() != ".zip" or destination.exists()
            or destination.is_symlink() or not destination.parent.is_dir()
            or destination.parent.resolve() != destination.parent.absolute()):
        raise ValueError("Unsafe source or ZIP destination")
    with source.open("rb") as stream:
        expected = _digest(stream)
    fd, name = tempfile.mkstemp(prefix=".evidence-", dir=destination.parent)
    os.close(fd)
    temp = Path(name)
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.write(source, arcname=source.name)
        with zipfile.ZipFile(temp) as archive:
            if archive.namelist() != [source.name] or archive.testzip() is not None:
                raise ValueError("Invalid evidence ZIP")
            with archive.open(source.name) as stream:
                if _digest(stream) != expected:
                    raise ValueError("Evidence SHA-256 mismatch")
        with source.open("rb") as stream:
            if _digest(stream) != expected:
                raise ValueError("Source changed during packaging")
        with temp.open("rb") as stream:
            os.fsync(stream.fileno())
        # Atomic no-overwrite publication, on the same filesystem.
        os.link(temp, destination)
        with destination.open("rb") as stream:
            zipped = _digest(stream)
        return {"filename": destination.name, "member": source.name,
                "original_sha256": expected, "zip_sha256": zipped,
                "source_retained": True}
    finally:
        temp.unlink(missing_ok=True)
