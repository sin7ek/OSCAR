import hashlib
import json
from types import SimpleNamespace

import pytest

from oscar import ctdb_verification, ripping


def xml(status, confidence=0, total=0):
    return (f'<ctdb xmlns="{ctdb_verification._NAMESPACE}">'
            f'<verify_result xmlns="" status="{status}" confidence="{confidence}" '
            f'total_entries="{total}" toc="disc" /></ctdb>').encode()


@pytest.mark.parametrize(("response", "expected"), [
    (xml("found", 4, 9), "matched"),
    (xml("found", 0, 9), "no_audio_match"),
    (xml("not_found"), "not_found"),
    (xml("failure"), "lookup_failed"),
])
def test_parse_ctdb_results(response, expected):
    assert ctdb_verification.parse_result(response)["status"] == expected


def test_verify_saved_disc_and_bind_evidence_to_exact_cue(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(tmp_path))
    monkeypatch.setenv("OSCAR_CTDB_EXECUTABLE", "/opt/ctdb/ctdb-cli")
    job = "a" * 32
    directory = tmp_path / ("oscar-" + job)
    audio = directory / "audio"
    audio.mkdir(parents=True)
    track = audio / "01 - Unknown track.flac"
    track.write_bytes(b"test fixture")
    cue = audio / "disc.cue"
    cue.write_text('FILE "01 - Unknown track.flac" WAVE\n TRACK 01 AUDIO\n INDEX 01 00:00:00\n')
    (directory / "state.json").write_text(json.dumps({
        "id": job, "status": "needs_verification", "returncode": 0,
        "files_sha256": {"audio/" + track.name: hashlib.sha256(track.read_bytes()).hexdigest()},
    }))
    (directory / "plan.json").write_text('{"track_count": 1}')

    def runner(args, **kwargs):
        assert args == ["/opt/ctdb/ctdb-cli", "--xml", "verify", str(cue)]
        return SimpleNamespace(returncode=0, stdout=xml("found", 2, 3), stderr=b"")

    assert ctdb_verification.verify(job, runner=runner)["confidence"] == 2
    assert ctdb_verification.saved_evidence(job, directory)[0]["status"] == "matched"
    cue.write_text(cue.read_text() + 'REM "changed"\n')
    assert ctdb_verification.saved_evidence(job, directory) is None
    track.write_bytes(b"changed")
    with pytest.raises(ripping.RipError, match="SHA-256"):
        ctdb_verification.verify(job, runner=runner)
