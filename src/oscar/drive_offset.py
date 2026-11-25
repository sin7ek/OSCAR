"""Read-only AccurateRip drive-offset lookup and opt-in disc calibration.

A drive model may appear multiple times with conflicting reported offsets.
In that case, never silently select one. This module never persists settings.
"""
from html.parser import HTMLParser
import re
import subprocess
import threading
import time
from urllib.request import Request, urlopen

URL = "https://www.accuraterip.com/driveoffsets.htm"
_ROW = re.compile(r"^(.+?)\s+([+-]?\d{1,5})\s+(\d+)\s+(\d+(?:\.\d+)?)%\s*$")

_PURGED = re.compile(r"^(.+?)\s+\[Purged\]$", re.I)
_MAX_DATABASE_BYTES = 4 * 1024 * 1024
_CACHE_SECONDS = 3600
_CACHE_LOCK = threading.Lock()
_DATABASE_CACHE = None


class OffsetError(RuntimeError):
    pass


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.cells = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        elif tag in {"td", "th"} and self.cells is not None:
            self.cell = []
        elif tag == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.cells.append("".join(self.cell))
            self.cell = None
        elif tag == "tr" and self.cells is not None:
            self.rows.append(" ".join(self.cells))
            self.cells = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def _parse_offsets(html, model):
    model = model.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.+ -]{3,80}", model):
        raise OffsetError("Invalid drive model")
    model_pattern = re.compile(
        r"(?<![A-Za-z0-9])" + re.escape(model) + r"(?![A-Za-z0-9])", re.I)
    parser = _Rows()
    parser.feed(html)
    records = []
    purged = False
    for row in parser.rows:
        line = re.sub(r"\s+", " ", row).strip()
        match = _ROW.fullmatch(line)
        if not match:
            excluded = _PURGED.fullmatch(line)
            if excluded and model_pattern.search(excluded[1]):
                purged = True
            continue
        name, offset, submissions, agreement = match.groups()
        if not model_pattern.search(name):
            continue
        percent = float(agreement)
        if percent > 100:
            continue
        records.append({"name": name, "offset_samples": int(offset),
                        "submissions": int(submissions), "agreement_percent": percent})
    return records, purged


def parse_offsets(html, model):
    return _parse_offsets(html, model)[0]


def _database_html():
    global _DATABASE_CACHE
    # Settings initializes several drives at once. Share one successful
    # download across callers and let transient failures be retried.
    with _CACHE_LOCK:
        if _DATABASE_CACHE and time.monotonic() < _DATABASE_CACHE[0]:
            return _DATABASE_CACHE[1]
        request = Request(URL, headers={"User-Agent": "OSCAR/0.1 drive-offset-assistant"})
        try:
            with urlopen(request, timeout=8) as reply:
                if reply.status != 200:
                    raise OffsetError("Offset database temporarily unavailable")
                data = reply.read(_MAX_DATABASE_BYTES + 1)
        except OSError as exc:
            raise OffsetError("Offset database unavailable; use manual lookup") from exc
        if len(data) > _MAX_DATABASE_BYTES:
            raise OffsetError("Offset database response too large")
        html = data.decode("utf-8", errors="replace")
        _DATABASE_CACHE = (time.monotonic() + _CACHE_SECONDS, html)
        return html


def lookup(model, *, html=None):
    records, purged = _parse_offsets(_database_html() if html is None else html, model)
    matches = []
    for record in records:
        matches.append({**record,
                        "estimated_confirmations": round(record["submissions"] * record["agreement_percent"] / 100),
                        "selectable": -2000 <= record["offset_samples"] <= 2000})
    matches.sort(key=lambda row: (-row["estimated_confirmations"], -row["submissions"],
                                  row["name"].casefold(), row["offset_samples"]))
    unique = {row["offset_samples"] for row in matches}
    selectable = [row for row in matches if row["selectable"] and row["estimated_confirmations"] > 0]
    leading = None
    if selectable:
        first = selectable[0]
        best_offsets = {row["offset_samples"] for row in selectable
                        if row["estimated_confirmations"] == first["estimated_confirmations"]}
        if len(best_offsets) == 1 and not purged:
            leading = first["offset_samples"]
    suggested = None
    if len(unique) == 1 and leading is not None and any(
            row["submissions"] >= 10 and row["agreement_percent"] >= 90 for row in matches):
        suggested = leading
    return {"source": URL, "model": model, "matches": matches, "leading_offset": leading,
            "purged": purged, "suggested_offset": suggested,
            "status": "suggestion" if suggested is not None else
                      ("conflict" if len(unique) > 1 else "manual_review")}


def disc_calibration(device, *, runner=subprocess.run):
    """Explicit non-ripping cyanrip -f operation. No settings writes.

    CLI stdout varies by cyanrip version: require one unambiguous declaration.
    """
    if not re.fullmatch(r"/dev/sr\d+", device):
        raise OffsetError("Invalid optical device")
    try:
        result = runner(["cyanrip", "-d", device, "-f", "-N", "-U", "-G"],
                        capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OffsetError("Disc offset detection unavailable or timed out") from exc
    output = (result.stdout or "") + "\n" + (result.stderr or "")
    offsets = {int(v) for v in re.findall(
        r"(?:drive\s+)?(?:read\s+)?offset(?:\s+correction)?\s*(?:is|:|=|found)?\s*([+-]\d{1,4})\b",
        output, flags=re.I)}
    if result.returncode != 0 or len(offsets) != 1:
        return {"status": "manual_review", "suggested_offset": None,
                "message": ("No unambiguous drive offset found. Try an AccurateRip-known retail CD, "
                            "or consult the offset database. The offset was not saved."),
                "exit_code": result.returncode}
    return {"status": "suggestion", "suggested_offset": offsets.pop(),
            "message": "Disc-based candidate; review and save manually. Not yet hardware-validated."}
