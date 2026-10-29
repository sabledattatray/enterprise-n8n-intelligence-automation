import json
import psycopg

with psycopg.connect("postgresql://eiap_admin:eiap_local_secure_pass_2026_x9@127.0.0.1:5433/n8n_internal") as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.id, w.name, e.status, e."startedAt", e."stoppedAt",
                   ROUND(EXTRACT(EPOCH FROM (e."stoppedAt" - e."startedAt")) * 1000) AS duration_ms
            FROM execution_entity e
            JOIN workflow_entity w ON e."workflowId" = w.id
            WHERE e.id >= 10
            ORDER BY e.id ASC;
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"ID: {r[0]} | Workflow: {r[1]} | Status: {r[2]} | Started: {r[3]} | Stopped: {r[4]} | Duration: {r[5]}ms")

