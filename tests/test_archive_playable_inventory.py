import pytest

from oscar.archive_audit import audit_archive
from oscar.archive_publish import _assert_playable_inventory, PublishError


def test_failed_evidence_cannot_be_published_as_audio(tmp_path):
    (tmp_path / "track.flac").touch()
    evidence = tmp_path / "Verification" / "FailedAttempts"
    evidence.mkdir(parents=True)
    failed = evidence / "original.FLAC"
    failed.touch()
    (evidence / ".ndignore").touch()
    with pytest.raises(PublishError, match="Unexpected or missing playable audio"):
        _assert_playable_inventory(tmp_path, [{"filename": "track.flac"}])
    failed.unlink()
    (evidence / "original.zip").touch()
    _assert_playable_inventory(tmp_path, [{"filename": "track.flac"}])


def test_missing_track_is_rejected(tmp_path):
    with pytest.raises(PublishError, match="missing playable audio"):
        _assert_playable_inventory(tmp_path, [{"filename": "track.flac"}])


def test_nested_declared_track_is_allowed(tmp_path):
    (tmp_path / "CD1").mkdir()
    (tmp_path / "CD1" / "track.flac").touch()
    _assert_playable_inventory(tmp_path, [{"filename": "CD1/track.flac"}])


def test_audit_reports_playable_evidence_without_counting_album(tmp_path):
    folder = tmp_path / "Label" / "Album" / "Verification" / "FailedAttempts"
    folder.mkdir(parents=True)
    failed = folder / "failed.FLAC"
    failed.write_bytes(b"evidence")
    (folder / "old.zip").touch()
    (folder / ".ndignore").touch()
    result = audit_archive(tmp_path)
    assert result["releases_examined"] == 0
    assert result["active_flacs"] == 0
    assert result["status"] == "PASS_WITH_WARNINGS"
    assert result["playable_evidence"] == [failed.relative_to(tmp_path).as_posix()]
    assert failed.exists()
