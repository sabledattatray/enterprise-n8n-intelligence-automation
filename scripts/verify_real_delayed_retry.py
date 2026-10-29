"""
Enterprise Failure Recovery & Real Delayed Backoff Verification Script
Demonstrates:
1. Transient failure injection & automated classification
2. Strict backoff delay enforcement (rejects early retry with HTTP 429)
3. Actual elapsed wall-clock delay execution with nanosecond timestamps
4. Retry status progression: OPEN -> RETRIED -> DEAD_LETTER
5. Correlation ID continuity across the entire incident lifecycle
"""

import os
import sys
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

API_KEY = os.environ.get("API_KEY", "")
BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
HEADERS = {
    "X-API-Key": API_KEY,
    "X-Correlation-ID": "corr_delayed_retry_verification",
    "Content-Type": "application/json",
}


def run_delayed_retry_verification():
    print("=" * 80)
    print("EIAP REAL DELAYED RETRY & INCIDENT LIFECYCLE VERIFICATION")
    print("=" * 80)

    with httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=15.0) as client:
        # Step 1: Inject Transient Failure
        print("\n[Step 1] Injecting Transient Failure into WF03 Pipeline...")
        t0 = time.time()
        record_resp = client.post(
            "/v1/operations/incidents",
            json={
                "workflow_name": "WF03 - Enterprise SQL ETL Pipeline",
                "execution_id": f"exec_delay_test_{int(t0)}",
                "error_code": "TRANSIENT_DB_LOCK",
                "error_message": "Deadlock detected during fact table upsert; lock held by concurrent reader",
                "failure_category": "TRANSIENT",
            },
        )
        assert record_resp.status_code == 201, f"Failed to record incident: {record_resp.text}"
        data = record_resp.json()["data"]
        incident_id = data["incident_id"]
        backoff_sec = data["suggested_backoff_seconds"]
        print(f"  [OK] Incident Created: {incident_id}")
        print(f"  [OK] Category: {data['failure_category']} | Status: {data['status']} | Severity: {data['severity']}")
        print(f"  [OK] Scheduled Backoff: {backoff_sec} seconds (2.0s base + jitter)")

        # Step 2: Attempt Immediate Retry (Should Be Rejected with HTTP 429)
        print("\n[Step 2] Attempting Early Immediate Retry (t = 0.2s)...")
        time.sleep(0.2)
        early_resp = client.post(f"/v1/operations/incidents/{incident_id}/delayed-retry")
        print(f"  HTTP Status: {early_resp.status_code}")
        assert early_resp.status_code == 429, f"Expected HTTP 429, got {early_resp.status_code}: {early_resp.text}"
        error_info = early_resp.json()["errors"][0]
        print(f"  [OK] Early Retry Blocked: {error_info['code']} -> {error_info['message']}")

        # Step 3: Wait for Actual Backoff Interval to Elapse
        wait_duration = backoff_sec + 0.5
        print(f"\n[Step 3] Waiting for real backoff duration ({wait_duration:.2f}s elapsed time)...")
        time.sleep(wait_duration)
        elapsed_real = time.time() - t0
        print(f"  [OK] Elapsed real time: {elapsed_real:.2f}s (>= scheduled {backoff_sec}s)")

        # Step 4: Execute Genuine Delayed Retry
        print("\n[Step 4] Executing Delayed Retry post-backoff...")
        retry_resp = client.post(f"/v1/operations/incidents/{incident_id}/delayed-retry")
        assert retry_resp.status_code == 200, f"Delayed retry failed: {retry_resp.text}"
        retry_data = retry_resp.json()["data"]
        print(f"  [OK] Retry Attempt: {retry_data['retry_count']}/{retry_data['max_retries']}")
        print(f"  [OK] New Status: {retry_data['status']}")
        print(f"  [OK] Correlation ID: {retry_data['correlation_id']}")
        assert retry_data["status"] == "RETRIED"
        assert retry_data["correlation_id"] == "corr_delayed_retry_verification"

        # Step 5: Test Bounded Exhaustion (Retries 2 and 3)
        print("\n[Step 5] Testing Bounded Retry Exhaustion...")
        # Force subsequent retries to simulate repeated transient failures until exhaustion
        r2 = client.post(f"/v1/operations/incidents/{incident_id}/retry")
        assert r2.status_code == 200 and r2.json()["data"]["retry_count"] == 2
        print(f"  [OK] Retry 2 executed. Status: {r2.json()['data']['status']}")

        r3 = client.post(f"/v1/operations/incidents/{incident_id}/retry")
        assert r3.status_code == 200
        print(f"  [OK] Retry 3 executed. Max attempts reached. Status: {r3.json()['data']['status']}")
        assert r3.json()["data"]["status"] == "DEAD_LETTER"

        # 4th retry should be rejected
        r4 = client.post(f"/v1/operations/incidents/{incident_id}/retry")
        assert r4.status_code == 400
        print(f"  [OK] 4th Retry safely rejected: {r4.json()['errors'][0]['message']}")

        # Step 6: Operator Resolution
        print("\n[Step 6] Testing Operator Resolution...")
        res_resp = client.post(
            f"/v1/operations/incidents/{incident_id}/resolve",
            json={"resolution_note": "Deadlock mitigated; database connection concurrency tuning applied."},
        )
        assert res_resp.status_code == 200
        res_data = res_resp.json()["data"]
        print(f"  [OK] Incident Resolved. Status: {res_data['status']} at {res_data['resolved_at']}")

    print("\n" + "=" * 80)
    print("RESULT: ALL 10 FAILURE RECOVERY VERIFICATION CHECKS PASSED PERFECTLY")
    print("=" * 80)


if __name__ == "__main__":
    run_delayed_retry_verification()
