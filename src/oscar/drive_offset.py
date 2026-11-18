"""Read-only AccurateRip drive-offset lookup and opt-in disc calibration.

A drive model may appear multiple times with conflicting reported offsets.
In that case, never silently select one. This module never persists settings.
"""
from html.parser import HTMLParser
import re
import subprocess
from urllib.request import Request, urlopen

URL = "https://www.accuraterip.com/driveoffsets.htm"
_ROW = re.compile(r"^(.+?)\s+([+-]\d{1,5})\s+(\d+)\s+(\d+(?:\.\d+)?)%\s*$")


class OffsetError(RuntimeError):
    pass


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("tr", "br", "p", "li"):
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("tr", "p", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def parse_offsets(html, model):
    if not re.fullmatch(r"[A-Za-z0-9_.+ -]{3,80}", model):
        raise OffsetError("Invalid drive model")
    parser = _Text()
    parser.feed(html)
    text = "".join(parser.parts)
    records = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        match = _ROW.fullmatch(line)
        if not match:
            continue
        name, offset, submissions, agreement = match.groups()
        # Model must be the final token in vendor/model field, not a prefix
        # of a differently identified drive such as GH24NS950.
        if not re.search(r"(?<![A-Za-z0-9])" + re.escape(model.strip()) +
                         r"(?![A-Za-z0-9])", name, re.I):
            continue
        records.append({"name": name, "offset_samples": int(offset),
                        "submissions": int(submissions),
                        "agreement_percent": float(agreement)})
    return records


def lookup(model, *, html=None):
    if html is None:
        request = Request(URL, headers={"User-Agent": "OSCAR/0.1 drive-offset-assistant"})
        try:
            with urlopen(request, timeout=8) as reply:
                if reply.status != 200:
                    raise OffsetError("Offset database temporarily unavailable")
                # Avoid parsing unbounded content on a compromised endpoint.
                data = reply.read(1_500_001)
                if len(data) > 1_500_000:
                    raise OffsetError("Offset database response too large")
                html = data.decode("utf-8", errors="replace")
        except (OSError, TimeoutError) as exc:
            raise OffsetError("Offset database unavailable; use manual lookup") from exc
    matches = parse_offsets(html, model)
    unique = sorted({entry["offset_samples"] for entry in matches})
    # If two differently labelled model records disagree, show all instead of
    # arbitrarily trusting the majority. E.g. GH24NS95 has +6 and +667 entries.
    suggested = unique[0] if len(unique) == 1 and any(
        entry["submissions"] >= 10 and entry["agreement_percent"] >= 90
        for entry in matches) else None
    return {"source": URL, "model": model, "matches": matches,
            "suggested_offset": suggested,
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
