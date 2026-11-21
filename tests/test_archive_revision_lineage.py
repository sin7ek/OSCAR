"""Historical Verify must follow immutable successive single-CD publications."""
import json
from pathlib import Path

import pytest

from oscar import archive_metadata_scan as scan
from oscar import archive_revision as revision
from oscar import archive_revision_cleanup as cleanup
from oscar import archive_revision_verify as verifier

from test_archive_revision import fixture, _approve, FakeFlac


def _two_revisions(fixture, monkeypatch):
    _, old, _, lookup = fixture
    monkeypatch.setattr(verifier, "FLAC", FakeFlac)
    first_plan = _approve(fixture)
    first = revision.apply(str(old), first_plan["fingerprint"],
                           "APPLY_VERIFIED_ARCHIVE_REVISION")
    previously_current = Path(first["archive_path"])

    def genres(*args):
        result = lookup(*args)
        result["genres"] = ["Jazz", "Blues"]
        return result

    monkeypatch.setattr(scan, "lookup_release_medium", genres)
    proposals = scan.scan("additions", str(previously_current), lookup=genres)
    genre = next(p for p in proposals["pending"] if p["field"] == "GENRE")
    scan.decide(genre["fingerprint"], "accept", lookup=genres)
    plan = revision.preview(str(previously_current))
    assert [c["field"] for c in plan["accepted_changes"]] == ["GENRE"]
    return first, plan, previously_current


def test_verify_old_generation_after_second_approved_revision(fixture, monkeypatch):
    first, plan, path = _two_revisions(fixture, monkeypatch)
    first_receipt = verifier.verify(first["operation_id"])["verification_fingerprint"]
    assert first_receipt
    second = revision.apply(str(path), plan["fingerprint"],
                            "APPLY_VERIFIED_ARCHIVE_REVISION")
    historical = verifier.verify(first["operation_id"])
    latest = verifier.verify(second["operation_id"])
    assert historical["status"] == "verified"
    assert historical["historical_revision"] is True
    assert historical["verification_fingerprint"] is None
    assert historical["cleanup_eligible"] is False
    assert historical["verified_generation_path"] == second["original_retained_at"]
    assert historical["original_flacs_verified"] == 2
    assert latest["historical_revision"] is False
    assert latest["cleanup_eligible"] is True
    assert latest["verification_fingerprint"]

    monkeypatch.setenv("OSCAR_ENABLE_ARCHIVE_HISTORY_CLEANUP", "1")
    with pytest.raises(cleanup.ArchiveCleanupError, match="Historical revision"):
        cleanup.clean(first["operation_id"], first_receipt, cleanup.CONFIRM,
                      external_backup_confirmed=True)
    assert Path(first["original_retained_at"]).is_dir()
    assert Path(second["original_retained_at"]).is_dir()
    assert Path(second["archive_path"]).is_dir()


def test_verify_historical_generation_rejects_tampered_successor_backup(fixture, monkeypatch):
    first, plan, path = _two_revisions(fixture, monkeypatch)
    second = revision.apply(str(path), plan["fingerprint"],
                            "APPLY_VERIFIED_ARCHIVE_REVISION")
    (Path(second["original_retained_at"]) / "01 - Song.flac").write_bytes(b"tampered")
    with pytest.raises(verifier.ArchiveVerifyError, match="Revised FLAC SHA-256"):
        verifier.verify(first["operation_id"])


def test_verify_historical_generation_rejects_broken_journal_chain(fixture, monkeypatch):
    first, plan, path = _two_revisions(fixture, monkeypatch)
    second = revision.apply(str(path), plan["fingerprint"],
                            "APPLY_VERIFIED_ARCHIVE_REVISION")
    with revision._db() as db:
        db.execute(
            "UPDATE archive_revision_operations SET source_manifest_sha256=? "
            "WHERE operation_id=?",
            ("f" * 64, second["operation_id"]),
        )
    with pytest.raises(verifier.ArchiveVerifyError, match="Successor original manifest"):
        verifier.verify(first["operation_id"])
