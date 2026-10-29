import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from apps.api.src.config import settings
from apps.api.src.database import get_db
from apps.api.src.main import app
from apps.api.src.models.entities import AnomalyEvent, KPISnapshot

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
    "X-Correlation-ID": "test_corr_kpi_monitoring",
}


def test_kpi_computation_and_reconciliation():
    """
    Computes enterprise KPIs over loaded fact_orders and reconciles every metric
    against independent ground truth SQL queries.
    """
    with TestingSessionLocal() as db:
        fact_count = db.execute(text("SELECT COUNT(*) FROM fact_orders WHERE currency_code = 'USD'")).scalar()
        if fact_count == 0:
            pytest.skip("No fact orders in database for currency USD; run ETL pipeline first.")

        # Ground truth SQL
        gt_row = db.execute(text("""
            SELECT
                COALESCE(SUM(revenue), 0) AS rev,
                COALESCE(SUM(cost), 0) AS cost,
                COALESCE(SUM(profit), 0) AS profit,
                COUNT(DISTINCT external_order_id) AS orders
            FROM fact_orders
            WHERE currency_code = 'USD'
        """)).mappings().first()

    # Call API endpoint
    resp = client.post(
        "/v1/kpis/compute",
        headers=HEADERS,
        json={"currency_code": "USD"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]

    # Reconcile primary KPI figures
    assert round(data["revenue"], 2) == round(float(gt_row["rev"]), 2)
    assert round(data["cost"], 2) == round(float(gt_row["cost"]), 2)
    assert round(data["profit"], 2) == round(float(gt_row["profit"]), 2)
    assert data["orders"] == int(gt_row["orders"])

    # Reconcile derived metrics
    expected_margin = round((float(gt_row["profit"]) / float(gt_row["rev"])) * 100.0, 2)
    assert abs(data["margin_pct"] - expected_margin) < 0.05

    expected_aov = round(float(gt_row["rev"]) / int(gt_row["orders"]), 2)
    assert abs(data["average_order_value"] - expected_aov) < 0.05

    # Reconcile category breakdown total
    cat_total = sum(c["revenue"] for c in data["breakdowns"]["by_category"])
    assert abs(cat_total - data["revenue"]) < 1.0

    # Reconcile geography breakdown total
    geo_total = sum(g["revenue"] for g in data["breakdowns"]["by_geography"])
    assert abs(geo_total - data["revenue"]) < 1.0

    # Verify snapshot materialized in PostgreSQL
    with TestingSessionLocal() as db:
        snapshot = db.query(KPISnapshot).filter(KPISnapshot.snapshot_id == data["snapshot_id"]).first()
        assert snapshot is not None
        assert float(snapshot.revenue) == pytest.approx(data["revenue"], 0.1)


def test_latest_kpi_snapshot_endpoint():
    """
    Verifies that GET /v1/kpis/latest returns the most recent materialized snapshot.
    """
    resp = client.get("/v1/kpis/latest", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "snapshot_id" in data
    assert data["revenue"] > 0
    assert data["orders"] > 0


def test_anomaly_detection_on_revenue_spike():
    """
    Verifies that the anomaly detection engine identifies the deliberate
    Day 85 revenue spike injected by seed_generator.py in standard_10k.csv.
    """
    # 1. Compute a fresh snapshot
    kpi_resp = client.post("/v1/kpis/compute", headers=HEADERS, json={"currency_code": "USD"})
    assert kpi_resp.status_code == 200
    snapshot_id = kpi_resp.json()["data"]["snapshot_id"]

    # Clear prior open anomalies in test database to test clean detection
    with TestingSessionLocal() as db:
        db.query(AnomalyEvent).delete()
        db.commit()

    # 2. Evaluate anomalies
    eval_resp = client.post(f"/v1/anomalies/evaluate/{snapshot_id}", headers=HEADERS)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()["data"]

    # Verify at least one anomaly was detected
    assert eval_data["anomalies_detected"] >= 1
    rules = [a["rule_id"] for a in eval_data["anomalies"]]
    assert "RULE_REV_SPIKE" in rules

    spike_anomaly = next(a for a in eval_data["anomalies"] if a["rule_id"] == "RULE_REV_SPIKE")
    assert spike_anomaly["metric"] == "daily_revenue"
    assert spike_anomaly["deviation_pct"] >= 50.0
    assert spike_anomaly["severity"] in ("WARNING", "CRITICAL")
    assert "Executive Alert Summary" in eval_data["executive_alert_text"]

    # Verify persisted in PostgreSQL
    with TestingSessionLocal() as db:
        event = db.query(AnomalyEvent).filter(AnomalyEvent.rule_id == "RULE_REV_SPIKE").first()
        assert event is not None
        assert event.status == "OPEN"


def test_anomaly_alert_suppression():
    """
    Verifies alert suppression: re-evaluating when an OPEN alert exists within 24 hours
    does not create duplicate anomaly records.
    """
    # Compute snapshot
    kpi_resp = client.post("/v1/kpis/compute", headers=HEADERS, json={"currency_code": "USD"})
    snapshot_id = kpi_resp.json()["data"]["snapshot_id"]

    # First evaluation (generates open anomaly if none exist)
    client.post(f"/v1/anomalies/evaluate/{snapshot_id}", headers=HEADERS)

    with TestingSessionLocal() as db:
        count_before = db.query(AnomalyEvent).filter(AnomalyEvent.status == "OPEN").count()

    # Second evaluation immediately afterwards
    eval_resp2 = client.post(f"/v1/anomalies/evaluate/{snapshot_id}", headers=HEADERS)
    assert eval_resp2.status_code == 200
    eval_data2 = eval_resp2.json()["data"]

    # All active candidates should be suppressed
    assert eval_data2["anomalies_detected"] == 0

    with TestingSessionLocal() as db:
        count_after = db.query(AnomalyEvent).filter(AnomalyEvent.status == "OPEN").count()
        # Open alerts should not increase
        assert count_after == count_before


def test_open_anomalies_list_endpoint():
    """
    Verifies that GET /v1/anomalies/open returns currently active unacknowledged anomalies.
    """
    resp = client.get("/v1/anomalies/open", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    if len(data) > 0:
        assert data[0]["status"] == "OPEN"

