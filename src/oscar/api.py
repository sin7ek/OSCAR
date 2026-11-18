"""OSCAR preview API: local drive settings only; no ripping or deletion."""
import os
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

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


def _rip_auth(token: str | None):
    from oscar.ripping import RipError, authorize, enabled
    if not enabled():
        raise HTTPException(status_code=403, detail="Experimental ripping disabled")
    try:
        authorize(token)
    except RipError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/api/rip/plan")
def get_rip_plan(stable_id: str, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, plan
    _rip_auth(x_oscar_rip_token)
    try:
        return plan(stable_id)
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/rip/start")
def start_rip(request: RipRequest, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, start
    _rip_auth(x_oscar_rip_token)
    if request.confirmation != "RIP_TO_STAGING":
        raise HTTPException(status_code=422, detail="Explicit staging confirmation required")
    try:
        return start(request.stable_id)
    except (RipError, OSError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rip/jobs/{job_id}")
def get_rip_status(job_id: str, x_oscar_rip_token: str | None = Header(default=None)):
    from oscar.ripping import RipError, status
    _rip_auth(x_oscar_rip_token)
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


@app.post("/api/archive/name-preview")
def get_archive_name_preview(request: ArchiveNamePreviewRequest):
    """Preview only: does not touch files, devices, staging or Archive."""
    from oscar.archive_naming import archive_preview
    try:
        return archive_preview(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
