import hashlib
import json
import struct
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from oscar import cd_extra_accuraterip, ctdb_verification, ripping, verification


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


def test_verify_cyanrip_split_pregap_cue(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(tmp_path))
    monkeypatch.setenv("OSCAR_CTDB_EXECUTABLE", "/opt/ctdb/ctdb-cli")
    job = "b" * 32
    directory = tmp_path / ("oscar-" + job)
    audio = directory / "audio"
    audio.mkdir(parents=True)
    manifest = {}
    lines = []
    for number in range(1, 16):
        name = f"{number:02d} - Unknown track.flac"
        data = f"test track {number}".encode()
        (audio / name).write_bytes(data)
        manifest["audio/" + name] = hashlib.sha256(data).hexdigest()
        lines.extend([f'FILE "{name}" WAVE', f"  TRACK {number:02d} AUDIO", "    INDEX 01 00:00:00"])
        if number in {1, 2, 14}:
            lines.extend([f"  TRACK {number + 1:02d} AUDIO", "    INDEX 00 04:52:07"])
    cue = audio / "disc.cue"
    original = ("\r\n".join(lines) + "\r\n").encode()
    cue.write_bytes(original)
    (directory / "state.json").write_text(json.dumps({
        "id": job, "status": "needs_verification", "returncode": 0,
        "files_sha256": manifest,
    }))
    (directory / "plan.json").write_text('{"track_count": 15}')

    def runner(args, **kwargs):
        compatible = type(cue)(args[-1])
        assert compatible != cue
        assert kwargs["cwd"] == compatible.parent
        emitted = compatible.read_text().splitlines()
        assert sum(line.strip().startswith("TRACK") for line in emitted) == 15
        assert [line for line in emitted if "FILE " in line or "INDEX " in line] == [
            line for line in lines if "FILE " in line or "INDEX " in line]
        for path in audio.glob("*.flac"):
            assert (compatible.parent / path.name).resolve() == path
        return SimpleNamespace(returncode=0, stdout=xml("found", 3, 4), stderr=b"")

    assert ctdb_verification.verify(job, runner=runner)["status"] == "matched"
    assert cue.read_bytes() == original
    assert not list(directory.glob(".ctdb-cue-*"))
    result, _ = ctdb_verification.saved_evidence(job, directory)
    assert result["cue_layout"] == "cyanrip_split_pregaps"
    assert result["verifier_cue_sha256"] != hashlib.sha256(original).hexdigest()

    cue.write_bytes(original.replace(b"INDEX 00", b"INDEX 01", 1))
    with pytest.raises(ripping.RipError, match="ordered full-disc"):
        ctdb_verification.verify(job, runner=runner)
    assert ctdb_verification.saved_evidence(job, directory) is None

def test_ctdb_uses_saved_audio_toc_for_trailing_cd_extra_data_track(tmp_path, monkeypatch):
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(tmp_path))
    monkeypatch.setenv("OSCAR_CTDB_EXECUTABLE", "/opt/ctdb/ctdb-cli")
    job = "c" * 32
    directory = tmp_path / ("oscar-" + job)
    audio = directory / "audio"
    audio.mkdir(parents=True)
    offsets = [0, 10551, 34064, 49877, 73925, 96418, 120451, 142777, 160183,
               178556, 195592, 215025, 229446, 245987, 262818, 278257]
    manifest = {}
    lines = []
    for number in range(1, 16):
        name = f"{number:02d} - Unknown track.flac"
        data = f"test track {number}".encode()
        (audio / name).write_bytes(data)
        manifest["audio/" + name] = hashlib.sha256(data).hexdigest()
        lines.extend([f'FILE "{name}" WAVE', f"  TRACK {number:02d} AUDIO", "    INDEX 01 00:00:00"])
    audio_cue = "\n".join(lines) + "\n"
    cue = audio / "disc.cue"
    data_track = audio / "16 - Unknown track.bin"
    data_track.write_bytes(b"data session")
    original = audio_cue + ('FILE "16 - Unknown track.bin" BINARY\n'
                            '  TRACK 16 MODE1/2352\n    PREGAP 02:32:00\n    INDEX 01 00:00:00\n')
    cue.write_text(original)
    (directory / "state.json").write_text(json.dumps({
        "id": job, "status": "needs_verification", "returncode": 0, "files_sha256": manifest,
    }))
    plan = {"track_count": 15, "toc_string": " ".join(
        str(value) for value in [1, 15, offsets[-1] + 150, *(o + 150 for o in offsets[:-1])])}
    plan_path = directory / "plan.json"
    plan_path.write_text(json.dumps(plan))
    log = audio / "disc.log"
    log.write_text(
        "Track 16 is data:\n  Properties:\n"
        "    Data bytes:  145247760 (138.52 Mib)\n"
        "    Frames:      61755\n"
        "    Pregap LSN:  278257 (duration: 00:02:32.120)\n"
        "    Start LSN:   289657\n"
        "    End LSN:     351411\n"
    )
    full_toc = ":".join([*map(str, offsets[:-1]), "-289657", "351412"])

    def flac(path):
        number = int(path.name[:2])
        samples = 588 * (offsets[number] - offsets[number - 1])
        return SimpleNamespace(info=SimpleNamespace(
            total_samples=samples, sample_rate=44100, channels=2, bits_per_sample=16))

    monkeypatch.setattr(ctdb_verification, "FLAC", flac)

    def runner(args, **kwargs):
        assert args[-2:] == ["--disc-toc", full_toc]
        compatible = Path(args[3])
        assert compatible.read_text() == audio_cue
        assert not list(compatible.parent.glob("*.bin"))
        return SimpleNamespace(returncode=0, stdout=xml("found", 5, 7),
                               stderr=f"CTDB request TOC: {full_toc}\n".encode())

    result = ctdb_verification.verify(job, runner=runner)
    assert result["status"] == "matched"
    assert result["cue_layout"] == "cd_extra_full_toc"
    assert result["disc_toc"] == full_toc
    assert cue.read_text() == original
    assert data_track.read_bytes() == b"data session"
    assert ctdb_verification.saved_evidence(job, directory)[0]["disc_toc"] == full_toc

    # The original cyanrip lookup missed this pressing, but its calculated
    # CRCs can be compared with the correct full-disc AccurateRip entry.
    records = []
    for number in range(1, 16):
        records.append(
            f"EAC CRC32: ABCDEF01\nAccurip: not found\n"
            f"Accurip v1: {number:08X}\nAccurip v2: {number + 100:08X}\n"
            f"Metadata:\n  track: {number}\nFile(s):\n"
            f"  audio/{number:02d} - Unknown track.flac\n")
    console = directory / "cyanrip-console.log"
    console.write_text("".join(records) + "Ripping errors: 0\n")
    ids = cd_extra_accuraterip.identifiers(full_toc)
    assert ids == (15, 0x00241E6A, 0x019F2496, 0xF4124D10)
    reference = struct.pack("<BIII", *ids) + b"".join(
        struct.pack("<BII", 1, number + 100, 0) for number in range(1, 16))

    def ar_lookup(request, timeout):
        assert request.full_url.endswith("/a/6/e/dBAR-015-00241e6a-019f2496-f4124d10.bin")
        return BytesIO(reference)

    monkeypatch.setattr(cd_extra_accuraterip, "urlopen", ar_lookup)
    report_with_ar = verification._verify(directory, job, runner=lambda *args, **kwargs:
        SimpleNamespace(returncode=0))
    assert report_with_ar["status"] == "checks_passed"
    assert report_with_ar["verification_method"] == "cyanrip_cd_extra_accuraterip_lookup"
    assert report_with_ar["single_version_tracks"] == list(range(1, 16))
    assert report_with_ar["accuraterip_lookup"]["matched_tracks"] == 15
    assert all(track["accuraterip"]["v2"]["confidence"] == 1 for track in report_with_ar["tracks"])
    assert all("v1" not in track["accuraterip"] for track in report_with_ar["tracks"])

    # A response with the wrong pressing IDs cannot provide confirmation.
    monkeypatch.setattr(cd_extra_accuraterip, "urlopen",
                        lambda *args, **kwargs: BytesIO(b"\x0e" + reference[1:]))
    report_wrong_ar = verification._verify(directory, job, runner=lambda *args, **kwargs:
        SimpleNamespace(returncode=0))
    assert report_wrong_ar["status"] == "review_required"
    assert report_wrong_ar["accuraterip_lookup"]["status"] == "lookup_failed"

    assert ctdb_verification.verify(job, runner=lambda *args, **kwargs:
        SimpleNamespace(returncode=0, stdout=xml("not_found"), stderr=b""))["status"] == "lookup_failed"
    assert ctdb_verification.saved_evidence(job, directory)[0]["status"] == "matched"

    # A historical audio-only lookup is not evidence for the physical TOC.
    report = directory / ctdb_verification.REPORT
    old = json.loads(report.read_text())
    old["cue_layout"] = "cd_extra_audio_session"
    old.pop("disc_toc")
    report.write_text(json.dumps(old))
    assert ctdb_verification.saved_evidence(job, directory) is None

    original_log = log.read_text()
    log.write_text(original_log.replace("351411", "351412"))
    with pytest.raises(ripping.RipError, match="data-track geometry disagrees"):
        ctdb_verification.verify(job, runner=runner)
    log.write_text(original_log)

    offsets[-1] += 1
    with pytest.raises(ripping.RipError, match="against the saved TOC"):
        ctdb_verification.verify(job, runner=runner)
    assert ctdb_verification.saved_evidence(job, directory) is None
