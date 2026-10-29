import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.api.src.config import settings
from apps.api.src.database import get_db
from apps.api.src.main import app
from apps.api.src.models.entities import OperationalIncident

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
    "X-Correlation-ID": "test_corr_failure_recovery",
}


def test_record_transient_incident_and_retry_lifecycle():
    """
    Verifies that a transient failure (e.g. 504 Timeout) is classified as TRANSIENT,
    receives exponential backoff with jitter, and can be retried up to max_retries.
    """
    # 1. Record Transient Failure
    record_resp = client.post(
        "/v1/operations/incidents",
        headers=HEADERS,
        json={
            "workflow_name": "WF03 - Enterprise SQL ETL Pipeline",
            "execution_id": "exec_test_transient_01",
            "error_code": "ETL_TIMEOUT_504",
            "error_message": "Gateway Timeout: Database connection pool temporarily exhausted",
        },
    )
    assert record_resp.status_code == 201
    inc_data = record_resp.json()["data"]
    incident_id = inc_data["incident_id"]

    assert inc_data["failure_category"] == "TRANSIENT"
    assert inc_data["severity"] == "WARNING"
    assert inc_data["status"] == "OPEN"
    assert inc_data["eligible_for_retry"] is True
    assert inc_data["suggested_backoff_seconds"] is not None
    assert inc_data["suggested_backoff_seconds"] > 2.0  # Base 2s + jitter

    # 2. Trigger Retry 1
    retry_resp = client.post(f"/v1/operations/incidents/{incident_id}/retry", headers=HEADERS)
    assert retry_resp.status_code == 200
    retry_data = retry_resp.json()["data"]
    assert retry_data["retry_count"] == 1
    assert retry_data["status"] == "RETRIED"
    assert retry_data["eligible_for_retry"] is True

    # 3. Resolve Incident
    resolve_resp = client.post(
        f"/v1/operations/incidents/{incident_id}/resolve",
        headers=HEADERS,
        json={"resolution_note": "Connection pool scaled up and verified operational"},
    )
    assert resolve_resp.status_code == 200
    res_data = resolve_resp.json()["data"]
    assert res_data["status"] == "RESOLVED"
    assert res_data["resolved_at"] is not None


def test_permanent_auth_failure_classification():
    """
    Verifies that authentication errors are classified as AUTH with CRITICAL severity
    and marked DEAD_LETTER without endless retry loops.
    """
    resp = client.post(
        "/v1/operations/incidents",
        headers=HEADERS,
        json={
            "workflow_name": "WF04 - Power BI Refresh Orchestrator",
            "execution_id": "exec_test_auth_02",
            "error_code": "AUTH_FORBIDDEN_403",
            "error_message": "Invalid client secret provided for Entra ID tenant",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["failure_category"] == "AUTH"
    assert data["severity"] == "CRITICAL"
    assert data["status"] == "DEAD_LETTER"
    assert data["eligible_for_retry"] is False


def test_retry_exhaustion_moves_to_dead_letter():
    """
    Verifies that exceeding max_retries moves the incident to DEAD_LETTER status.
    """
    record_resp = client.post(
        "/v1/operations/incidents",
        headers=HEADERS,
        json={
            "workflow_name": "WF01 - Enterprise Data Ingestion",
            "error_code": "HTTP_503_TEMPORARY",
            "error_message": "Upstream source temporarily unavailable",
        },
    )
    incident_id = record_resp.json()["data"]["incident_id"]

    # Retries 1, 2, 3
    client.post(f"/v1/operations/incidents/{incident_id}/retry", headers=HEADERS)
    client.post(f"/v1/operations/incidents/{incident_id}/retry", headers=HEADERS)
    client.post(f"/v1/operations/incidents/{incident_id}/retry", headers=HEADERS)

    # 4th retry should be rejected and moved to DEAD_LETTER
    exceeded_resp = client.post(f"/v1/operations/incidents/{incident_id}/retry", headers=HEADERS)
    assert exceeded_resp.status_code == 400
    assert "exceeded" in exceeded_resp.json()["errors"][0]["message"].lower()

    with TestingSessionLocal() as db:
        record = db.query(OperationalIncident).filter(OperationalIncident.incident_id == incident_id).first()
        assert record.status == "DEAD_LETTER"


def test_operational_health_endpoint():
    """
    Verifies that GET /v1/operations/health returns aggregated system health metrics.
    """
    resp = client.get("/v1/operations/health", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "platform_status" in data
    assert "total_incidents" in data
    assert "open_incidents" in data
    assert "dead_letter_incidents" in data
    assert data["total_incidents"] > 0


def test_real_delayed_retry_enforcement():
    """
    Verifies that /delayed-retry enforces scheduled backoff periods (returning HTTP 429 when called prematurely)
    and succeeds once the backoff window elapses.
    """
    from datetime import datetime, timezone, timedelta

    # 1. Create a transient incident
    record_resp = client.post(
        "/v1/operations/incidents",
        headers=HEADERS,
        json={
            "workflow_name": "WF03 - Enterprise SQL ETL Pipeline",
            "execution_id": "exec_delayed_retry_test_01",
            "error_code": "PG_LOCK_TIMEOUT_504",
            "error_message": "Deadlock detected during fact upsert transaction",
        },
    )
    assert record_resp.status_code == 201
    incident_id = record_resp.json()["data"]["incident_id"]

    # 2. Call delayed-retry immediately -> Should fail with HTTP 429
    early_resp = client.post(f"/v1/operations/incidents/{incident_id}/delayed-retry", headers=HEADERS)
    assert early_resp.status_code == 429
    err_obj = early_resp.json()["errors"][0]
    assert err_obj["code"] == "BACKOFF_ACTIVE"
    assert "remaining" in err_obj["message"].lower()

    # 3. Fast-forward the scheduled_retry_at in database to simulate backoff elapsing
    with TestingSessionLocal() as db:
        rec = db.query(OperationalIncident).filter(OperationalIncident.incident_id == incident_id).first()
        details = dict(rec.error_details or {})
        details["scheduled_retry_at"] = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
        rec.error_details = details
        db.commit()

    # 4. Call delayed-retry again -> Now it should succeed
    success_resp = client.post(f"/v1/operations/incidents/{incident_id}/delayed-retry", headers=HEADERS)
    assert success_resp.status_code == 200
    res_data = success_resp.json()["data"]
    assert res_data["status"] == "RETRIED"
    assert res_data["retry_count"] == 1


