"""Read-only AccurateRip lookup for a validated trailing-data CD-Extra TOC."""
import hashlib
import struct
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_RESPONSE = 1_000_000


def identifiers(disc_toc):
    """Use the CUETools full-disc AR identifiers, with the audio track count."""
    offsets = list(map(int, disc_toc.split(":")))
    starts, data, end = offsets[:-2], -offsets[-2], offsets[-1]
    count = len(starts)
    digit_sum = sum(sum(map(int, str(start // 75 + 2))) for start in (*starts, data))
    cddb = ((digit_sum % 255) << 24) | ((end // 75 - starts[0] // 75) << 8) | (count + 1)
    first = (sum(starts) + end) & 0xFFFFFFFF
    second = (sum((i + 1) * max(start, 1) for i, start in enumerate(starts))
              + (count + 1) * end) & 0xFFFFFFFF
    return count, first, second, cddb


def lookup(disc_toc, calculated, *, opener=None):
    count, first, second, cddb = ids = identifiers(disc_toc)
    first_hex = f"{first:08x}"
    url = ("https://www.accuraterip.com/accuraterip/" + "/".join(first_hex[-1:-4:-1])
           + f"/dBAR-{count:03d}-{first_hex}-{second:08x}-{cddb:08x}.bin")
    detail = {"disc_toc": disc_toc, "url": url, "status": "lookup_failed"}
    try:
        request = Request(url, headers={"User-Agent": "OSCAR CD-Extra verification"})
        with (opener or urlopen)(request, timeout=12) as response:
            raw = response.read(MAX_RESPONSE + 1)
    except HTTPError as exc:
        if exc.code == 404:
            detail["status"] = "not_found"
        return detail, {}
    except (OSError, URLError):
        return detail, {}
    length = 13 + 9 * count
    if not raw or len(raw) > MAX_RESPONSE or len(raw) % length:
        return detail, {}
    matches = {number: {} for number in range(1, count + 1)}
    for offset in range(0, len(raw), length):
        if struct.unpack_from("<BIII", raw, offset) != ids:
            return detail, {}
        for number in matches:
            confidence, crc, _ = struct.unpack_from("<BII", raw, offset + 13 + 9 * (number - 1))
            reference = f"{crc:08X}"
            for version, value in calculated[number].items():
                if confidence and value == reference:
                    record = matches[number].setdefault(version, {
                        "crc": value, "status": "accurately_ripped", "confidence": 0,
                    })
                    record["confidence"] += confidence
    detail["status"] = "found"
    detail["response_sha256"] = hashlib.sha256(raw).hexdigest()
    detail["matched_tracks"] = sum(bool(versions) for versions in matches.values())
    return detail, matches
