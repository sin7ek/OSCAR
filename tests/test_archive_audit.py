"""Read-only OSCAR archive audit regression tests."""
import hashlib
import json
import shutil
import subprocess
import wave

import pytest

from oscar.archive_audit import audit_archive, audit_release


def _flac(folder, name):
    pcm = folder / "sample.wav"
    with wave.open(str(pcm), "wb") as source:
        source.setnchannels(1)
        source.setsampwidth(2)
        source.setframerate(44100)
        source.writeframes(b"\x00\x00" * 300)
    target = folder / name
    subprocess.run(["flac", "--silent", "-f", "-o", str(target), str(pcm)], check=True)
    pcm.unlink()
    return target


@pytest.fixture
def release(tmp_path):
    if not shutil.which("flac"):
        pytest.skip("flac executable required")
    folder = tmp_path / "Artist" / "Album"
    folder.mkdir(parents=True)
    audio = _flac(folder, "01 - Example.flac")
    cue = folder / "album.cue"
    cue.write_text('FILE "01 - Example.flac" WAVE\n  TRACK 01 AUDIO\n    INDEX 01 00:00:00\n')
    evidence_dir = folder / "ExtractionEvidence" / "audio"
    evidence_dir.mkdir(parents=True)
    original = evidence_dir / "Unknown disc.cue"
    original.write_bytes(b"original source cue\n")
    (folder / "SOURCES.txt").write_text("SOURCE_TYPE: PHYSICAL_CD_RIP\n")
    manifest = {
        "status": "published_verified", "job_id": "a" * 32, "copy_id": "b" * 32,
        "files": [{"filename": audio.name, "sha256": hashlib.sha256(audio.read_bytes()).hexdigest()}],
        "cue": {"filename": cue.name, "sha256": hashlib.sha256(cue.read_bytes()).hexdigest()},
        "source_evidence": [{
            "filename": "ExtractionEvidence/audio/Unknown disc.cue",
            "sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
            "size": original.stat().st_size,
        }],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest))
    return folder


def test_clean_release_passes(release):
    result = audit_release(release)
    assert result["status"] == "PASS"
    assert result["source_type"] == "PHYSICAL_CD_RIP"
    assert result["verification"]["ctdb"] == "NOT_INDEPENDENTLY_CHECKED"


def test_tampered_audio_fails(release):
    with (release / "01 - Example.flac").open("ab") as stream:
        stream.write(b"tamper")
    result = audit_release(release)
    assert result["status"] == "FAIL"
    assert any(e["code"] == "SHA256_MISMATCH" for e in result["errors"])


def test_tampered_evidence_fails(release):
    (release / "ExtractionEvidence/audio/Unknown disc.cue").write_text("modified")
    result = audit_release(release)
    assert any(e["code"] == "EVIDENCE_MISMATCH" for e in result["errors"])


def test_cue_reference_escape_blocked(release):
    cue = release / "album.cue"
    cue.write_text('FILE "../other.flac" WAVE\n  TRACK 01 AUDIO\n INDEX 01 00:00:00\n')
    result = audit_release(release)
    assert any(e["code"] == "CUE_BAD_REFERENCE" for e in result["errors"])


def test_digital_release_does_not_require_eac_or_cue(tmp_path):
    if not shutil.which("flac"):
        pytest.skip("flac executable required")
    folder = tmp_path / "Ruffneck" / "Collection XI"
    folder.mkdir(parents=True)
    _flac(folder, "01 - Track.flac")
    (folder / "SOURCES.txt").write_text("SOURCE_TYPE: DIGITAL_ACQUISITION\n")
    result = audit_release(folder)
    assert result["status"] == "PASS_WITH_WARNINGS"
    assert not any(i["code"] in {"MISSING_CUE", "EVIDENCE_NOT_EMBEDDED"}
                   for i in result["warnings"])


def test_unknown_provenance_is_not_guessed(tmp_path):
    folder = tmp_path / "Unknown"
    folder.mkdir()
    result = audit_release(folder)
    assert result["source_type"] == "UNKNOWN"


def test_album_discovery_skips_historical_evidence(release):
    other = release / "Verification" / "FailedAttempts"
    other.mkdir(parents=True)
    (other / "bad.flac").write_bytes(b"broken historical attempt")
    result = audit_archive(release.parent.parent)
    assert result["releases_examined"] == 1
    assert result["active_flacs"] == 1
