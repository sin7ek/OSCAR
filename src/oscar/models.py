"""Separate technical audio verification and physical-release identification."""
from enum import Enum

from pydantic import BaseModel, Field


class AudioStatus(str, Enum):
    PENDING = "pending"
    VERIFIED_AR = "verified_accuraterip"
    VERIFIED_CTDB = "verified_ctdb"
    REPEATABLE_LOCAL = "repeatable_local"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class MetadataStatus(str, Enum):
    PENDING = "pending"
    REVIEW = "review_required"
    APPROVED = "approved"


class TrackEvidence(BaseModel):
    number: int = Field(ge=1)
    file: str
    flac_audio_md5: str | None = None
    sha256: str | None = None
    accuraterip_status: str | None = None
    ctdb_status: str | None = None


class ArchiveManifest(BaseModel):
    schema_version: int = 1
    disc_id: str | None = None
    physical_catalog_number: str | None = None
    musicbrainz_release_id: str | None = None
    audio_status: AudioStatus = AudioStatus.PENDING
    metadata_status: MetadataStatus = MetadataStatus.PENDING
    source: str = "own_physical_cd"
    tracks: list[TrackEvidence] = Field(default_factory=list)
