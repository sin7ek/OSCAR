import hashlib
import json

import pytest

from oscar import cd_extra, toc


@pytest.fixture
def data_rip(tmp_path, monkeypatch):
    (tmp_path / "audio").mkdir()
    (tmp_path / "plan.json").write_text(json.dumps({"toc_string": "saved"}))
    layout = {"track": 3, "source": "audio/03 - Unknown track.bin",
              "format": "MODE1/2352", "start_lsn": 0, "sectors": 2, "size": 4704}
    monkeypatch.setattr(cd_extra, "geometry", lambda root: layout)
    monkeypatch.setattr(toc, "read_toc", lambda device: {"toc_string": "saved"})
    sectors = b"".join(b"\x00" + b"\xff" * 10 + b"\x00\x00\x02" +
                       bytes([frame, 1]) + b"\x00" * 2336 for frame in range(2))
    return tmp_path, layout, sectors


def test_capture_reads_twice_and_records_raw_digest(data_rip):
    root, layout, sectors = data_rip
    calls = []

    def reader(device, geometry):
        calls.append((device, geometry))
        yield sectors

    record = cd_extra.capture(root, "/dev/sr2", reader=reader)
    assert len(calls) == 2
    assert record["sha256"] == hashlib.sha256(sectors).hexdigest()
    assert record["verification"] == "two_matching_raw_reads"
    assert (root / layout["source"]).read_bytes() == sectors


def test_inconsistent_data_reads_leave_partial_only(data_rip):
    root, layout, sectors = data_rip
    calls = []

    def reader(device, geometry):
        calls.append(1)
        yield sectors if len(calls) == 1 else sectors[:-1] + b"\xff"

    with pytest.raises(cd_extra.DataError, match="differ"):
        cd_extra.capture(root, "/dev/sr2", reader=reader)
    assert not (root / layout["source"]).exists()
    assert (root / layout["source"]).with_suffix(".bin.partial").read_bytes() == sectors
