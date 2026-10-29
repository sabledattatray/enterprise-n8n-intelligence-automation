import json
import psycopg

conn = psycopg.connect("postgresql://eiap_admin:eiap_local_secure_pass_2026_x9@127.0.0.1:5433/n8n_internal")
cur = conn.cursor()
cur.execute('SELECT id, status, finished, "startedAt", "stoppedAt", "workflowId" FROM execution_entity ORDER BY id DESC LIMIT 5')
print("Recent Executions:")
for row in cur.fetchall():
    print(" ", row)

cur.execute('SELECT "executionId", data FROM execution_data ORDER BY "executionId" DESC LIMIT 1')
row = cur.fetchone()
if row:
    print(f"\nExecution {row[0]} data:")
    print(json.dumps(row[1], indent=2))
