"""Read-only audio-CD TOC via MetaBrainz libdiscid.

A standard TOC exposes INDEX 01 track starts and lead-out. It does NOT
establish INDEX 00, pregap audio, HTOA, secure-read quality or drive offset.
"""
import ctypes
import ctypes.util
import re


class TocError(RuntimeError):
    pass


def _load_libdiscid():
    library = ctypes.util.find_library("discid")
    if not library:
        raise TocError("libdiscid is not installed in the OSCAR container")
    lib = ctypes.CDLL(library)
    lib.discid_new.restype = ctypes.c_void_p
    lib.discid_free.argtypes = (ctypes.c_void_p,)
    lib.discid_read_sparse.argtypes = (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint)
    lib.discid_read_sparse.restype = ctypes.c_int
    lib.discid_get_error_msg.argtypes = (ctypes.c_void_p,)
    lib.discid_get_error_msg.restype = ctypes.c_char_p
    for name in ("discid_get_id", "discid_get_toc_string"):
        func = getattr(lib, name)
        func.argtypes = (ctypes.c_void_p,)
        func.restype = ctypes.c_char_p
    for name in ("discid_get_first_track_num", "discid_get_last_track_num",
                 "discid_get_sectors"):
        func = getattr(lib, name)
        func.argtypes = (ctypes.c_void_p,)
        func.restype = ctypes.c_int
    for name in ("discid_get_track_offset", "discid_get_track_length"):
        func = getattr(lib, name)
        func.argtypes = (ctypes.c_void_p, ctypes.c_int)
        func.restype = ctypes.c_int
    return lib


def read_toc(device: str, lib=None) -> dict:
    """Read only the disc's standard TOC, never audio sectors."""
    if not re.fullmatch(r"/dev/sr\d+", device):
        raise TocError("Only enumerated /dev/srN devices are supported")
    lib = lib if lib is not None else _load_libdiscid()
    handle = lib.discid_new()
    if not handle:
        raise TocError("libdiscid failed to allocate a DiscId handle")
    try:
        if lib.discid_read_sparse(handle, device.encode("ascii"), 0) != 1:
            detail = lib.discid_get_error_msg(handle)
            raise TocError((detail or b"Failed reading TOC").decode("utf-8", "replace"))
        first = lib.discid_get_first_track_num(handle)
        last = lib.discid_get_last_track_num(handle)
        leadout = lib.discid_get_sectors(handle)
        if first < 1 or last < first or last > 99 or leadout <= 0:
            raise TocError("Invalid CD TOC returned by libdiscid")
        tracks = []
        for track in range(first, last + 1):
            start = lib.discid_get_track_offset(handle, track)
            length = lib.discid_get_track_length(handle, track)
            if start < 0 or length <= 0:
                raise TocError("Invalid track offset or length")
            tracks.append({
                "number": track,
                "start_sector": start,
                "length_sectors": length,
                "duration_seconds": round(length / 75.0, 3),
            })
        discid = lib.discid_get_id(handle)
        toc_string = lib.discid_get_toc_string(handle)
        if not discid or not toc_string:
            raise TocError("libdiscid returned an empty Disc ID/TOC")
        return {
            "device": device,
            "musicbrainz_disc_id": discid.decode("ascii"),
            "toc_string": toc_string.decode("ascii"),
            "first_track": first,
            "last_track": last,
            "leadout_sector": leadout,
            "tracks": tracks,
            "indices_00_checked": False,
            "pregaps_checked": False,
            "htoa_checked": False,
            "audio_extracted": False,
        }
    finally:
        lib.discid_free(handle)
