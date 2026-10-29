import json
import psycopg

with psycopg.connect("postgresql://eiap_admin:eiap_local_secure_pass_2026_x9@127.0.0.1:5433/n8n_internal") as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.id, w.name, e.status, e."startedAt", e."stoppedAt",
                   ROUND(EXTRACT(EPOCH FROM (e."stoppedAt" - e."startedAt")) * 1000) AS duration_ms
            FROM execution_entity e
            JOIN workflow_entity w ON e."workflowId" = w.id
            ORDER BY e.id ASC;
        """)
        rows = cur.fetchall()
        print(f"Total executions recorded: {len(rows)}")
        for r in rows:
            print(f"Execution #{r[0]:02d} | Status: {r[2]:7s} | Duration: {r[5]:5.0f}ms | Workflow: {r[1]}")

