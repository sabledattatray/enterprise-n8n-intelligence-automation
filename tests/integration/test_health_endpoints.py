from fastapi.testclient import TestClient
from apps.api.src.main import app

client = TestClient(app)


def test_liveness_endpoint():
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ALIVE"
    assert "version" in data
    assert "service" in data


def test_correlation_id_middleware_injection():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers
    assert response.headers["X-Correlation-ID"].startswith("corr_")
    assert "X-Response-Time-Ms" in response.headers

