from oscar.models import ArchiveManifest, AudioStatus, MetadataStatus


def test_empty_manifest_is_not_verified():
    manifest = ArchiveManifest()
    assert manifest.audio_status == AudioStatus.PENDING
    assert manifest.metadata_status == MetadataStatus.PENDING
    assert manifest.tracks == []


def test_metadata_and_audio_are_independent():
    manifest = ArchiveManifest(audio_status=AudioStatus.VERIFIED_CTDB)
    assert manifest.metadata_status != MetadataStatus.APPROVED
