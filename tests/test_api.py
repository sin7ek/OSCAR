from fastapi.testclient import TestClient

from oscar.api import app


def test_health_is_safe_scaffold():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ripping"] == "disabled"
    assert payload["publishing"] == "disabled"
    assert payload["cleanup"] == "disabled"
