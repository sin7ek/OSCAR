import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen.flac import FLAC

from oscar import external_verification as external


def test_candidate_toc():
    assert external.candidate_toc([588 * 100, 588 * 200]) == [1, 2, 450, 150, 250]


@pytest.mark.parametrize("samples", [[], [0], [589], [-588], [588] * 100, [588 * 450001]])
def test_unsupported_layout(samples):
    with pytest.raises(ValueError):
        external.candidate_toc(samples)


@pytest.fixture
def make_flac(tmp_path):
    if not shutil.which("flac"):
        pytest.skip("FLAC executable required")

    def create(name, tags):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["flac", "--silent", "--force-raw-format", "--endian=little", "--sign=signed",
             "--channels=2", "--bps=16", "--sample-rate=44100", "-o", str(path), "-"],
            input=bytes(588 * 100 * 4), check=True,
        )
        audio = FLAC(path)
        audio.update(tags)
        audio.save()
        return path

    return create


def verifier(toc_line, status="found", confidence=2):
    def run(command, **kwargs):
        if command[0] == "flac":
            return subprocess.run(command, **kwargs)
        assert command[:3] == ["/opt/ctdb/ctdb-cli", "--xml", "verify"]
        cue = Path(command[-1])
        assert cue.parent == kwargs["cwd"]
        assert cue.read_text().count("INDEX 01 00:00:00") == len(toc_line.split(":")) - 1
        assert (cue.parent / "01.flac").is_symlink()
        xml = (
            '<ctdb xmlns="http://db.cuetools.net/ns/mmd-1.0#">'
            f'<verify_result xmlns="" status="{status}" confidence="{confidence}" '
            'total_entries="3" toc="test-toc" /></ctdb>'
        ).encode()
        return SimpleNamespace(returncode=0, stderr=f"CTDB request TOC: {toc_line}\n".encode(),
                               stdout=xml)

    return run


def test_external_match_with_tagged_multidisc_flacs(tmp_path, make_flac):
    paths = [
        make_flac("CD1/20 not filename order.flac", {"tracknumber": "1/2", "discnumber": "1/2"}),
        make_flac("CD1/01.flac", {"tracknumber": "02", "tracktotal": "2", "discnumber": "1"}),
        make_flac("CD2/track.flac", {"tracknumber": "01/1", "discnumber": "2/2"}),
    ]
    (tmp_path / "SOURCES.txt").write_text("Existing evidence\n")
    hashes = {path: external.digest(path) for path in paths}
    run = verifier("0:100:200")

    def run_multidisc(command, **kwargs):
        if command[0] == "flac":
            return run(command, **kwargs)
        cue = Path(command[-1])
        first = (cue.parent / "01.flac").resolve()
        if first == paths[2]:
            return verifier("0:100")(command, **kwargs)
        assert first == paths[0]
        assert (cue.parent / "02.flac").resolve() == paths[1]
        return run(command, **kwargs)

    report = external.verify(tmp_path, executable="/opt/ctdb/ctdb-cli", runner=run_multidisc)
    assert report["status"] == "database_matched_candidate_layout"
    assert report["source_type"] == "external"
    assert report["disc_total_declared"] is True
    assert report["assumed_single_disc"] is False
    for disc in report["discs"]:
        assert disc["ctdb"]["status"] == "matched"
        assert disc["ctdb"]["confidence"] == 2
        assert disc["accuraterip"]["status"] == "not_performed"
    assert {path: external.digest(path) for path in paths} == hashes
    assert set(p for p in tmp_path.rglob("*") if p.is_file()) == {*paths, tmp_path / "SOURCES.txt"}
    assert (tmp_path / "SOURCES.txt").read_text() == "Existing evidence\n"


@pytest.mark.parametrize(("toc", "service_status", "confidence", "ctdb_status"), [
    ("0:999", "found", 2, "lookup_failed"),
    ("0:100", "not_found", 0, "not_found"),
    ("0:100", "found", 0, "no_audio_match"),
])
def test_ctdb_status_for_single_disc_without_total(
    tmp_path, make_flac, toc, service_status, confidence, ctdb_status,
):
    make_flac("track.flac", {"tracknumber": "01"})
    report = external.verify(tmp_path, executable="/opt/ctdb/ctdb-cli",
                             runner=verifier(toc, service_status, confidence))
    assert report["status"] == "integrity_passed"
    assert report["assumed_single_disc"] is True
    assert report["discs"][0]["track_total_declared"] is False
    assert report["discs"][0]["ctdb"]["status"] == ctdb_status


@pytest.mark.parametrize(("first", "second"), [
    ({"tracknumber": "1/3"}, {"tracknumber": "2"}),
    ({"tracknumber": "1"}, {"tracknumber": "1"}),
    ({"tracknumber": "1"}, {"tracknumber": "3"}),
    ({"tracknumber": "1", "discnumber": "1/2"}, {"tracknumber": "2"}),
    ({"tracknumber": "1/2", "tracktotal": "3"}, {"tracknumber": "2"}),
])
def test_inventory_rejects_ambiguous_or_incomplete_numbering(tmp_path, make_flac, first, second):
    make_flac("first.flac", first)
    make_flac("second.flac", second)
    with pytest.raises(ValueError, match="track|TRACKNUMBER|disc"):
        external.inventory(tmp_path)


def test_source_changed(tmp_path, make_flac):
    path = make_flac("track.flac", {"tracknumber": "1"})

    def runner(command, **kwargs):
        with path.open("ab") as stream:
            stream.write(b"changed")
        return SimpleNamespace(returncode=1)

    with pytest.raises(ValueError, match="Source FLACs changed"):
        external.verify(tmp_path, runner=runner)


@pytest.mark.parametrize(("integrity", "raises"), [("failed", False), ("unavailable", True)])
def test_integrity_failure_prevents_ctdb(tmp_path, make_flac, integrity, raises):
    make_flac("track.flac", {"tracknumber": "1"})

    def runner(command, **kwargs):
        assert command[0] == "flac"
        if raises:
            raise FileNotFoundError("flac")
        return SimpleNamespace(returncode=1)

    report = external.verify(tmp_path, executable="/opt/ctdb/ctdb-cli", runner=runner)
    assert report["status"] == f"integrity_{integrity}"
    assert report["discs"][0]["file_integrity"] == {"track.flac": integrity}
    assert report["discs"][0]["ctdb"]["status"] == "not_performed"


def test_reject_symlink(tmp_path, make_flac):
    path = make_flac("track.flac", {"tracknumber": "1"})
    (tmp_path / "link.flac").symlink_to(path)
    with pytest.raises(ValueError, match="Symlink"):
        external.inventory(tmp_path)
