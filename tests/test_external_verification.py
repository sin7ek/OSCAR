from pathlib import Path
from types import SimpleNamespace

import pytest

from oscar import external_verification as external


def test_candidate_toc():
    assert external.candidate_toc([588 * 100, 588 * 200]) == [1, 2, 450, 150, 250]


@pytest.mark.parametrize("samples", [[], [0], [589], [-588]])
def test_invalid_layout(samples):
    with pytest.raises(ValueError):
        external.candidate_toc(samples)


def test_external_match_does_not_claim_physical_rip(tmp_path, monkeypatch):
    path = tmp_path / "track.flac"
    path.write_bytes(b"fixture")
    info = SimpleNamespace(sample_rate=44100, channels=2, bits_per_sample=16,
                           total_samples=588 * 100)
    monkeypatch.setattr(external, "inventory",
                        lambda album: (tmp_path, {1: [(1, 1, 1, path, info)]}))
    def runner(command, **kwargs):
        if command[0] == "flac":
            return SimpleNamespace(returncode=0)
        cue = Path(command[-1])
        assert 'INDEX 01 00:00:00' in cue.read_text()
        assert (cue.parent / "01.flac").resolve() == path
        return SimpleNamespace(returncode=0, stderr=b"", stdout=b"fixture")
    monkeypatch.setattr(external, "parse_result",
                        lambda output: {"status": "matched", "confidence": 2, "total": 3})
    report = external.verify(tmp_path, executable="/fake/ctdb", runner=runner)
    assert report["status"] == "database_matched_candidate_layout"
    assert report["source_type"] == "external"
    assert report["discs"][0]["accuraterip"]["status"] == "not_performed"
    assert path.read_bytes() == b"fixture"


def test_source_changed(tmp_path, monkeypatch):
    path = tmp_path / "track.flac"
    path.write_bytes(b"fixture")
    info = SimpleNamespace(sample_rate=44100, channels=2, bits_per_sample=16,
                           total_samples=588)
    monkeypatch.setattr(external, "inventory",
                        lambda album: (tmp_path, {1: [(1, 1, 1, path, info)]}))
    def runner(command, **kwargs):
        path.write_bytes(b"changed")
        return SimpleNamespace(returncode=1)
    with pytest.raises(ValueError, match="Source changed"):
        external.verify(tmp_path, runner=runner)
