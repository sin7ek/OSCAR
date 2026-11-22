"""OSCAR preview API: local drive settings only; no ripping or deletion."""
import os
import threading
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from oscar.settings import OscarSettings, discover_settings, inspect_drives, save_settings
from oscar.web import settings_page

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the metadata-only worker when explicitly enabled."""
    stop = threading.Event()
    worker = None
    if os.environ.get("OSCAR_ENABLE_METADATA_WORKER") == "1":
        from oscar.metadata_queue import worker_loop
        worker = threading.Thread(target=worker_loop, args=(stop,),
                                  daemon=True, name="oscar-metadata-retry")
        worker.start()
    try:
        yield
    finally:
        stop.set()
        if worker is not None:
            worker.join(timeout=2)


app = FastAPI(title="OSCAR", version="0.1.0-alpha", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "stage": "scaffold",
        "ripping": "disabled",
        "publishing": "disabled",
        "cleanup": "disabled",
    }


@app.get("/", include_in_schema=False)
def home():
    return settings_page()


# Branding is a presentation-only endpoint. Missing artwork must never prevent startup.
_BRAND_ASSETS = frozenset({"OSCAR-header.png", "favicon-16.png", "favicon-32.png",
                          "apple-touch-icon.png"})


@app.get("/brand/{filename}", include_in_schema=False)
def brand_asset(filename: str):
    if filename not in _BRAND_ASSETS:
        raise HTTPException(status_code=404, detail="Brand asset not found")
    asset = Path(__file__).resolve().parent / "assets" / filename
    if not asset.is_file():
        raise HTTPException(status_code=404, detail="Brand asset not found")
    return FileResponse(asset, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/settings", response_model=OscarSettings)
def get_settings():
    return discover_settings()


@app.put("/api/settings", response_model=OscarSettings)
def put_settings(settings: OscarSettings):
    # Only configuration is saved; no device command is executed.
    ids = [drive.stable_id for drive in settings.drives]
    if len(ids) != len(set(ids)):
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Duplicate drive stable IDs")
    save_settings(settings)
    return settings


@app.get("/api/drives")
def get_drives() -> list[dict[str, str | bool]]:
    return inspect_drives()


@app.get("/api/media")
def get_media_status():
    """Opt-in drive-status probe; never starts a rip or writes any media."""
    import os
    from fastapi import HTTPException

    if os.environ.get("OSCAR_ENABLE_MEDIA_PROBE") != "1":
        raise HTTPException(status_code=403, detail="Media probe disabled")
    from oscar.media import probe_enabled_drives

    return probe_enabled_drives()


@app.get("/api/toc")
def get_toc(stable_id: str):
    """Read standard TOC for one configured enabled disc drive."""
    import os
    from fastapi import HTTPException
    from oscar.toc import TocError, read_toc

    if os.environ.get("OSCAR_ENABLE_TOC_PROBE") != "1":
        raise HTTPException(status_code=403, detail="TOC reader disabled")
    settings = discover_settings()
    allowed = {d.stable_id for d in settings.drives if d.enabled}
    drives = {str(d["stable_id"]): d for d in inspect_drives()}
    drive = drives.get(stable_id)
    if stable_id not in allowed or drive is None:
        raise HTTPException(status_code=403, detail="Drive must be enabled and present")
    if not drive["identity_persistent"]:
        raise HTTPException(status_code=409, detail="Drive has no persistent identity")
    try:
        return read_toc(str(drive["device"]))
    except TocError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/releases")
def get_release_candidates(stable_id: str, catalog_number: str | None = None):
    """Lookup candidate releases; never auto-approve a physical edition."""
    from fastapi import HTTPException
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled, lookup_releases, assess_disc_candidates

    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    toc = get_toc(stable_id)
    try:
        return assess_disc_candidates(lookup_releases(toc["musicbrainz_disc_id"], toc["toc_string"]), catalog_number)
    except MusicBrainzError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc



@app.get("/api/release-search")
def search_release_by_physical_evidence(catalog_number: str | None = None,
                                        title: str | None = None):
    """MusicBrainz discovery by printed catalog number or title, not an approval."""
    from oscar.musicbrainz import (
        MusicBrainzError, lookup_enabled, search_release_candidates,
    )
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return search_release_candidates(catalog_number=catalog_number, title=title)
    except MusicBrainzError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/release-medium")
def get_release_medium(stable_id: str, release_id: str):
    """Display the medium on a candidate release associated with this Disc ID."""
    from fastapi import HTTPException
    from oscar.boxsets import lookup_release_medium
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled

    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    toc = get_toc(stable_id)
    try:
        return lookup_release_medium(
            release_id, toc["musicbrainz_disc_id"], len(toc["tracks"])
        )
    except MusicBrainzError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc



@app.get("/api/name-aliases")
def get_name_aliases(entity_type: str, entity_id: str):
    """One opt-in, read-only artist/work alias request (no disc operations)."""
    from fastapi import HTTPException
    from oscar.aliases import lookup_aliases
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled

    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        from oscar.alias_cache import get_alias
        return get_alias(entity_type, entity_id)
    except MusicBrainzError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/name-aliases/batch")
def get_name_aliases_batch(entities: list[dict]):
    """Enrich at most 12 artist/work names; deduplicated and persisted."""
    from fastapi import HTTPException
    from oscar.alias_cache import resolve_many
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled

    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return {"entities": resolve_many(entities)}
    except MusicBrainzError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/metadata-queue")
def get_metadata_queue_status():
    """Read-only counts of queued alias requests."""
    from oscar.metadata_queue import summary
    return {"worker_enabled": os.environ.get("OSCAR_ENABLE_METADATA_WORKER") == "1",
            **summary()}


# Experimental extraction endpoints require BOTH environment opt-in and a token.
# Endpoints never accept a filesystem destination from the browser.
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field


class RipRequest(BaseModel):
    stable_id: str = Field(min_length=1, max_length=256)
    confirmation: str
    selected_tracks: list[int] | None = Field(default=None, max_length=99)


def _rip_auth(token: str | None, request: Request | None = None):
    """Normal token mode, or explicitly opted-in trusted UI without a token.

    Trusted UI is intended ONLY behind an authenticated reverse proxy or
    tightly isolated local network. Same-origin + a non-simple request header
    reduce browser CSRF risk; they are not user authentication.
    """
    from urllib.parse import urlsplit
    from ipaddress import ip_address
    from oscar.ripping import RipError, authorize, enabled
    if not enabled():
        raise HTTPException(status_code=403, detail="Experimental ripping disabled")
    if token:
        try:
            authorize(token)
        except RipError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return
    if os.environ.get("OSCAR_TRUSTED_LOCAL_UI") != "1" or request is None:
        raise HTTPException(status_code=403, detail="Rip token required; trusted UI mode disabled")
    if request.headers.get("x-oscar-ui-action") != "confirmed":
        raise HTTPException(status_code=403, detail="Explicit OSCAR UI action header required")
    source = request.client.host if request.client else ""
    try:
        if not (ip_address(source).is_private or ip_address(source).is_loopback):
            raise ValueError("Untrusted source address")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Trusted UI requires local/private network access") from exc
    host = request.headers.get("host") or ""
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != host.lower():
            raise HTTPException(status_code=403, detail="Cross-origin action denied")
    elif request.method not in ("GET", "HEAD"):
        raise HTTPException(status_code=403, detail="Same-origin request required for actions")
    if request.headers.get("sec-fetch-site") not in (None, "same-origin", "none"):
        raise HTTPException(status_code=403, detail="Cross-site request denied")


@app.get("/api/ui/access")
def get_ui_access():
    """No credentials in responses; help the UI choose its auth workflow."""
    return {"trusted_local_ui": os.environ.get("OSCAR_TRUSTED_LOCAL_UI") == "1"}


@app.get("/api/rip/plan")
def get_rip_plan(stable_id: str, request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, plan
    _rip_auth(x_oscar_rip_token, request)
    try:
        return plan(stable_id)
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/rip/start")
def start_rip(request: RipRequest, http_request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, start
    _rip_auth(x_oscar_rip_token, http_request)
    expected = "RIP_DIAGNOSTIC_TRACKS" if request.selected_tracks is not None else "RIP_TO_STAGING"
    if request.confirmation != expected:
        raise HTTPException(status_code=422, detail="Explicit staging confirmation required")
    try:
        return start(request.stable_id, selected_tracks=request.selected_tracks)
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class DriveTrayRequest(BaseModel):
    stable_id: str = Field(min_length=1, max_length=256)
    action: str = Field(pattern=r"^(eject|close)$")
    confirmation: str


@app.post("/api/rip/tray")
def rip_tray_action(body: DriveTrayRequest, request: Request,
                    x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, control_tray
    _rip_auth(x_oscar_rip_token, request)
    if body.confirmation != "CONTROL_TRAY":
        raise HTTPException(status_code=422, detail="Explicit tray confirmation required")
    try:
        return control_tray(body.stable_id, body.action)
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class StopRipRequest(BaseModel):
    confirmation: str


@app.post("/api/rip/jobs/{job_id}/stop")
def rip_stop_job(job_id: str, body: StopRipRequest, request: Request,
                 x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, stop
    _rip_auth(x_oscar_rip_token, request)
    if body.confirmation != "STOP_RIP_KEEP_STAGING":
        raise HTTPException(status_code=422, detail="Explicit stop-and-retain-staging confirmation required")
    try:
        return stop(job_id)
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}")
def get_rip_status(job_id: str, request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, status
    _rip_auth(x_oscar_rip_token, request)
    try:
        return status(job_id)
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ArchiveNamePreviewRequest(BaseModel):
    profile: str = Field(pattern=r"^(album|compilation|classical)$")
    album_title: str = Field(min_length=1, max_length=300)
    release_year: str | None = Field(default=None, max_length=4)
    catalog_number: str | None = Field(default=None, max_length=100)
    album_artist: str | None = Field(default=None, max_length=200)
    composers: list[str] = Field(default_factory=list, max_length=30)
    disc_number: int = Field(default=1, ge=1, le=99)
    track_number: int = Field(default=1, ge=1, le=99)
    track_title: str = Field(default="Untitled", max_length=300)
    track_artist: str | None = Field(default=None, max_length=200)
    performer_suffix: str | None = Field(default=None, max_length=100)


@app.post("/api/archive/name-preview")
def get_archive_name_preview(request: ArchiveNamePreviewRequest):
    """Preview only: does not touch files, devices, staging or Archive."""
    from oscar.archive_naming import archive_preview
    try:
        return archive_preview(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/drive-offset/lookup")
def drive_offset_lookup(stable_id: str):
    """Read-only external drive-model suggestion; never change saved offset."""
    from oscar.drive_offset import OffsetError, lookup
    drives = {str(d["stable_id"]): d for d in inspect_drives()}
    drive = drives.get(stable_id)
    if drive is None or not drive.get("identity_persistent"):
        raise HTTPException(status_code=404, detail="Persistent optical drive not found")
    # Vendor names differ across AccurateRip; query with specific model token.
    model = str(drive["label"]).split()[-1]
    try:
        return lookup(model)
    except OffsetError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/drive-offset/from-disc")
def drive_offset_from_disc(request: RipRequest, http_request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """User-triggered reference-disc calibration, no rip and no settings write."""
    from oscar.drive_offset import OffsetError, disc_calibration
    from oscar.ripping import selected_drive, _ACTIVE, _LOCK, RipError
    _rip_auth(x_oscar_rip_token, http_request)
    if request.confirmation != "CALIBRATE_OFFSET":
        raise HTTPException(status_code=422, detail="Explicit calibration confirmation required")
    try:
        device, _ = selected_drive_for_calibration(request.stable_id)
        with _LOCK:
            if request.stable_id in _ACTIVE:
                raise OffsetError("Cannot calibrate while this drive is ripping")
            _ACTIVE.add(request.stable_id)
        try:
            return disc_calibration(device)
        finally:
            with _LOCK:
                _ACTIVE.discard(request.stable_id)
    except (OffsetError, RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def selected_drive_for_calibration(stable_id: str):
    """Resolve a known enabled drive without requiring an offset yet."""
    import re
    import stat
    from oscar.ripping import RipError
    allowed = {d.stable_id for d in discover_settings().drives if d.enabled}
    drive = {str(d["stable_id"]): d for d in inspect_drives()}.get(stable_id)
    if stable_id not in allowed or not drive or not drive.get("identity_persistent"):
        raise RipError("Drive must be enabled and persistently identified")
    device = str(drive["device"])
    if not re.fullmatch(r"/dev/sr\d+", device) or not stat.S_ISBLK(os.stat(device).st_mode):
        raise RipError("Optical drive not accessible")
    return device, None


@app.post("/api/rip/jobs/{job_id}/verification")
def start_rip_verification(job_id: str, request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Explicit post-rip verification; does not use drive or modify FLAC/CUE."""
    from oscar import verification
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return verification.start(job_id)
    except (RipError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}/verification")
def get_rip_verification(job_id: str, request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Read saved verification evidence, or current in-process progress."""
    from oscar import verification
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return verification.report(job_id)
    except (RipError, OSError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class TrackRecoveryRequest(BaseModel):
    original_job_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    diagnostic_job_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    replacement_tracks: list[int] = Field(min_length=1, max_length=99)


class TrackRecoveryStartRequest(TrackRecoveryRequest):
    confirmation: str


@app.post("/api/track-recovery/preview")
def track_recovery_preview(body: TrackRecoveryRequest, request: Request,
                           x_oscar_rip_token: str | None = Header(default=None)):
    """Validate source hashes, cyanrip evidence, physical TOCs and CUE read-only."""
    from oscar import track_recovery
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return track_recovery.preview(
            body.original_job_id, body.diagnostic_job_id, body.replacement_tracks)
    except (track_recovery.RecoveryError, RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/track-recovery/start")
def track_recovery_start(body: TrackRecoveryStartRequest, request: Request,
                         x_oscar_rip_token: str | None = Header(default=None)):
    """Create a fresh staging copy; no source or archive overwrites."""
    from oscar import track_recovery
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return track_recovery.start(
            body.original_job_id, body.diagnostic_job_id,
            body.replacement_tracks, body.confirmation)
    except (track_recovery.RecoveryError, RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/track-recovery/jobs/{job_id}")
def track_recovery_status(job_id: str, request: Request,
                          x_oscar_rip_token: str | None = Header(default=None)):
    from oscar import track_recovery
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return track_recovery.status(job_id)
    except (track_recovery.RecoveryError, RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class DeferReleaseReviewRequest(BaseModel):
    reason: str
    title: str = Field(default="", max_length=200)
    catalog_number: str = Field(default="", max_length=100)
    notes: str = Field(default="", max_length=1000)


@app.post("/api/rip/jobs/{job_id}/release-review/defer")
def defer_release_review(job_id: str, body: DeferReleaseReviewRequest,
                         request: Request,
                         x_oscar_rip_token: str | None = Header(default=None)):
    """Store a review task, never tag or publish the rip."""
    from oscar.release_review_queue import RecoveryError, defer
    _rip_auth(x_oscar_rip_token, request)
    try:
        return defer(job_id, reason=body.reason, title=body.title,
                     catalog_number=body.catalog_number, notes=body.notes)
    except (RecoveryError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/release-reviews")
def get_release_review_backlog(request: Request,
                               x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.release_review_queue import pending
    _rip_auth(x_oscar_rip_token, request)
    return pending()


@app.post("/api/rip/jobs/{job_id}/release-review/resolve")
def resolve_release_review(job_id: str, request: Request,
                           x_oscar_rip_token: str | None = Header(default=None)):
    """Close only the review task; does not change the rip or metadata."""
    from oscar.release_review_queue import RecoveryError, resolve
    _rip_auth(x_oscar_rip_token, request)
    try:
        return resolve(job_id)
    except (RecoveryError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class PhysicalReleaseCompareRequest(BaseModel):
    release_id: str = Field(min_length=36, max_length=36)
    catalog_number: str = Field(min_length=1, max_length=100)
    barcode: str | None = Field(default=None, max_length=14)


@app.post("/api/rip/jobs/{job_id}/physical-release/compare")
def compare_physical_release(job_id: str, body: PhysicalReleaseCompareRequest,
                             http_request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Read-only compare user-observed physical catalog/barcode to MB release data."""
    from oscar.physical_release import PhysicalReleaseError, compare
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, http_request)
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return compare(job_id, body.release_id,
                       catalog_number=body.catalog_number, barcode=body.barcode)
    except (PhysicalReleaseError, MusicBrainzError, RipError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class MetadataPreviewRequest(BaseModel):
    release_id: str = Field(min_length=36, max_length=36)


class MetadataCopyRequest(BaseModel):
    release_id: str = Field(min_length=36, max_length=36)
    fingerprint: str = Field(min_length=64, max_length=64)
    confirmation: str


@app.post("/api/rip/jobs/{job_id}/metadata/preview")
def preview_rip_metadata(job_id: str, request: MetadataPreviewRequest,
                         http_request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Read-only exact-release preview; user still must review physical edition."""
    from oscar.metadata_staging import MetadataError, preview
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, http_request)
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return preview(job_id, request.release_id)
    except (MetadataError, MusicBrainzError, RipError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class MetadataReprocessRequest(BaseModel):
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    confirmation: str


@app.post("/api/go/jobs/{job_id}/musicbrainz/metadata-refresh")
def musicbrainz_metadata_refresh(job_id: str, request: Request,
                                x_oscar_rip_token: str | None = Header(default=None)):
    """Compare new MusicBrainz metadata with an existing verified tagged copy."""
    from oscar.metadata_reprocess import ReprocessError, refresh_preview
    from oscar.metadata_staging import MetadataError
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled
    from oscar.ripping import RipError
    from oscar.workflow_ledger import WorkflowError
    _rip_auth(x_oscar_rip_token, request)
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return refresh_preview(job_id)
    except (ReprocessError, MetadataError, MusicBrainzError, RipError,
            WorkflowError, ValueError, OSError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/go/jobs/{job_id}/musicbrainz/reprocess-copy")
def musicbrainz_reprocess_copy(job_id: str, body: MetadataReprocessRequest,
                              request: Request,
                              x_oscar_rip_token: str | None = Header(default=None)):
    """Explicitly start a separate tagged staging copy; never archive or replace."""
    from oscar.metadata_reprocess import ReprocessError, create_new_staging_copy
    from oscar.metadata_staging import MetadataError
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled
    from oscar.ripping import RipError
    from oscar.workflow_ledger import WorkflowError
    _rip_auth(x_oscar_rip_token, request)
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return create_new_staging_copy(job_id, body.fingerprint, body.confirmation)
    except (ReprocessError, MetadataError, MusicBrainzError, RipError,
            WorkflowError, ValueError, OSError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class AdoptRefreshedMetadataRequest(BaseModel):
    copy_id: str = Field(min_length=32, max_length=32, pattern=r"^[a-f0-9]{32}$")
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    confirmation: str


@app.post("/api/go/jobs/{job_id}/musicbrainz/adopt-refreshed-copy")
def go_adopt_refreshed_metadata(job_id: str, body: AdoptRefreshedMetadataRequest,
                               request: Request,
                               x_oscar_rip_token: str | None = Header(default=None)):
    """Explicitly select a verified refreshed copy before first Go publish."""
    from oscar.metadata_reprocess import ReprocessError, adopt_new_staging_copy_for_go
    from oscar.metadata_staging import MetadataError
    from oscar.workflow_ledger import WorkflowError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return adopt_new_staging_copy_for_go(
            job_id, body.copy_id, body.fingerprint, body.confirmation)
    except (ReprocessError, MetadataError, WorkflowError, RipError,
            OSError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/rip/jobs/{job_id}/metadata/copy")
def create_tagged_staging_copy(job_id: str, request: MetadataCopyRequest,
                               http_request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Explicitly reviewed copy-on-write Vorbis tagging: no archive operations."""
    from oscar.metadata_staging import MetadataError, start_copy
    from oscar.musicbrainz import lookup_enabled
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, http_request)
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return start_copy(job_id, request.release_id, request.fingerprint, request.confirmation)
    except (MetadataError, RipError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}/metadata/copies/{copy_id}")
def get_tagged_staging_copy(job_id: str, copy_id: str,
                            request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.metadata_staging import MetadataError, copy_status
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return copy_status(job_id, copy_id)
    except (MetadataError, RipError, ValueError, OSError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}/metadata/copies/{copy_id}/inspect")
def inspect_tagged_staging_copy(job_id: str, copy_id: str, request: Request,
                                 x_oscar_rip_token: str | None = Header(default=None)):
    """Read real FLAC tags from a finished tagged copy; no MusicBrainz call."""
    from oscar.metadata_staging import MetadataError, inspect_copy
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return inspect_copy(job_id, copy_id)
    except (MetadataError, RipError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ClassicalSection(BaseModel):
    start: int = Field(ge=1, le=150)
    end: int = Field(ge=1, le=150)
    name: str = Field(min_length=1, max_length=120)


class ClassicalPreviewRequest(BaseModel):
    sections: list[ClassicalSection] = Field(default_factory=list, max_length=30)
    movements: dict[str, str] = Field(default_factory=dict)


class ClassicalCopyRequest(BaseModel):
    preview: dict
    confirmation: str


@app.post("/api/rip/jobs/{job_id}/metadata/copies/{copy_id}/classical-v2/preview")
def preview_classical_v2(job_id: str, copy_id: str, body: ClassicalPreviewRequest,
                         http_request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Review CD section labels separately from MusicBrainz compositions."""
    from oscar.classical_v2 import ClassicalError, create_preview
    from oscar.metadata_staging import MetadataError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, http_request)
    try:
        return create_preview(job_id, copy_id, [x.model_dump() for x in body.sections],
                              body.movements)
    except (ClassicalError, MetadataError, RipError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/rip/jobs/{job_id}/metadata/classical-v2/copy")
def create_classical_v2_copy(job_id: str, body: ClassicalCopyRequest,
                             http_request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Create a new separately tagged copy only after explicit review."""
    from oscar.classical_v2 import ClassicalError, start_copy
    from oscar.metadata_staging import MetadataError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, http_request)
    if body.preview.get("job_id") != job_id:
        raise HTTPException(status_code=422, detail="Preview job does not match requested rip")
    try:
        return start_copy(body.preview, body.confirmation)
    except (ClassicalError, MetadataError, RipError, ValueError, OSError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}/metadata/classical-v2/copies/{copy_id}")
def classical_v2_copy_status(job_id: str, copy_id: str, request: Request,
                             x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.classical_v2 import ClassicalError, copy_status
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return copy_status(job_id, copy_id)
    except (ClassicalError, RipError, OSError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}/metadata/classical-v2/copies/{copy_id}/inspect")
def inspect_classical_v2_copy(job_id: str, copy_id: str, request: Request,
                              x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.classical_v2 import ClassicalError, inspect_copy
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return inspect_copy(job_id, copy_id)
    except (ClassicalError, RipError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}/archive-review/{copy_id}")
def get_archive_review(job_id: str, copy_id: str, request: Request,
                       kind: str = "classical_v2", profile: str = "auto",
                       x_oscar_rip_token: str | None = Header(default=None)):
    """Non-destructive consistency, cover candidate and index-preserving CUE preview."""
    from oscar.archive_review import ReviewError, review
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return review(job_id, copy_id, kind, profile=profile)
    except (ReviewError, RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc



class ArchivePublishPreviewRequest(BaseModel):
    copy_id: str = Field(min_length=32, max_length=32)
    kind: str = "original_tags"
    profile: str = "auto"
    include_cover: bool = False


class ArchivePublishRequest(ArchivePublishPreviewRequest):
    fingerprint: str = Field(min_length=64, max_length=64)
    confirmation: str
    acknowledge_metadata_observations: bool = False
    approve_cover: bool = False


def _archive_publish_enabled():
    if os.environ.get("OSCAR_ENABLE_ARCHIVE_PUBLISH") != "1":
        raise HTTPException(status_code=403, detail="Archive publication disabled; configure dedicated archive mount and opt-in flag")


@app.post("/api/rip/jobs/{job_id}/archive-publish/preview")
def preview_archive_publish(job_id: str, body: ArchivePublishPreviewRequest,
                            request: Request,
                            x_oscar_rip_token: str | None = Header(default=None)):
    """Prepare archive publication plan without writing any files."""
    from oscar.archive_publish import PublishError, prepare
    from oscar.archive_review import ReviewError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    _archive_publish_enabled()
    try:
        return prepare(job_id, body.copy_id, body.kind, body.profile,
                       include_cover=body.include_cover)
    except (PublishError, ReviewError, RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/rip/jobs/{job_id}/archive-publish/start")
def start_archive_publish(job_id: str, body: ArchivePublishRequest,
                          request: Request,
                          x_oscar_rip_token: str | None = Header(default=None)):
    """Explicit, fingerprinted archive-copy operation (no source modifications)."""
    from oscar.archive_publish import PublishError, start
    from oscar.archive_review import ReviewError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    _archive_publish_enabled()
    try:
        return start(job_id, body.copy_id, body.kind, body.profile,
                     body.fingerprint, body.confirmation,
                     acknowledge_observations=body.acknowledge_metadata_observations,
                     include_cover=body.include_cover, approve_cover=body.approve_cover)
    except (PublishError, ReviewError, RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}/archive-publish/{publish_id}")
def get_archive_publish_status(job_id: str, publish_id: str, request: Request,
                               x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_publish import PublishError, status
    _rip_auth(x_oscar_rip_token, request)
    _archive_publish_enabled()
    try:
        return status(job_id, publish_id)
    except PublishError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/rip/dashboard")
def rip_drives_dashboard(request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Observe active/idle optical drives; read-only and never starts a rip."""
    from oscar.ripping import dashboard, RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return dashboard()
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ArchiveMetadataScanRequest(BaseModel):
    mode: str = Field(pattern=r"^(additions|changes)$")
    archive_path: str = Field(min_length=2, max_length=1500)


class ArchiveMetadataDecisionRequest(BaseModel):
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    choice: str = Field(pattern=r"^(accept|ignore)$")


class ArchiveBulkScanRequest(BaseModel):
    mode: str = Field(pattern=r"^(additions|changes)$")


class ArchiveRevisionPreviewRequest(BaseModel):
    archive_path: str = Field(min_length=2, max_length=1500)


class ArchiveRevisionApplyRequest(ArchiveRevisionPreviewRequest):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmation: str


@app.post("/api/collection/archive-revisions/preview")
def archive_revision_preview(body: ArchiveRevisionPreviewRequest, request: Request,
                             x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision import RevisionError, preview
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    from oscar.musicbrainz import MusicBrainzError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return preview(body.archive_path)
    except (RevisionError, ScanError, CatalogError, MusicBrainzError,
            ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/collection/archive-revisions/apply")
def archive_revision_apply(body: ArchiveRevisionApplyRequest, request: Request,
                           x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision import RevisionError, start
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    from oscar.musicbrainz import MusicBrainzError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return start(body.archive_path, body.fingerprint, body.confirmation)
    except (RevisionError, ScanError, CatalogError, MusicBrainzError,
            ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/archive-revisions/workers/{task_id}")
def archive_revision_worker(task_id: str, request: Request,
                            x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision import RevisionError, task_status
    _rip_auth(x_oscar_rip_token, request)
    try:
        return task_status(task_id)
    except RevisionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/collection/archive-revisions/operations")
def archive_revision_operations(request: Request,
                                x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision import operations
    _rip_auth(x_oscar_rip_token, request)
    return operations()


class ArchiveBoxsetPreviewRequest(BaseModel):
    release_id: str = Field(pattern=r"^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$")
    field: str = Field(default="LABEL", pattern=r"^(LABEL|GENRE)$")


@app.post("/api/collection/archive-revisions/boxset-preview")
def archive_revision_boxset_preview(body: ArchiveBoxsetPreviewRequest, request: Request,
                                    x_oscar_rip_token: str | None = Header(default=None)):
    """Read-only release-wide review; never applies partial boxset revisions."""
    from oscar.archive_revision_boxset import BoxsetReviewError, preview
    from oscar.archive_revision import RevisionError
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    from oscar.musicbrainz import MusicBrainzError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return preview(body.release_id, field=body.field)
    except (BoxsetReviewError, RevisionError, ScanError, CatalogError,
            MusicBrainzError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ArchiveBoxsetApplyRequest(ArchiveBoxsetPreviewRequest):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmation: str


@app.post("/api/collection/archive-revisions/boxset-apply")
def archive_revision_boxset_apply(body: ArchiveBoxsetApplyRequest, request: Request,
                                  x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision_boxset_apply import BoxsetApplyError, start
    from oscar.archive_revision_boxset import BoxsetReviewError
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    from oscar.musicbrainz import MusicBrainzError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return start(body.release_id, body.fingerprint, body.confirmation, field=body.field)
    except (BoxsetApplyError, BoxsetReviewError, ScanError, CatalogError,
            MusicBrainzError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/archive-revisions/boxset-workers/{task_id}")
def archive_revision_boxset_worker(task_id: str, request: Request,
                                   x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision_boxset_apply import BoxsetApplyError, task_status
    _rip_auth(x_oscar_rip_token, request)
    try:
        return task_status(task_id)
    except BoxsetApplyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ArchiveBoxsetReconcileRequest(BaseModel):
    operation_id: str = Field(pattern=r"^[a-f0-9]{32}$")


@app.post("/api/collection/archive-revisions/boxset-reconcile")
def archive_revision_boxset_reconcile(body: ArchiveBoxsetReconcileRequest, request: Request,
                                      x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision_boxset_apply import BoxsetApplyError, reconcile
    _rip_auth(x_oscar_rip_token, request)
    try:
        return reconcile(body.operation_id)
    except (BoxsetApplyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/archive-revisions/boxset-operations")
def archive_revision_boxset_operations(request: Request,
                                        x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision_boxset_apply import operations
    _rip_auth(x_oscar_rip_token, request)
    return operations()


@app.post("/api/collection/archive-revisions/boxset-verify")
def archive_revision_boxset_verify(body: ArchiveBoxsetReconcileRequest, request: Request,
                                   x_oscar_rip_token: str | None = Header(default=None)):
    """Read-only integrity audit of an already completed group migration."""
    from oscar.archive_revision_boxset_verify import verify
    from oscar.archive_revision_boxset_apply import BoxsetApplyError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return verify(body.operation_id)
    except (BoxsetApplyError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class GenreEvidencePreviewRequest(BaseModel):
    archive_path: str = Field(min_length=5, max_length=2048)
    discogs_release_id: int | None = Field(default=None, ge=1, le=99999999)
    workflow: str = Field(default="semi_automatic",
                          pattern=r"^(best_guess|semi_automatic|secure)$")


@app.post("/api/collection/genre-evidence/preview")
def preview_archive_genre_evidence(body: GenreEvidencePreviewRequest, request: Request,
                                   x_oscar_rip_token: str | None = Header(default=None)):
    """Read-only report; no metadata approval, no SOURCES or FLAC writes."""
    from oscar.genre_evidence import GenreEvidenceError, report_for_archive
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled
    from oscar.discogs_readonly import DiscogsError
    _rip_auth(x_oscar_rip_token, request)
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return report_for_archive(body.archive_path,
                                  discogs_release_id=body.discogs_release_id,
                                  workflow=body.workflow)
    except (GenreEvidenceError, ScanError, CatalogError,
            MusicBrainzError, DiscogsError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ArchiveRevisionVerifyRequest(BaseModel):
    operation_id: str = Field(pattern=r"^[a-f0-9]{32}$")


@app.post("/api/collection/archive-revisions/verify")
def archive_revision_verify(body: ArchiveRevisionVerifyRequest, request: Request,
                            x_oscar_rip_token: str | None = Header(default=None)):
    """Independent read-only integrity check of both archive generations and DB."""
    from oscar.archive_revision_verify import ArchiveVerifyError, verify
    from oscar.archive_revision import RevisionError
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return verify(body.operation_id)
    except (ArchiveVerifyError, RevisionError, ScanError, CatalogError,
            ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ArchiveRevisionCleanRequest(BaseModel):
    operation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    verification_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmation: str
    external_backup_confirmed: bool = False


@app.post("/api/collection/archive-revisions/clean")
def archive_revision_clean(body: ArchiveRevisionCleanRequest, request: Request,
                           x_oscar_rip_token: str | None = Header(default=None)):
    """Irreversible per-operation cleanup, separately opted in and reverified."""
    from oscar.archive_revision_cleanup import ArchiveCleanupError, clean
    from oscar.archive_revision_verify import ArchiveVerifyError
    from oscar.archive_revision import RevisionError
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return clean(
            body.operation_id, body.verification_fingerprint, body.confirmation,
            external_backup_confirmed=body.external_backup_confirmed,
        )
    except (ArchiveCleanupError, ArchiveVerifyError, RevisionError, ScanError,
            CatalogError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ArchiveRevisionReconcileRequest(BaseModel):
    operation_id: str = Field(pattern=r"^[a-f0-9]{32}$")


@app.post("/api/collection/archive-revisions/reconcile")
def archive_revision_reconcile(body: ArchiveRevisionReconcileRequest, request: Request,
                               x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_revision import RevisionError, reconcile
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return reconcile(body.operation_id)
    except (RevisionError, ScanError, CatalogError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/collection/archive-metadata/scan-all")
def archive_metadata_scan_all(body: ArchiveBulkScanRequest, request: Request,
                              x_oscar_rip_token: str | None = Header(default=None)):
    """Start a background scan over all Collection-indexed published archive leaves."""
    from oscar.archive_metadata_bulk import start
    from oscar.archive_metadata_scan import ScanError
    from oscar.collection_catalog import CatalogError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return start(body.mode)
    except (ScanError, CatalogError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/archive-metadata/scan-all/status")
def archive_metadata_scan_current(request: Request,
                                 x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_metadata_bulk import current
    _rip_auth(x_oscar_rip_token, request)
    return current()


@app.get("/api/collection/archive-metadata/scan-all/{scan_id}")
def archive_metadata_scan_status(scan_id: str, request: Request,
                                 x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_metadata_bulk import status
    from oscar.archive_metadata_scan import ScanError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return status(scan_id)
    except ScanError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/collection/archive-metadata/scan")
def scan_archive_metadata(body: ArchiveMetadataScanRequest, request: Request,
                          x_oscar_rip_token: str | None = Header(default=None)):
    """Scan one published archive for externally proposed changes, no FLAC writes."""
    from oscar.archive_metadata_scan import ScanError, scan
    from oscar.musicbrainz import MusicBrainzError
    from oscar.collection_catalog import CatalogError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return scan(body.mode, body.archive_path)
    except (ScanError, CatalogError, MusicBrainzError, ValueError, OSError,
            KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/archive-metadata/proposals")
def archive_metadata_proposals(request: Request, include_decided: bool = False,
                               x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_metadata_scan import list_proposals
    _rip_auth(x_oscar_rip_token, request)
    return list_proposals(include_decided=include_decided)


@app.post("/api/collection/archive-metadata/decision")
def archive_metadata_decision(body: ArchiveMetadataDecisionRequest, request: Request,
                              x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_metadata_scan import ScanError, decide
    from oscar.musicbrainz import MusicBrainzError
    from oscar.collection_catalog import CatalogError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return decide(body.fingerprint, body.choice)
    except (ScanError, CatalogError, MusicBrainzError, ValueError, OSError,
            KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class ArchiveMetadataReopenRequest(BaseModel):
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


@app.post("/api/collection/archive-metadata/reopen")
def archive_metadata_reopen(body: ArchiveMetadataReopenRequest, request: Request,
                            x_oscar_rip_token: str | None = Header(default=None)):
    """Undo an Ignore/Accept decision without deleting its historical event."""
    from oscar.archive_metadata_scan import ScanError, reopen_decision
    from oscar.musicbrainz import MusicBrainzError
    from oscar.collection_catalog import CatalogError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return reopen_decision(body.fingerprint)
    except (ScanError, CatalogError, MusicBrainzError, ValueError, OSError,
            KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/archive-metadata/history")
def archive_metadata_history(request: Request,
                             x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.archive_metadata_scan import decision_history
    _rip_auth(x_oscar_rip_token, request)
    return decision_history()


# Local collection inventory is separate from Discogs and never writes to /archive.
@app.get("/api/collection")
def collection_list(request: Request, search: str = "", sort_by: str = "artist",
                    descending: bool = False, limit: int = 250, offset: int = 0,
                    section: str = "",
                    x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.collection_catalog import CatalogError, list_items
    _rip_auth(x_oscar_rip_token, request)
    try:
        return list_items(search=search, sort_by=sort_by, descending=descending,
                          limit=limit, offset=offset, section=section)
    except (CatalogError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/collection/import-archives")
def collection_import_archives(request: Request,
                               x_oscar_rip_token: str | None = Header(default=None)):
    """Explicitly scan published OSCAR archive manifests; never modify archives."""
    from oscar.collection_catalog import CatalogError, import_published
    _rip_auth(x_oscar_rip_token, request)
    try:
        return import_published()
    except (CatalogError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/export")
def collection_export(request: Request, format: str = "ods",
                      x_oscar_rip_token: str | None = Header(default=None)):
    from fastapi.responses import Response
    from oscar.collection_catalog import CatalogError, export_csv, export_ods, export_xlsx
    _rip_auth(x_oscar_rip_token, request)
    if format not in {"ods", "csv", "xlsx"}:
        raise HTTPException(status_code=422, detail="Export must be ods, xlsx or csv")
    try:
        body = export_ods() if format == "ods" else export_xlsx() if format == "xlsx" else export_csv()
    except (CatalogError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(content=body,
                    media_type=("application/vnd.oasis.opendocument.spreadsheet"
                                if format == "ods" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == "xlsx" else "text/csv; charset=utf-8"),
                    headers={"Content-Disposition": f'attachment; filename="oscar-collection.{format}"',
                             "Cache-Control": "no-store"})


@app.get("/api/discogs/account")
def discogs_account(request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Opt-in live token check and folder names; no Discogs writes or caching."""
    from oscar.discogs_readonly import DiscogsError, account_summary
    _rip_auth(x_oscar_rip_token, request)
    try:
        return account_summary()
    except DiscogsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/collection/index-tracks")
def collection_index_tracks(request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Explicit read-only-from-archive indexed copy of per-track Vorbis metadata."""
    from oscar.collection_tracks import TrackIndexError, index_published_tracks
    _rip_auth(x_oscar_rip_token, request)
    try:
        return index_published_tracks()
    except (TrackIndexError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/collection/tracks")
def collection_find_tracks(request: Request, search: str = "", role: str = "",
                           limit: int = 150, offset: int = 0,
                           x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.collection_tracks import TrackIndexError, find_tracks
    _rip_auth(x_oscar_rip_token, request)
    try:
        return find_tracks(search=search, role=role, limit=limit, offset=offset)
    except (TrackIndexError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/collection/enrich-labels")
def collection_enrich_labels(request: Request,
                             x_oscar_rip_token: str | None = Header(default=None)):
    """Opt-in MusicBrainz-only lookup for missing local label fields."""
    from oscar.collection_labels import LabelEnrichmentError, backfill_labels
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled
    _rip_auth(x_oscar_rip_token, request)
    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    try:
        return backfill_labels()
    except (LabelEnrichmentError, MusicBrainzError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/collection/reconcile-approved-labels")
def collection_reconcile_approved_labels(request: Request,
                                         x_oscar_rip_token: str | None = Header(default=None)):
    """Explicit safe repair for sourced labels from previously completed revisions."""
    from oscar.collection_labels import LabelEnrichmentError, reconcile_applied_archive_labels
    from oscar.archive_metadata_scan import ScanError
    from oscar.archive_revision import RevisionError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return reconcile_applied_archive_labels()
    except (LabelEnrichmentError, ScanError, RevisionError, ValueError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class WorkflowReviewAction(BaseModel):
    action: str = Field(pattern=r"^(defer|resume)$")


@app.post("/api/workflow/jobs/{job_id}/register")
def workflow_register(job_id: str, request: Request,
                      x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.workflow_ledger import WorkflowError, register
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token,request)
    try:
        return register(job_id)
    except (WorkflowError, RipError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc


@app.post("/api/workflow/jobs/{job_id}/refresh")
def workflow_refresh(job_id: str, request: Request,
                     x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.workflow_ledger import WorkflowError, refresh
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token,request)
    try:
        return refresh(job_id)
    except (WorkflowError, RipError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc


@app.post("/api/workflow/jobs/{job_id}/review")
def workflow_review(job_id: str, body: WorkflowReviewAction, request: Request,
                    x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.workflow_ledger import WorkflowError, review_action
    _rip_auth(x_oscar_rip_token,request)
    try:
        return review_action(job_id,body.action)
    except (WorkflowError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc


@app.get("/api/workflow/jobs")
def workflow_jobs(request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.workflow_ledger import WorkflowError, list_jobs
    _rip_auth(x_oscar_rip_token,request)
    try:
        return list_jobs()
    except (WorkflowError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc


class GoSemiReleaseApproval(BaseModel):
    release_id: str = Field(min_length=36, max_length=36)
    confirmation: str


@app.post("/api/go/jobs/{job_id}/accept-release")
def go_accept_semi_release(job_id: str, body: GoSemiReleaseApproval,
                           request: Request,
                           x_oscar_rip_token: str | None = Header(default=None)):
    """Operator accepts exactly one previously discovered inferred release.

    This endpoint does NOT approve a physical pressing, generate tags or
    publish an archive. Only tracked Semi Automatic jobs can use it.
    """
    from oscar.workflow_ledger import WorkflowError, accept_semi_release
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return accept_semi_release(job_id, body.release_id, body.confirmation)
    except (WorkflowError, RipError, OSError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class GoArchivePublishApproval(BaseModel):
    fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    confirmation: str
    acknowledge_metadata_observations: bool = False


@app.post("/api/go/jobs/{job_id}/archive/preview")
def go_archive_preview(job_id: str, request: Request,
                       x_oscar_rip_token: str | None = Header(default=None)):
    """Read-only classical/track/CUE review of precisely this verified Go copy."""
    from oscar.go_controller import GoError, archive_preview
    from oscar.workflow_ledger import WorkflowError
    from oscar.archive_review import ReviewError
    from oscar.archive_publish import PublishError
    from oscar.metadata_staging import MetadataError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    _archive_publish_enabled()
    try:
        return archive_preview(job_id)
    except (GoError, WorkflowError, ReviewError, PublishError, MetadataError,
            RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/go/jobs/{job_id}/archive/publish")
def go_archive_publish(job_id: str, body: GoArchivePublishApproval, request: Request,
                       x_oscar_rip_token: str | None = Header(default=None)):
    """Only after explicit operator confirmation of a fresh exact Go preview."""
    from oscar.go_controller import GoError, archive_publish_start
    from oscar.workflow_ledger import WorkflowError
    from oscar.archive_review import ReviewError
    from oscar.archive_publish import PublishError
    from oscar.metadata_staging import MetadataError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    _archive_publish_enabled()
    try:
        return archive_publish_start(
            job_id, body.fingerprint, body.confirmation,
            acknowledge_observations=body.acknowledge_metadata_observations)
    except (GoError, WorkflowError, ReviewError, PublishError, MetadataError,
            RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/go/jobs/{job_id}/musicbrainz/refresh-match")
def musicbrainz_refresh_accepted_match(job_id: str, request: Request,
                                      x_oscar_rip_token: str | None = Header(default=None)):
    """Fresh read-only MusicBrainz lookup; never alter historical provenance."""
    from oscar.match_refresh import refresh_accepted_match
    from oscar.musicbrainz import MusicBrainzError
    from oscar.ripping import RipError
    from oscar.workflow_ledger import WorkflowError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return refresh_accepted_match(job_id)
    except (MusicBrainzError, WorkflowError, RipError, ValueError,
            OSError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/go/jobs/{job_id}/musicbrainz/discid-attach")
def musicbrainz_discid_attach_link(job_id: str, request: Request,
                                  x_oscar_rip_token: str | None = Header(default=None)):
    """Prepare an external human-confirmed MusicBrainz TOC submission link only.

    Never submit a MusicBrainz edit or infer physical edition verification.
    A saved, verified, explicitly accepted single-CD Semi Automatic job is required.
    """
    import json
    import re
    import urllib.parse
    from oscar import verification, workflow_ledger
    from oscar.boxsets import lookup_release_medium
    from oscar.musicbrainz import MusicBrainzError
    from oscar.ripping import RipError
    from oscar.workflow_ledger import WorkflowError

    _rip_auth(x_oscar_rip_token, request)
    try:
        workflow = workflow_ledger.refresh(job_id)
        if (workflow.get("identification_mode") != "semi_automatic"
                or not workflow.get("accepted_release_id")
                or workflow.get("release_match_status") != "INFERRED_OPERATOR_ACCEPTED"):
            raise ValueError("An explicitly accepted Semi Automatic release is required")
        folder = verification._safe_job(job_id)
        state = verification._load_job(folder, job_id)
        report = verification.report(job_id)
        if (report.get("status") != "checks_passed"
                or report.get("job_id") != job_id
                or not all(t.get("checks_passed") for t in report.get("tracks", []))):
            raise ValueError("A fully verified rip is required before Disc ID submission")
        planfile = folder / "plan.json"
        if planfile.is_symlink() or not planfile.is_file():
            raise ValueError("Unsafe or missing saved rip plan")
        plan = json.loads(planfile.read_text(encoding="utf-8"))
        toc = plan.get("toc_string")
        disc_id = plan.get("disc_id")
        if not isinstance(toc, str) or len(toc) > 1200:
            raise ValueError("Missing or invalid saved physical CD TOC")
        values = toc.split()
        if (len(values) < 4 or len(values) > 102
                or any(not re.fullmatch(r"[0-9]{1,10}", v) for v in values)):
            raise ValueError("Invalid saved TOC format")
        first, last, leadout = map(int, values[:3])
        starts = [int(v) for v in values[3:]]
        if (first != 1 or last < first or last > 99
                or len(starts) != last - first + 1
                or any(x < 150 or x >= leadout for x in starts)
                or starts != sorted(set(starts))):
            raise ValueError("Saved TOC track boundaries are invalid")
        if (last != report.get("expected_tracks")
                or disc_id != state.get("disc_id")
                or disc_id != plan.get("disc_id")):
            raise ValueError("Saved TOC does not match the verified rip")
        release_id = workflow["accepted_release_id"]
        info = lookup_release_medium(release_id, disc_id, last)
        media = info.get("all_media") or []
        if (info.get("status") != "no_exact_medium_match"
                or len(media) != 1 or info.get("total_media") != 1
                or media[0].get("format") != "CD"
                or media[0].get("position") != 1
                or media[0].get("track_count") != last
                or media[0].get("disc_id_attached")):
            raise ValueError("MusicBrainz CD medium is ambiguous, incompatible, or already has this Disc ID")
        url = "https://musicbrainz.org/cdtoc/attach?" + urllib.parse.urlencode({"toc": toc, "filter-release.query": release_id})
        return {
            "status": "human_submission_required",
            "job_id": job_id,
            "release_id": release_id,
            "disc_id": disc_id,
            "track_count": last,
            "medium_position": 1,
            "musicbrainz_attach_url": url,
            "release_url": "https://musicbrainz.org/release/" + release_id,
            "warning": ("MusicBrainz is an external website. Independently select the exact "
                        "physical CD medium and confirm there. OSCAR will not submit "
                        "anything, store MusicBrainz credentials or claim this edit succeeded."),
        }
    except (ValueError, RipError, WorkflowError, MusicBrainzError, OSError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/go/start")
def go_start(request: RipRequest, http_request: Request,
             x_oscar_rip_token: str | None = Header(default=None)):
    """Start tracked extraction, with same explicit staging confirmation."""
    from oscar.go_controller import GoError, start
    from oscar.ripping import RipError
    from oscar.workflow_ledger import WorkflowError
    _rip_auth(x_oscar_rip_token,http_request)
    if request.selected_tracks is not None or request.confirmation != "RIP_TO_STAGING":
        raise HTTPException(status_code=422, detail="Go! only accepts complete-disc rips")
    try:
        return start(request.stable_id)
    except (GoError,RipError,WorkflowError,OSError,ValueError) as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc


@app.post("/api/go/jobs/{job_id}/advance")
def go_advance(job_id: str, request: Request,
               x_oscar_rip_token: str | None = Header(default=None)):
    """Advance only safely supported rip/verification/identification operations."""
    from oscar.go_controller import GoError, advance
    from oscar.workflow_ledger import WorkflowError
    from oscar.musicbrainz import MusicBrainzError
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token,request)
    try:
        return advance(job_id)
    except (GoError,WorkflowError,MusicBrainzError,RipError,OSError,ValueError) as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc
