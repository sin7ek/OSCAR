"""Capture and preserve a trailing Mode 1 CD-Extra data track."""
import ctypes
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

SECTOR_SIZE = 2352
ARCHIVE_FILENAME = "CD-Extra/data-track.bin"
CHECKSUM_FILENAME = "CD-Extra/data-track.sha256"


class DataError(ValueError):
    pass


def geometry(root):
    """Identify the exact trailing data track from the saved CUE and rip log."""
    from oscar import ctdb_verification, verification

    audio = root / "audio"
    if audio.is_symlink() or not audio.is_dir():
        raise DataError("Unsafe audio folder")
    cues = list(audio.glob("*.cue"))
    if len(cues) != 1:
        return None
    cue = verification._file_readonly(root, "audio/" + cues[0].name)
    original = cue.read_text(encoding="utf-8-sig")
    extra = ctdb_verification._CD_EXTRA_SUFFIX.search(original)
    if not extra:
        return None
    plan = json.loads(verification._file_readonly(root, "plan.json").read_text())
    count = plan["track_count"]
    if int(extra[1]) != int(extra[2]) or int(extra[2]) != count + 1:
        raise DataError("Unexpected CD-Extra track number")
    refs = verification._cue_refs(original[:extra.start()])
    offsets, leadout = ctdb_verification._check_audio_session(
        root, refs, original[:extra.start()], plan["toc_string"])
    toc = ctdb_verification._cd_extra_toc(root, count, offsets, leadout)
    start, end = toc.split(":")[-2:]
    start, end = -int(start), int(end)
    name = re.search(r'^FILE "([^"]+)" BINARY', extra[0], re.M | re.I)[1]
    return {"track": count + 1, "source": "audio/" + name, "format": "MODE1/2352",
            "start_lsn": start, "sectors": end - start, "size": (end - start) * SECTOR_SIZE,
            "disc_toc": toc}


def _reader(device, layout):
    """Read raw main-channel Mode 1 sectors via libcdio's MMC interface."""
    libname = ctypes.util.find_library("cdio")
    if not libname:
        raise DataError("libcdio unavailable for CD-Extra data extraction")
    lib = ctypes.CDLL(libname)
    lib.cdio_open.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.cdio_open.restype = ctypes.c_void_p
    lib.cdio_destroy.argtypes = [ctypes.c_void_p]
    lib.cdio_get_track_lsn.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
    lib.cdio_get_track_lsn.restype = ctypes.c_int32
    lib.cdio_get_track_last_lsn.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
    lib.cdio_get_track_last_lsn.restype = ctypes.c_int32
    lib.mmc_read_cd.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32, ctypes.c_int,
        ctypes.c_bool, ctypes.c_bool, ctypes.c_uint8, ctypes.c_bool, ctypes.c_bool,
        ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint32]
    lib.mmc_read_cd.restype = ctypes.c_int
    handle = lib.cdio_open(os.fsencode(device), 0)
    if not handle:
        raise DataError("Could not open drive for data extraction")
    try:
        if (lib.cdio_get_track_lsn(handle, layout["track"]) != layout["start_lsn"]
                or lib.cdio_get_track_last_lsn(handle, layout["track"]) !=
                layout["start_lsn"] + layout["sectors"] - 1):
            raise DataError("Inserted data track differs from the saved geometry")
        for lsn in range(layout["start_lsn"], layout["start_lsn"] + layout["sectors"], 16):
            count = min(16, layout["start_lsn"] + layout["sectors"] - lsn)
            buffer = ctypes.create_string_buffer(count * SECTOR_SIZE)
            for attempt in range(3):
                if lib.mmc_read_cd(handle, buffer, lsn, 2, False, True, 1, True, True,
                                   0, 0, SECTOR_SIZE, count) == 0:
                    break
            else:
                raise DataError(f"Data sector read failed at LSN {lsn}")
            yield buffer.raw
    finally:
        lib.cdio_destroy(handle)


def _validated_chunks(reader, device, layout, cancelled):
    cursor = layout["start_lsn"]
    for block in reader(device, layout):
        if cancelled():
            raise DataError("Data extraction stopped by operator")
        if not block or len(block) % SECTOR_SIZE:
            raise DataError("Invalid raw data-sector length")
        for offset in range(0, len(block), SECTOR_SIZE):
            sector = block[offset:offset + SECTOR_SIZE]
            minute, frame = divmod(cursor + 150, 60 * 75)
            second, frame = divmod(frame, 75)
            bcd = bytes((value // 10 * 16 + value % 10 for value in (minute, second, frame)))
            if sector[:16] != b"\x00" + b"\xff" * 10 + b"\x00" + bcd + b"\x01":
                raise DataError(f"Invalid Mode 1 sector header at LSN {cursor}")
            cursor += 1
        if cursor > layout["start_lsn"] + layout["sectors"]:
            raise DataError("Unexpected data beyond the saved track")
        yield block
    if cursor != layout["start_lsn"] + layout["sectors"]:
        raise DataError("Incomplete data track")


def capture(root, device, *, reader=_reader, cancelled=lambda: False):
    """Read twice, compare SHA-256, record the result before releasing the drive."""
    from oscar import toc

    layout = geometry(root)
    if not layout:
        return None
    plan = json.loads((root / "plan.json").read_text())
    if toc.read_toc(device)["toc_string"] != plan["toc_string"]:
        raise DataError("Inserted audio TOC differs from the saved rip")
    target = root / layout["source"]
    partial = target.with_suffix(".bin.partial")
    digest = hashlib.sha256()
    with partial.open("xb") as output:
        for block in _validated_chunks(reader, device, layout, cancelled):
            output.write(block)
            digest.update(block)
        output.flush()
        os.fsync(output.fileno())
    second = hashlib.sha256()
    for block in _validated_chunks(reader, device, layout, cancelled):
        second.update(block)
    if second.digest() != digest.digest() or toc.read_toc(device)["toc_string"] != plan["toc_string"]:
        raise DataError("Data reads differ or inserted disc changed; partial image retained")
    # The ripping job owns this directory exclusively; refuse existing images.
    if target.exists() or target.is_symlink():
        raise DataError("Data image already exists; preserving both files")
    os.rename(partial, target)
    return {**layout, "sha256": digest.hexdigest(), "verification": "two_matching_raw_reads"}


def review(root, track, include):
    """Bind archive choice to original extraction evidence and exact payload."""
    from oscar import verification

    if not include:
        return {"track": track, "status": "excluded_by_operator"}
    try:
        layout = geometry(root)
        if not layout or layout["track"] != track:
            raise DataError("Data track geometry is unavailable")
        state = json.loads(verification._file_readonly(root, "state.json").read_text())
        record = state.get("cd_extra_data")
        if not isinstance(record, dict) or record.get("verification") != "two_matching_raw_reads":
            raise DataError(state.get("cd_extra_data_error") or
                            "Verified data image unavailable; reinsert the CD and rip again")
        if any(record.get(key) != value for key, value in layout.items()):
            raise DataError("Saved data geometry differs from extraction evidence")
        source = verification._file_readonly(root, layout["source"])
        if source.stat().st_size != layout["size"] or verification._digest(source) != record.get("sha256"):
            raise DataError("Data image differs from its extraction SHA-256")
        return {**record, "filename": ARCHIVE_FILENAME, "status": "included"}
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        return {"track": track, "status": "unavailable", "message": str(exc)[:250]}


def copy_to_archive(root, temp, record):
    from oscar import verification

    source = verification._file_readonly(root, record["source"])
    target = temp / ARCHIVE_FILENAME
    target.parent.mkdir()
    with source.open("rb") as inp, target.open("xb") as out:
        shutil.copyfileobj(inp, out, 1024 * 1024)
        out.flush()
        os.fsync(out.fileno())
    if target.stat().st_size != record["size"] or verification._digest(target) != record["sha256"]:
        raise DataError("Archive data image differs from reviewed extraction")
    with (temp / CHECKSUM_FILENAME).open("x", encoding="ascii") as out:
        out.write(checksum_line(record))
        out.flush()
        os.fsync(out.fileno())


def checksum_line(record):
    return record["sha256"] + "  data-track.bin\n"


def check_archive(folder, manifest):
    """Validate archived binary and its checksum file without mounting the disc."""
    from oscar import verification

    record = (manifest.get("provenance") or {}).get("cd_extra_data")
    if not record:
        return
    if record.get("status") == "excluded_by_operator":
        return
    if record.get("status") != "included":
        raise DataError("Invalid archived CD-Extra data status")
    if (record.get("format") != "MODE1/2352" or type(record.get("sectors")) is not int
            or record["sectors"] <= 0 or record.get("size") != record["sectors"] * SECTOR_SIZE
            or record.get("verification") != "two_matching_raw_reads"
            or not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", "")))):
        raise DataError("Invalid archived CD-Extra data evidence")
    target = folder / ARCHIVE_FILENAME
    checksum = folder / CHECKSUM_FILENAME
    if (record.get("filename") != ARCHIVE_FILENAME or target.parent.is_symlink()
            or target.is_symlink() or checksum.is_symlink()
            or not target.is_file() or not checksum.is_file()
            or target.stat().st_size != record.get("size")
            or verification._digest(target) != record.get("sha256")
            or checksum.stat().st_size != len(checksum_line(record))
            or checksum.read_text(encoding="ascii") != checksum_line(record)):
        raise DataError("Archived CD-Extra data or checksum failed integrity verification")


def extract_payload(folder, destination):
    """Export 2048-byte Mode 1 sector payloads from a verified archive."""
    manifest_path = folder / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise DataError("Missing archive manifest")
    manifest = json.loads(manifest_path.read_text())
    record = manifest.get("provenance", {}).get("cd_extra_data", {})
    if record.get("status") != "included":
        raise DataError("Archive has no verified CD-Extra image")
    check_archive(folder, manifest)
    if destination.resolve().is_relative_to(folder.resolve()):
        raise DataError("Choose an output outside the archive")
    digest = hashlib.sha256()
    with (folder / ARCHIVE_FILENAME).open("rb") as source, destination.open("xb") as out:
        for _ in range(record["sectors"]):
            sector = source.read(SECTOR_SIZE)
            if len(sector) != SECTOR_SIZE:
                raise DataError("Incomplete data sector")
            digest.update(sector)
            out.write(sector[16:2064])
        if source.read(1) or digest.hexdigest() != record["sha256"]:
            raise DataError("Data changed during export; output is incomplete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Export the Mode 1 payload of an archived CD-Extra data track")
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    extract_payload(args.archive, args.output)
