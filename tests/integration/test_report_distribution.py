import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.api.src.config import settings
from apps.api.src.database import get_db
from apps.api.src.main import app
from apps.api.src.models.entities import ReportDispatch

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
    "X-Correlation-ID": "test_corr_report_distribution",
}


def test_report_dispatch_to_mailpit():
    """
    Verifies that executive report is generated and delivered to Mailpit SMTP,
    and verified via Mailpit REST API.
    """
    recipient = f"executive-{uuid.uuid4().hex[:6]}@internal.local"

    # 1. Dispatch Report
    resp = client.post(
        "/v1/reports/dispatch",
        headers=HEADERS,
        json={"recipient_email": recipient, "channel": "EMAIL"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "SENT"
    assert data["recipient"] == recipient
    assert data["idempotent_replay"] is False
    assert "Mailpit" in data["smtp_target"]

    # 2. Verify Delivery in Mailpit REST API
    mailpit_api = "http://127.0.0.1:8025/api/v1/messages"
    try:
        with httpx.Client(timeout=5.0) as http_c:
            mp_resp = http_c.get(mailpit_api)
            if mp_resp.status_code == 200:
                messages = mp_resp.json().get("messages", [])
                assert len(messages) > 0
                latest_msg = messages[0]
                assert recipient in latest_msg["To"][0]["Address"]
                assert "EIAP Executive Briefing" in latest_msg["Subject"]
    except Exception as exc:
        pytest.fail(f"Failed to query Mailpit HTTP API at {mailpit_api}: {exc}")

    # 3. Verify Database Record in report_dispatches
    with TestingSessionLocal() as db:
        record = db.query(ReportDispatch).filter(ReportDispatch.dispatch_id == data["dispatch_id"]).first()
        assert record is not None
        assert record.status == "SENT"
        assert record.recipient_hash == data["recipient_hash"]


def test_report_dispatch_idempotent_deduplication():
    """
    Verifies that duplicate dispatch requests for the same report & recipient
    return the cached dispatch with idempotent_replay=True.
    """
    recipient = f"cfo-{uuid.uuid4().hex[:6]}@internal.local"

    # First dispatch
    resp1 = client.post(
        "/v1/reports/dispatch",
        headers=HEADERS,
        json={"recipient_email": recipient},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()["data"]
    assert data1["idempotent_replay"] is False

    # Second dispatch immediately afterwards
    resp2 = client.post(
        "/v1/reports/dispatch",
        headers=HEADERS,
        json={"recipient_email": recipient},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    assert data2["dispatch_id"] == data1["dispatch_id"]
    assert data2["idempotent_replay"] is True


def test_report_dispatch_history_endpoint():
    """
    Verifies that GET /v1/reports/history lists previously dispatched reports.
    """
    resp = client.get("/v1/reports/history", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0
    assert "report_id" in data[0]
    assert data[0]["status"] in ("SENT", "DELIVERED", "FAILED")

