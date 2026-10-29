import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.api.src.config import settings
from apps.api.src.database import get_db
from apps.api.src.main import app
from apps.api.src.models.entities import IntegrationEvent

# Use local postgres connection for integration test
engine = create_engine(settings.LOCAL_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

HEADERS = {
    "X-API-Key": settings.API_KEY,
    "X-Correlation-ID": "test_corr_pbi_mock",
}


def test_powerbi_refresh_success_lifecycle():
    """
    Verifies that a mock Power BI refresh request is submitted and progresses
    through the asynchronous lifecycle: IN_PROGRESS -> COMPLETED.
    """
    dataset_id = f"ds-sales-test-{uuid.uuid4().hex[:6]}"
    workspace_id = "ws-analytics-test"

    # 1. Submit Refresh
    submit_resp = client.post(
        "/v1/integrations/powerbi/refresh",
        headers=HEADERS,
        json={
            "dataset_id": dataset_id,
            "workspace_id": workspace_id,
            "simulate_failure": False,
            "simulate_timeout": False,
        },
    )
    assert submit_resp.status_code == 202
    submit_data = submit_resp.json()["data"]
    refresh_id = submit_data["refresh_id"]
    assert refresh_id.startswith("pbi_ref_")
    assert submit_data["status"] == "IN_PROGRESS"
    assert submit_data["adapter_mode"] == "mock"
    assert submit_data["idempotent_replay"] is False

    # 2. Poll Refresh (attempt 1) -> transitions to COMPLETED
    poll_resp = client.get(
        f"/v1/integrations/powerbi/refresh/{refresh_id}",
        headers=HEADERS,
    )
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()["data"]
    assert poll_data["refresh_id"] == refresh_id
    assert poll_data["status"] == "COMPLETED"
    assert poll_data["completed_at"] is not None
    assert poll_data["attempts"] >= 1

    # 3. Verify PostgreSQL audit trail in integration_events
    with TestingSessionLocal() as db:
        event = (
            db.query(IntegrationEvent)
            .filter(IntegrationEvent.external_request_id == refresh_id)
            .first()
        )
        assert event is not None
        assert event.integration_type == "POWERBI_REFRESH"
        assert event.status == "COMPLETED"
        assert event.metadata_json["dataset_id"] == dataset_id


def test_powerbi_refresh_idempotent_deduplication():
    """
    Verifies that consecutive refresh submissions for the same dataset within the
    5-minute deduplication window return the existing refresh operation.
    """
    dataset_id = f"ds-dedup-{uuid.uuid4().hex[:6]}"

    # First request
    resp1 = client.post(
        "/v1/integrations/powerbi/refresh",
        headers=HEADERS,
        json={"dataset_id": dataset_id},
    )
    assert resp1.status_code == 202
    data1 = resp1.json()["data"]
    assert data1["idempotent_replay"] is False

    # Second identical request immediately afterwards
    resp2 = client.post(
        "/v1/integrations/powerbi/refresh",
        headers=HEADERS,
        json={"dataset_id": dataset_id},
    )
    assert resp2.status_code == 202
    data2 = resp2.json()["data"]
    assert data2["refresh_id"] == data1["refresh_id"]
    assert data2["idempotent_replay"] is True


def test_powerbi_refresh_simulated_failure():
    """
    Verifies that when simulate_failure=True, the adapter transitions to FAILED
    with a sanitized error message and updates integration_events.
    """
    dataset_id = f"ds-fail-{uuid.uuid4().hex[:6]}"

    submit_resp = client.post(
        "/v1/integrations/powerbi/refresh",
        headers=HEADERS,
        json={
            "dataset_id": dataset_id,
            "simulate_failure": True,
        },
    )
    assert submit_resp.status_code == 202
    refresh_id = submit_resp.json()["data"]["refresh_id"]

    # Poll status
    poll_resp = client.get(
        f"/v1/integrations/powerbi/refresh/{refresh_id}",
        headers=HEADERS,
    )
    assert poll_resp.status_code == 200
    poll_data = poll_resp.json()["data"]
    assert poll_data["status"] == "FAILED"
    assert "error" in poll_data["error_message"].lower()

    # Check DB event status
    with TestingSessionLocal() as db:
        event = (
            db.query(IntegrationEvent)
            .filter(IntegrationEvent.external_request_id == refresh_id)
            .first()
        )
        assert event is not None
        assert event.status == "FAILED"


def test_powerbi_refresh_simulated_timeout():
    """
    Verifies that when simulate_timeout=True, the refresh operation remains IN_PROGRESS.
    """
    dataset_id = f"ds-timeout-{uuid.uuid4().hex[:6]}"

    submit_resp = client.post(
        "/v1/integrations/powerbi/refresh",
        headers=HEADERS,
        json={
            "dataset_id": dataset_id,
            "simulate_timeout": True,
        },
    )
    assert submit_resp.status_code == 202
    refresh_id = submit_resp.json()["data"]["refresh_id"]

    # Poll status multiple times; status should remain IN_PROGRESS
    for _ in range(2):
        poll_resp = client.get(
            f"/v1/integrations/powerbi/refresh/{refresh_id}",
            headers=HEADERS,
        )
        assert poll_resp.status_code == 200
        assert poll_resp.json()["data"]["status"] == "IN_PROGRESS"


def test_powerbi_nonexistent_refresh_returns_404():
    """
    Verifies that polling a non-existent refresh ID returns a clean 404 envelope.
    """
    resp = client.get(
        "/v1/integrations/powerbi/refresh/pbi_ref_nonexistent_9999",
        headers=HEADERS,
    )
    assert resp.status_code == 404
    assert resp.json()["status"] == "ERROR"

