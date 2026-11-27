"""Track Recovery v1 is tested entirely offline; never access a real optical drive."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oscar.api import app
from oscar import track_recovery as recovery, ripping, workflow_ledger

ORIG = "a" * 32
DIAG = "b" * 32
DEST = "c" * 32
DISC = "1FGELhYaLaSf9MIPUxtlZGDbQU8-"
TOKEN = "0123456789abcdef0123456789abcdef"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def log_track(n, matched=True):
    status = "accurately ripped" if matched else "not accurately ripped"
    return (
        f"EAC CRC32: 12345678\n"
        f"Accurip: disc found in database (max confidence: 168)\n"
        f"Accurip v1: F506EE3C ({status}, confidence 36)\n"
        f"Accurip v2: 67189F07 ({status}, confidence 168)\n"
        f"Metadata:\n  track: {n}\n  tracktotal: 3\n"
        f"File(s):\n  audio/{n:02d} - Unknown track.flac\n"
    )


@pytest.fixture
def layout(tmp_path, monkeypatch):
    root = tmp_path / "stage"
    root.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setenv("OSCAR_RIP_ROOT", str(root))
    monkeypatch.setenv("OSCAR_WORKFLOW_DB", str(config / "workflow.sqlite3"))
    monkeypatch.setenv("OSCAR_RIP_TOKEN", TOKEN)
    monkeypatch.setenv("OSCAR_ENABLE_RIPPING", "1")
    monkeypatch.setattr(workflow_ledger, "discover_settings",
                        lambda: SimpleNamespace(secure_review_level="strict"))
    for job_id, selected in ((ORIG, None), (DIAG, [2])):
        directory = root / ("oscar-" + job_id)
        audio = directory / "audio"
        audio.mkdir(parents=True)
        hashes = {}
        for n in ([2] if selected else [1, 2, 3]):
            data = f"CD rip {job_id[0]} track {n}".encode()
            name = f"audio/{n:02d} - Unknown track.flac"
            (directory / name).write_bytes(data)
            hashes[name] = sha(data)
        plan = {"disc_id": DISC, "toc_string": "1 3 150 150 200 250 300",
                "track_count": 3, "selected_tracks": selected,
                "stable_id": "usb-LG" if selected else "ata-Optiarc",
                "offset_samples": 6 if selected else 48}
        (directory / "plan.json").write_text(json.dumps(plan))
        (directory / "state.json").write_text(json.dumps({
            "id": job_id, "disc_id": DISC,
            "status": "partial_diagnostic" if selected else "needs_verification",
            "returncode": 0, "files_sha256": hashes,
        }))
        (directory / "cyanrip-console.log").write_text(
            "".join(log_track(n) for n in ([2] if selected else [1, 2, 3]))
            + "Ripping errors: 0\n")
        if not selected:
            cue = "".join(
                f'FILE "{n:02d} - Unknown track.flac" WAVE\n'
                f'  TRACK {n:02d} AUDIO\n    INDEX 01 00:00:00\n'
                for n in (1, 2, 3)
            )
            (audio / "Unknown disc.cue").write_text(cue)
            (directory / "verification-report.json").write_text(json.dumps({
                "job_id": job_id, "status": "review_required",
                "ripping_errors": 0,
                "tracks": [{"number": n, "checks_passed": n != 2}
                           for n in (1, 2, 3)],
            }))
    return root


def _output(count=3, offset2=0, confidence2=168):
    lines = []
    for n in range(1, count + 1):
        lines.append(
            f"[ {n}/{count}]  /staging/oscar-{DEST}/audio/{n:02d} - Unknown track.flac "
            ": found (confidence 168)"
        )
    lines.append("AccurateRip V1 AccurateRip V2")
    for n in range(1, count + 1):
        offset = offset2 if n == 2 else 0
        conf = confidence2 if n == 2 else 168
        lines.append(
            f"/staging/oscar-{DEST}/audio/{n:02d} - Unknown track.flac "
            f"36 0 F506EE3C {conf} {offset} 67189F07"
        )
    return "\n".join(lines) + "\n"


def _runner(args, **kwargs):
    if args[0] == "flac":
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    assert args[:4] == ["trackverify", "-R", "-V", "normal"]
    assert len(args) == 7
    return SimpleNamespace(returncode=0, stdout=_output(), stderr="")


def test_preview_validates_cd_evidence_before_writing(layout):
    result = recovery.preview(ORIG, DIAG, [2])
    assert result["eligible"]
    assert result["replacement_tracks"] == [2]
    assert result["disc_id"] == DISC
    assert len(result["sources"]) == 3
    assert len(list(layout.glob("oscar-*"))) == 2


def test_full_recovery_copies_audio_verifies_independently_and_forces_manual_go(layout):
    before = {
        str(p): p.read_bytes() for d in (ORIG, DIAG)
        for p in (layout / ("oscar-" + d) / "audio").glob("*.flac")
    }
    dest = layout / ("oscar-" + DEST)
    dest.mkdir()
    (dest / "plan.json").write_text(json.dumps({
        "disc_id": DISC, "track_count": 3,
        "recovery": {"format": "OSCAR_TRACK_RECOVERY_V1",
                     "original_job_id": ORIG, "diagnostic_job_id": DIAG,
                     "selected_tracks": [2]},
    }))
    recovery._run(DEST, ORIG, DIAG, [2], runner=_runner)
    state = json.loads((dest / "state.json").read_text())
    report = json.loads((dest / "verification-report.json").read_text())
    provenance = json.loads((dest / "recovery-sources.json").read_text())
    assert state["status"] == "needs_verification"
    assert state["returncode"] == 0
    assert report["status"] == "checks_passed"
    assert report["verification_method"] == "independent_trackverify_R_v1_v2"
    assert len(report["tracks"]) == 3
    assert all(t["checks_passed"] for t in report["tracks"])
    assert report["tracks"][1]["source_job_id"] == DIAG
    track = provenance["tracks"][1]
    assert track["source_job_id"] == DIAG
    assert track["selected_attempt"]["drive_id"] == "usb-LG"
    assert track["selected_attempt"]["read_offset_samples"] == 6
    assert track["selected_attempt"]["sha256"] == sha(b"CD rip b track 2")
    assert track["excluded_attempt"]["job_id"] == ORIG
    assert track["excluded_attempt"]["sha256"] == sha(b"CD rip a track 2")
    assert track["excluded_attempt"]["drive_id"] == "ata-Optiarc"
    assert track["excluded_attempt"]["read_offset_samples"] == 48
    assert track["excluded_attempt"]["checks_passed"] is False
    assert "excluded_attempt" not in provenance["tracks"][0]
    assert not any(p.is_symlink() for p in (dest / "audio").iterdir())
    assert (dest / "audio" / "02 - Unknown track.flac").read_bytes() == (
        layout / ("oscar-" + DIAG) / "audio" / "02 - Unknown track.flac").read_bytes()
    for item, content in before.items():
        assert Path(item).read_bytes() == content
    with workflow_ledger._db() as db:
        ledger = db.execute("SELECT phase,identification_mode FROM workflow_jobs "
                            "WHERE job_id=?", (DEST,)).fetchone()
    assert ledger["phase"] == "RELEASE_REVIEW_PENDING"
    assert ledger["identification_mode"] == "semi_automatic"


@pytest.mark.parametrize("output", [_output(offset2=12), _output(confidence2=0),
                                    _output().replace("67189F07", "garbled", 1),
                                    _output().replace("found (confidence 168)", "not found", 1)])
def test_independent_ar_requires_complete_positive_results(output):
    with pytest.raises(recovery.RecoveryError):
        recovery._parse_trackverify(output, 3)


def test_mismatched_toc_and_hash_fail_closed(layout):
    diag_plan = layout / ("oscar-" + DIAG) / "plan.json"
    data = json.loads(diag_plan.read_text())
    data["toc_string"] = "2 3 150 150 200 250 300"
    diag_plan.write_text(json.dumps(data))
    with pytest.raises(recovery.RecoveryError, match="TOCs differ"):
        recovery.preview(ORIG, DIAG, [2])
    data["toc_string"] = "1 3 150 150 200 250 300"
    diag_plan.write_text(json.dumps(data))
    (layout / ("oscar-" + DIAG) / "audio" / "02 - Unknown track.flac").write_bytes(b"changed")
    with pytest.raises(recovery.RecoveryError, match="hash changed"):
        recovery.preview(ORIG, DIAG, [2])


def test_wrong_selection_and_negative_ar_rejected(layout):
    with pytest.raises(recovery.RecoveryError, match="selected tracks|Selected tracks"):
        recovery.preview(ORIG, DIAG, [1])
    with pytest.raises(recovery.RecoveryError, match="unique replacement"):
        recovery.preview(ORIG, DIAG, [2, 2])
    path = layout / ("oscar-" + DIAG) / "cyanrip-console.log"
    path.write_text(log_track(2, matched=False) + "Ripping errors: 0\n")
    with pytest.raises(recovery.RecoveryError, match="lacks a full AccurateRip"):
        recovery.preview(ORIG, DIAG, [2])


def test_authenticated_api_and_confirmation(layout, monkeypatch):
    client = TestClient(app)
    body = {"original_job_id": ORIG, "diagnostic_job_id": DIAG,
            "replacement_tracks": [2]}
    assert client.post("/api/track-recovery/preview", json=body).status_code == 403
    headers = {"X-OSCAR-RIP-TOKEN": TOKEN}
    response = client.post("/api/track-recovery/preview", json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["eligible"]
    response = client.post("/api/track-recovery/start",
                           json={**body, "confirmation": "WRONG"}, headers=headers)
    assert response.status_code == 409
    assert len(list(layout.glob("oscar-*"))) == 2
    page = client.get("/").text
    assert "Track Recovery" in page
    assert "recovery-preview" in page
    assert "recovery-create" in page
