"""No physical hardware or MusicBrainz HTTP required for unit tests."""
import io
import json

import pytest
from fastapi.testclient import TestClient

from oscar.api import app
from oscar import toc, musicbrainz


class FakeLib:
    def __init__(self, success=True):
        self.success = success
        self.freed = False
        self.calls = []
    def discid_new(self): return 123
    def discid_free(self, h):
        assert h == 123
        self.freed = True
    def discid_read_sparse(self, h, dev, flags):
        self.calls.append((h, dev, flags))
        return int(self.success)
    def discid_get_error_msg(self, h): return b"TOC read failed"
    def discid_get_first_track_num(self, h): return 1
    def discid_get_last_track_num(self, h): return 2
    def discid_get_sectors(self, h): return 37500
    def discid_get_track_offset(self, h, n): return [150, 15150][n - 1]
    def discid_get_track_length(self, h, n): return [15000, 22350][n - 1]
    def discid_get_id(self, h): return b"I5l9cCSFccLKFEKS.7wqSZAorPU-"
    def discid_get_toc_string(self, h): return b"1 2 37500 150 15150"


def test_read_toc_uses_toc_only():
    lib = FakeLib()
    result = toc.read_toc("/dev/sr2", lib)
    assert lib.calls == [(123, b"/dev/sr2", 0)]
    assert lib.freed
    assert result["tracks"][0]["duration_seconds"] == 200
    assert result["tracks"][1]["start_sector"] == 15150
    assert result["musicbrainz_disc_id"] == "I5l9cCSFccLKFEKS.7wqSZAorPU-"
    assert not result["pregaps_checked"]
    assert not result["htoa_checked"]


def test_toc_failure_always_frees_handle():
    lib = FakeLib(success=False)
    with pytest.raises(toc.TocError, match="TOC read failed"):
        toc.read_toc("/dev/sr2", lib)
    assert lib.freed


def test_toc_rejects_non_optical_path():
    with pytest.raises(toc.TocError):
        toc.read_toc("/dev/sda", FakeLib())


def test_toc_api_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OSCAR_ENABLE_TOC_PROBE", raising=False)
    assert TestClient(app).get("/api/toc", params={"stable_id": "ata-Optiarc"}).status_code == 403


def test_toc_api_requires_configured_drive(monkeypatch):
    monkeypatch.setenv("OSCAR_ENABLE_TOC_PROBE", "1")
    import oscar.api as api
    from oscar.settings import OscarSettings
    monkeypatch.setattr(api, "discover_settings", lambda: OscarSettings())
    monkeypatch.setattr(api, "inspect_drives", lambda: [
        {"stable_id": "ata-Optiarc", "device": "/dev/sr2", "identity_persistent": True}
    ])
    assert TestClient(app).get("/api/toc", params={"stable_id": "ata-Optiarc"}).status_code == 403


class FakeResponse:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return json.dumps({
        "releases": [
            {
                "id": "a2342fe1-04b2-4a3f-bad4-eca6c7ee9e1c",
                "title": "One release",
                "artist-credit": [{"name": "Orchestra"}],
                "label-info": [{
                    "label": {"name": "Decca"},
                    "catalog-number": "ABC 123"
                }],
                "date": "1996",
            },
            {
                "id": "b2342fe1-04b2-4a3f-bad4-eca6c7ee9e1c",
                "title": "Another edition",
                "artist-credit": [{"name": "Orchestra"}],
                "date": "2003"
            }
        ]
    }).encode()


def test_musicbrainz_retains_multiple_release_candidates(monkeypatch):
    monkeypatch.setattr(musicbrainz.time, "sleep", lambda n: None)
    monkeypatch.setattr(musicbrainz.time, "monotonic", lambda: 10000.0)
    result = musicbrainz.lookup_releases(
        "I5l9cCSFccLKFEKS.7wqSZAorPU-", "1 2 37500 150 15150",
        opener=lambda request, timeout: FakeResponse(),
    )
    assert len(result["releases"]) == 2
    assert result["requires_review"] is True
    assert result["releases"][0]["labels"][0]["catalog_number"] == "ABC 123"


def test_musicbrainz_rejects_untrusted_discid():
    with pytest.raises(musicbrainz.MusicBrainzError):
        musicbrainz.lookup_releases("../../etc/passwd", "1 2 37500 150 15150")
