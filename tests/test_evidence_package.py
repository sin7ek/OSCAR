import hashlib
import zipfile

import pytest

from oscar.evidence_package import package
from oscar.archive_audit import audit_archive


def test_package_preserves_original_bytes(tmp_path):
    source = tmp_path / "failed.flac"
    source.write_bytes(b"failed extraction evidence")
    target = tmp_path / "failed.zip"
    result = package(source, target)
    assert source.exists()
    assert result["original_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert result["zip_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    with zipfile.ZipFile(target) as archive:
        assert archive.read(source.name) == source.read_bytes()
    with pytest.raises(ValueError):
        package(source, target)


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
