"""Read-only OSCAR development API.

No drive, ripping, archive-write or deletion endpoints are exposed yet.
"""
from fastapi import FastAPI

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
