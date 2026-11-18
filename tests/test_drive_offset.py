"""Offline tests for read-only AccurateRip offset workflow."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
from oscar.api import app
from oscar.drive_offset import lookup, disc_calibration, parse_offsets
from oscar.web import settings_page

HTML = """<html><table>
<tr><td>LG Electronics - DVD-RAM GH24NS95</td><td>+667</td><td>1</td><td>100%</td></tr>
<tr><td>LG Electronics - DVDRAM GH24NS95</td><td>+6</td><td>1315</td><td>100%</td></tr>
<tr><td>Optiarc - DVD RW AD-7200S</td><td>+48</td><td>1157</td><td>100%</td></tr>
<tr><td>Optiarc - DVD RW AD-7200SX</td><td>+8</td><td>1000</td><td>100%</td></tr>
</table></html>"""


def test_exact_model_match_ignores_prefix():
    rows = parse_offsets(HTML, "AD-7200S")
    assert len(rows) == 1
    assert rows[0]["offset_samples"] == 48


def test_db_suggestion_requires_submissions():
    result = lookup("AD-7200S", html=HTML)
    assert result["status"] == "suggestion"
    assert result["suggested_offset"] == 48


def test_conflicting_model_requires_review_even_when_one_is_popular():
    result = lookup("GH24NS95", html=HTML)
    assert result["status"] == "conflict"
    assert result["suggested_offset"] is None
    assert {r["offset_samples"] for r in result["matches"]} == {6, 667}


def test_disc_calibration_only_proposes_without_saving():
    args_seen = []
    def runner(args, **kwargs):
        args_seen.extend(args)
        return SimpleNamespace(returncode=0, stdout="Drive offset: +48", stderr="")
    result=disc_calibration("/dev/sr2",runner=runner)
    assert result["suggested_offset"]==48
    assert args_seen==["cyanrip","-d","/dev/sr2","-f","-N","-U","-G"]


def test_disc_calibration_without_reference_entry_does_not_guess():
    result=disc_calibration("/dev/sr2",runner=lambda *a,**k:
        SimpleNamespace(returncode=1,stdout="No AccurateRip entry",stderr=""))
    assert result["suggested_offset"] is None


def test_ui_shows_both_auto_and_manual_paths():
    html = settings_page().body.decode()
    assert "Look up offset" in html
    assert "Detect from CD (experimental)" in html
    assert "https://www.accuraterip.com/driveoffsets.htm" in html


def test_calibration_requires_token(monkeypatch):
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING","1")
    monkeypatch.setenv("OSCAR_RIP_TOKEN","0123456789abcdef0123456789abcdef")
    r=TestClient(app).post("/api/drive-offset/from-disc",
      json={"stable_id":"test","confirmation":"CALIBRATE_OFFSET"})
    assert r.status_code==403
