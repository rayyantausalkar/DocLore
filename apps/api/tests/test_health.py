from fastapi.testclient import TestClient

from doclore_api.main import app


def test_health_endpoint_reports_api_status() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "doclore-api"}
