"""
End-to-End Environment Smoke Test for EIAP Phase 1 Foundation.
Validates:
1. API Liveness & Readiness endpoints
2. PostgreSQL database connection & latency
3. Batch ingestion endpoint with authentication & idempotency
4. Mailpit HTTP API connectivity
5. n8n orchestrator healthcheck
"""

import json
import os
import sys
import time
from pathlib import Path
import httpx
from dotenv import load_dotenv

# Load local environment if present
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
N8N_BASE_URL = os.environ.get("N8N_BASE_URL", "http://127.0.0.1:5678")
MAILPIT_BASE_URL = os.environ.get("MAILPIT_BASE_URL", "http://127.0.0.1:8025")
API_KEY = os.environ.get("API_KEY", "")


def run_smoke_test():
    print("=" * 70)
    print("EIAP PHASE 1 FOUNDATION SMOKE TEST")
    print("=" * 70)
    results = {}

    with httpx.Client(timeout=10.0) as client:
        # 1. API Live
        print("\n[1/5] Checking API Liveness (/health/live)...")
        try:
            r = client.get(f"{API_BASE_URL}/health/live")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            data = r.json()
            assert data["status"] == "ALIVE"
            print(f"  --> PASSED: Service '{data['service']}' v{data['version']} is ALIVE")
            results["api_liveness"] = "PASSED"
        except Exception as e:
            print(f"  --> FAILED: {e}")
            results["api_liveness"] = f"FAILED: {e}"

        # 2. API Ready
        print("\n[2/5] Checking API Readiness & Database Connectivity (/health/ready)...")
        try:
            r = client.get(f"{API_BASE_URL}/health/ready")
            assert r.status_code == 200, f"Expected 200, got {r.status_code} ({r.text})"
            data = r.json()
            assert data["status"] == "READY"
            pg_status = data["dependencies"]["postgres_analytics"]
            print(f"  --> PASSED: Analytics Database is UP (Latency: {pg_status['latency_ms']} ms)")
            results["api_readiness"] = "PASSED"
        except Exception as e:
            print(f"  --> FAILED: {e}")
            results["api_readiness"] = f"FAILED: {e}"

        # 3. Batch Ingestion API
        print("\n[3/5] Testing Ingestion Intake Endpoint (/v1/ingestion/batches)...")
        sample_batch = {
            "source": "SMOKE_TEST",
            "batch_id": f"smoke_batch_{int(time.time())}",
            "checksum": "a1b2c3d4e5f60718293a4b5c6d7e8f90",
            "schema_version": "1.0",
            "records": [
                {
                    "external_order_id": "ORD-SMOKE-001",
                    "order_date": "2026-08-01T10:00:00Z",
                    "product_code": "PROD-ENT-001",
                    "quantity": 1,
                    "unit_price": 1200.00,
                    "currency_code": "USD",
                }
            ],
        }
        try:
            headers = {"X-API-Key": API_KEY, "X-Correlation-ID": "corr_smoke_test_001"}
            r = client.post(f"{API_BASE_URL}/v1/ingestion/batches", json=sample_batch, headers=headers)
            assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
            res_data = r.json()
            run_id = res_data["data"]["run_id"]
            print(f"  --> PASSED: Batch accepted, created Run ID: {run_id}")

            # Test Idempotency (replay same batch)
            r_replay = client.post(f"{API_BASE_URL}/v1/ingestion/batches", json=sample_batch, headers=headers)
            assert r_replay.status_code == 200, f"Expected 200 for replay, got {r_replay.status_code}"
            assert r_replay.json()["data"]["run_id"] == run_id
            print(f"  --> PASSED: Idempotent replay detected correctly (matched Run ID)")
            results["ingestion_api"] = "PASSED"
        except Exception as e:
            print(f"  --> FAILED: {e}")
            results["ingestion_api"] = f"FAILED: {e}"

        # 4. Mailpit Connectivity
        print("\n[4/5] Checking Mailpit Local SMTP Service (Web UI & API)...")
        try:
            r = client.get(f"{MAILPIT_BASE_URL}/api/v1/messages")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            print(f"  --> PASSED: Mailpit HTTP API responding cleanly at {MAILPIT_BASE_URL}")
            results["mailpit"] = "PASSED"
        except Exception as e:
            print(f"  --> FAILED: {e}")
            results["mailpit"] = f"FAILED: {e}"

        # 5. n8n Orchestrator Health
        print("\n[5/5] Checking n8n Workflow Orchestrator (/healthz)...")
        try:
            r = client.get(f"{N8N_BASE_URL}/healthz")
            assert r.status_code == 200, f"Expected 200, got {r.status_code}"
            print(f"  --> PASSED: n8n Engine is responding cleanly at {N8N_BASE_URL}")
            results["n8n_orchestrator"] = "PASSED"
        except Exception as e:
            print(f"  --> FAILED: {e}")
            results["n8n_orchestrator"] = f"FAILED: {e}"

    print("\n" + "=" * 70)
    print("SMOKE TEST SUMMARY:")
    for k, v in results.items():
        print(f"  {k:20}: {v}")
    print("=" * 70)
    
    all_passed = all(v == "PASSED" for v in results.values())
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    run_smoke_test()

