#!/usr/bin/env python3
"""
Enterprise Intelligence Automation Platform (EIAP)
Database Seeder Script

Loads the deterministic 10,000-row fixture into PostgreSQL analytics warehouse
using the core EIAP FastAPI pipeline (Ingestion -> Quality Engine -> SQL ETL -> KPI Compute).
Ensures the database is fully seeded for regression test suites and demonstration.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from apps.api.src.config import settings
from apps.api.src.main import app


def seed_database():
    print("=" * 80)
    print("EIAP DATABASE SEEDER: POPULATING POSTGRESQL ANALYTICS WAREHOUSE")
    print(f"Target Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'configured'}")
    print("=" * 80)

    client = TestClient(app)
    headers = {
        "X-API-Key": settings.API_KEY,
        "X-Correlation-ID": "seed_db_initialization",
    }

    fixture_path = "data/fixtures/standard_10k.csv"
    if not Path(fixture_path).exists():
        print(f"[ERROR] Fixture file not found: {fixture_path}")
        sys.exit(1)

    t0 = time.perf_counter()

    # Step 1: Ingest 10k Records
    print("\n[Step 1/4] Ingesting 10,000 records from standard_10k.csv...")
    resp_ingest = client.post(
        "/v1/ingestion/file",
        headers=headers,
        json={"file_path": fixture_path, "batch_id": "seed_batch_standard_10k"},
    )
    if resp_ingest.status_code not in (200, 201):
        print(f"[FAIL] Ingestion failed: {resp_ingest.status_code} - {resp_ingest.text}")
        sys.exit(1)

    run_id = resp_ingest.json()["data"]["run_id"]
    print(f"  --> Ingestion run created: {run_id}")

    # Step 2: Quality Engine Validation
    print("\n[Step 2/4] Executing Data Quality Engine validation...")
    resp_val = client.post(f"/v1/quality/validate/{run_id}", headers=headers)
    if resp_val.status_code != 200:
        print(f"[FAIL] Quality validation failed: {resp_val.status_code} - {resp_val.text}")
        sys.exit(1)

    val_data = resp_val.json()["data"]
    print(f"  --> Quality validation complete: {val_data['accepted_rows']} accepted, {val_data['rejected_rows']} rejected, {val_data['duplicate_rows']} duplicate")

    # Step 3: Atomic SQL ETL Commit
    print("\n[Step 3/4] Executing atomic dimensional ETL commit...")
    resp_etl = client.post(f"/v1/etl/commit/{run_id}", headers=headers)
    if resp_etl.status_code != 200:
        print(f"[FAIL] ETL commit failed: {resp_etl.status_code} - {resp_etl.text}")
        sys.exit(1)

    etl_data = resp_etl.json()["data"]
    print(f"  --> ETL committed: {etl_data['facts_upserted']} fact rows upserted, {etl_data['dimensions_loaded']} dimensions loaded")

    # Step 4: Initial KPI Snapshot Computation
    print("\n[Step 4/4] Computing baseline KPI snapshot (USD)...")
    resp_kpi = client.post("/v1/kpis/compute", headers=headers, json={"currency_code": "USD"})
    if resp_kpi.status_code != 200:
        print(f"[FAIL] KPI compute failed: {resp_kpi.status_code} - {resp_kpi.text}")
        sys.exit(1)

    kpi_data = resp_kpi.json()["data"]
    snapshot_id = kpi_data["snapshot_id"]
    print(f"  --> KPI snapshot materialized: {snapshot_id}")
    print(f"  --> Revenue: ${kpi_data['revenue']:,.2f} | Orders: {kpi_data['orders']:,} | Margin: {kpi_data['margin_pct']:.2f}%")

    total_time = time.perf_counter() - t0
    print(f"\n[OK] Database successfully seeded in {total_time:.2f}s!")


if __name__ == "__main__":
    seed_database()
