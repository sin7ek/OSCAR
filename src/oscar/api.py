"""OSCAR preview API: local drive settings only; no ripping or deletion."""
from fastapi import FastAPI

from oscar.settings import OscarSettings, inspect_drives, read_settings, save_settings
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
    return read_settings()


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
