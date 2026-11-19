"""OSCAR preview API: local drive settings only; no ripping or deletion."""
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

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
def get_release_candidates(stable_id: str):
    """Lookup candidate releases; never auto-approve a physical edition."""
    from fastapi import HTTPException
    from oscar.musicbrainz import MusicBrainzError, lookup_enabled, lookup_releases

    if not lookup_enabled():
        raise HTTPException(status_code=403, detail="MusicBrainz lookup disabled")
    toc = get_toc(stable_id)
    try:
        return lookup_releases(toc["musicbrainz_disc_id"], toc["toc_string"])
    except MusicBrainzError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc



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
    if request.confirmation != "RIP_TO_STAGING":
        raise HTTPException(status_code=422, detail="Explicit staging confirmation required")
    try:
        return start(request.stable_id)
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
                       kind: str = "classical_v2",
                       x_oscar_rip_token: str | None = Header(default=None)):
    """Non-destructive consistency, cover candidate and index-preserving CUE preview."""
    from oscar.archive_review import ReviewError, review
    from oscar.ripping import RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return review(job_id, copy_id, kind)
    except (ReviewError, RipError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/dashboard")
def rip_drives_dashboard(request: Request, x_oscar_rip_token: str | None = Header(default=None)):
    """Observe active/idle optical drives; read-only and never starts a rip."""
    from oscar.ripping import dashboard, RipError
    _rip_auth(x_oscar_rip_token, request)
    try:
        return dashboard()
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
