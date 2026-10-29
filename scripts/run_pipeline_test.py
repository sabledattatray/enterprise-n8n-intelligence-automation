"""
End-to-End Pipeline Execution & Reconciliation Test for WF01, WF02, WF03.
Triggers live n8n webhooks and verifies against PostgreSQL warehouse.
"""

import time
import httpx
import psycopg

N8N_BASE_URL = "http://127.0.0.1:5678"
API_BASE_URL = "http://127.0.0.1:8000"
DB_CONN = "postgresql://eiap_admin:eiap_local_secure_pass_2026_x9@127.0.0.1:5433/business_analytics"
N8N_DB_CONN = "postgresql://eiap_admin:eiap_local_secure_pass_2026_x9@127.0.0.1:5433/n8n_internal"


def run_pipeline():
    print("=" * 80)
    print("EXECUTING EIAP END-TO-END PIPELINE VIA N8N WEBHOOKS (10,000 ROWS)")
    print("=" * 80)

    # 1. Clean previous test runs in business_analytics to ensure clean benchmark
    print("\n[Step 1] Preparing clean warehouse staging environment...")
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE fact_orders, raw_orders, rejected_records, ingestion_runs, workflow_executions CASCADE;")
            conn.commit()
    print("  --> Staging tables truncated successfully.")

    # 2. Trigger WF01 via live n8n webhook
    batch_id = "batch_std10k_e2e_benchmark"
    payload = {
        "source": "STANDARD_FIXTURE_10K",
        "batch_id": batch_id,
        "file_path": "data/fixtures/standard_10k.csv"
    }

    t0 = time.perf_counter()
    print(f"\n[Step 2] Triggering WF01 Webhook ({N8N_BASE_URL}/webhook/v1/ingest)...")
    with httpx.Client(timeout=120.0) as client:
        res = client.post(f"{N8N_BASE_URL}/webhook/v1/ingest", json=payload)
        t_ingest = time.perf_counter() - t0
        print(f"  --> Webhook Response Status: {res.status_code} in {t_ingest:.2f}s")
        print(f"  --> Response Body: {res.text[:300]}...")

    # 3. Query PostgreSQL warehouse for Ingestion & Quality Run
    print("\n[Step 3] Querying PostgreSQL Ingestion Run Ledger...")
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT run_id, source, batch_id, status, total_rows, accepted_rows, rejected_rows, duplicate_rows FROM ingestion_runs WHERE batch_id = %s", (batch_id,))
            run_row = cur.fetchone()
            assert run_row is not None, "Ingestion run not found in ingestion_runs!"
            run_id, source, b_id, r_status, total, accepted, rejected, duplicates = run_row
            print(f"  --> Run ID: {run_id}")
            print(f"  --> Status: {r_status}")
            print(f"  --> Total Staged: {total}")
            print(f"  --> Accepted Rows: {accepted}")
            print(f"  --> Duplicate Rows: {duplicates}")
            print(f"  --> Quarantined Rows: {rejected}")

            # 4. Trigger WF03 (ETL Commit) if not already committed
            if r_status != "COMMITTED":
                print(f"\n[Step 4] Triggering WF03 ETL Webhook ({N8N_BASE_URL}/webhook/v1/etl-commit)...")
                t_etl0 = time.perf_counter()
                with httpx.Client(timeout=120.0) as client:
                    etl_res = client.post(
                        f"{N8N_BASE_URL}/webhook/v1/etl-commit",
                        json={"run_id": str(run_id), "correlation_id": "corr_e2e_test"}
                    )
                    t_etl = time.perf_counter() - t_etl0
                    print(f"  --> ETL Webhook Status: {etl_res.status_code} in {t_etl:.2f}s")
                    print(f"  --> ETL Response: {etl_res.text}")

            # 5. Full Source-to-Target Reconciliation Audit
            print("\n" + "=" * 80)
            print("SOURCE-TO-TARGET RECONCILIATION AUDIT")
            print("=" * 80)
            cur.execute("SELECT count(*) FROM fact_orders WHERE source = %s", (source,))
            fact_count = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM raw_orders WHERE run_id = %s", (run_id,))
            raw_count = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM rejected_records WHERE run_id = %s", (run_id,))
            reject_count = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM dim_date;")
            dim_date_count = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM dim_product;")
            dim_prod_count = cur.fetchone()[0]

            cur.execute("SELECT count(*) FROM dim_geography;")
            dim_geo_count = cur.fetchone()[0]

            print(f"  Source Records Processed : {raw_count:>6}")
            print(f"  Accepted Facts Loaded   : {fact_count:>6} (Expected: 8564)")
            print(f"  Duplicate Orders Handled: {duplicates:>6} (Expected:  499)")
            print(f"  Quarantined Rejects     : {reject_count:>6} (Expected:  937)")
            print(f"  Reconciliation Invariant: {fact_count} + {duplicates} + {reject_count} = {fact_count + duplicates + reject_count}")
            assert (fact_count + duplicates + reject_count) == raw_count, "Reconciliation invariant failure!"

            # 6. Test Idempotent Replay
            print("\n[Step 6] Testing Idempotent Replay (Re-submitting identical 10k batch)...")
            with httpx.Client(timeout=120.0) as client:
                replay_res = client.post(f"{N8N_BASE_URL}/webhook/v1/ingest", json=payload)
                print(f"  --> Replay Response: {replay_res.status_code}")
                print(f"  --> Replay Body: {replay_res.text[:300]}")

            cur.execute("SELECT count(*) FROM fact_orders WHERE source = %s", (source,))
            fact_count_after_replay = cur.fetchone()[0]
            print(f"  --> Facts after replay: {fact_count_after_replay}")
            assert fact_count_after_replay == fact_count, "DUPLICATE FACTS DETECTED AFTER REPLAY!"
            print("  --> PASSED: 0 duplicate fact rows inserted on identical replay!")

            # 7. Check n8n execution log IDs
            with psycopg.connect(N8N_DB_CONN) as n8n_conn:
                with n8n_conn.cursor() as n8n_cur:
                    n8n_cur.execute('SELECT id, status, mode, "startedAt", "stoppedAt", "workflowId" FROM execution_entity ORDER BY id DESC LIMIT 5')
                    print("\n[Step 7] Recent n8n Executions Recorded in Orchestrator Engine:")
                    for ex in n8n_cur.fetchall():
                        print(f"  Execution #{ex[0]}: Status={ex[1]}, Mode={ex[2]}, Started={ex[3]}, Stopped={ex[4]}, WorkflowID={ex[5]}")

    print("\n" + "=" * 80)
    print("ALL INTEGRATION VERIFICATIONS & RECONCILIATIONS PASSED 100%!")
    print("=" * 80)


if __name__ == "__main__":
    run_pipeline()

