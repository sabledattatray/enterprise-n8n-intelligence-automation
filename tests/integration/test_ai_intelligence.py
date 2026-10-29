import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from apps.api.src.config import settings
from apps.api.src.database import get_db
from apps.api.src.main import app
from apps.api.src.models.entities import AISummary, KPISnapshot

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
    "X-Correlation-ID": "test_corr_ai_intelligence",
}


def test_ai_summary_generation_and_grounding():
    """
    Verifies that AI executive summary is generated, adheres to the 7-section structure,
    and passes strict grounding validation against authoritative snapshot figures.
    """
    # 1. Fetch latest snapshot or compute one
    kpi_resp = client.post("/v1/kpis/compute", headers=HEADERS, json={"currency_code": "USD"})
    assert kpi_resp.status_code == 200
    snapshot_data = kpi_resp.json()["data"]
    snapshot_id = snapshot_data["snapshot_id"]

    # 2. Generate summary
    resp = client.post(
        "/v1/ai/generate",
        headers=HEADERS,
        json={"snapshot_id": snapshot_id, "provider": "mock"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    # Verify structural integrity
    sections = data["sections"]
    assert len(sections["business_overview"]) > 50
    assert len(sections["revenue_profitability"]) > 50
    assert len(sections["order_performance"]) > 50
    assert len(sections["product_geography_insights"]) > 50
    assert len(sections["detected_anomalies"]) > 10
    assert len(sections["operational_observations"]) > 30
    assert len(sections["investigation_priorities"]) >= 2

    # Verify grounding validation
    assert data["validation_status"] in ("VALIDATED", "FALLBACK_GENERATED")
    checks = data["grounding_checks"]
    assert len(checks) >= 4
    for c in checks:
        assert c["is_grounded"] is True

    # Verify database persistence in ai_summaries table
    with TestingSessionLocal() as db:
        record = db.query(AISummary).filter(AISummary.summary_id == data["summary_id"]).first()
        assert record is not None
        assert record.snapshot_id == uuid.UUID(snapshot_id)
        assert record.model_provider == "mock"
        assert record.validation_status in ("VALIDATED", "FALLBACK_GENERATED")


def test_ai_fallback_simulation():
    """
    Verifies that when force_fallback=True or external provider fails,
    the engine safely activates the deterministic template fallback.
    """
    resp = client.post(
        "/v1/ai/generate",
        headers=HEADERS,
        json={"provider": "mock", "force_fallback": True},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["validation_status"] == "FALLBACK_GENERATED"
    assert data["model_name"] == "deterministic-template-engine-v1"


def test_ai_latest_endpoint():
    """
    Verifies that GET /v1/ai/latest retrieves the most recent validated summary.
    """
    resp = client.get("/v1/ai/latest", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "summary_id" in data
    assert "sections" in data
    assert len(data["sections"]["investigation_priorities"]) > 0


def test_ai_nonexistent_snapshot_returns_404():
    """
    Verifies that requesting a summary for a nonexistent snapshot UUID returns 404.
    """
    random_uuid = str(uuid.uuid4())
    resp = client.post(
        "/v1/ai/generate",
        headers=HEADERS,
        json={"snapshot_id": random_uuid},
    )
    assert resp.status_code == 404
    assert resp.json()["status"] == "ERROR"

