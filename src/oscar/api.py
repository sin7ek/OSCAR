"""OSCAR preview API: local drive settings only; no ripping or deletion."""
from fastapi import FastAPI

from oscar.settings import OscarSettings, discover_settings, inspect_drives, save_settings
from oscar.web import settings_page

app = FastAPI(title="OSCAR", version="0.1.0-alpha")


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
        return lookup_aliases(entity_type, entity_id)
    except MusicBrainzError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
