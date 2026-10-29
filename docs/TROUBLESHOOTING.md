# Operational Troubleshooting Guide: EIAP

**Document Version:** 1.0.0  
**Target Platform:** Enterprise n8n Intelligence Automation Platform  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Repository:** [https://github.com/sabledattatray/enterprise-n8n-intelligence-automation](https://github.com/sabledattatray/enterprise-n8n-intelligence-automation)  

---

## 1. Quick Diagnostic Checklist

When investigating an operational issue, execute these diagnostic commands in order:

```bash
# 1. Check all container health states
docker compose ps

# 2. Inspect API service logs
docker compose logs --tail=100 api

# 3. Inspect n8n workflow logs
docker compose logs --tail=100 n8n

# 4. Check platform incident status
curl -H "X-API-Key: <key>" http://127.0.0.1:8000/v1/operations/health
```

---

## 2. Common Issues & Resolutions

### Issue 1: PostgreSQL Port Conflict (`5432` already in use)
- **Symptom:** Docker container fails to start, reporting `port is already allocated`.
- **Cause:** A native PostgreSQL server is already running on host port `5432` (common on Windows developer machines).
- **Resolution:** EIAP explicitly maps host port `5433` to container port `5432`. Ensure `docker-compose.yml` and `.env` specify `POSTGRES_PORT=5433` and `127.0.0.1:5433:5432`. Never stop the host system's native database.

---

### Issue 2: HTTP 403 Forbidden on API Calls
- **Symptom:** Endpoints return `{"detail": "Forbidden: Invalid API Key"}`.
- **Cause:** The `X-API-Key` header is missing, expired, or does not match the active `API_KEY` in `.env`.
- **Resolution:**
  1. Inspect the active key in `.env`:
     ```powershell
     Get-Content .env | Select-String "API_KEY"
     ```
  2. Ensure your request includes:
     `-H "X-API-Key: <value>"`
  3. If rotated, restart containers to refresh environment injection:
     `docker compose restart api n8n`

---

### Issue 3: HTTP 429 `BACKOFF_ACTIVE` on Incident Retry
- **Symptom:** Calling `POST /v1/operations/incidents/{incident_id}/delayed-retry` returns `429 Too Many Requests`.
- **Cause:** The platform's backoff engine prevents premature retries. The scheduled backoff time window has not elapsed yet.
- **Resolution:** Check the `remaining_seconds` field in the response error envelope. Wait until the scheduled timestamp before re-calling, or use the force parameter for manual emergency operator overrides:
  `POST /v1/operations/incidents/{incident_id}/retry`

---

### Issue 4: n8n Workflow Import "Active Constraint" Error
- **Symptom:** CLI import outputs `null value in column "active" of relation "workflow_entity" violates not-null constraint`.
- **Cause:** n8n v1.82.2 enforces a database-level non-null constraint on the `active` column.
- **Resolution:** All workflow JSON files in `workflows/*.json` include `"active": true`. Ensure custom exported files include this property before running `n8n import:workflow`.

---

### Issue 5: No Emails Visible in Mailpit
- **Symptom:** Reports show status `SENT`, but Mailpit UI on `http://127.0.0.1:8025` is empty.
- **Cause:** Mailpit container was restarted with non-persistent volume or port forwarding issue.
- **Resolution:**
  1. Verify Mailpit is running: `docker compose ps eiap_mailpit`.
  2. Send a smoke dispatch:
     ```bash
     curl -X POST http://127.0.0.1:8000/v1/reports/dispatch \
       -H "X-API-Key: <key>" \
       -H "Content-Type: application/json" \
       -d '{"report_id": "test_smoke", "recipient_email": "test@internal.local"}'
     ```
  3. Refresh [http://127.0.0.1:8025/](http://127.0.0.1:8025/).

---

### Issue 6: Deadlock Detection during WF03 Fact Upserts
- **Symptom:** Operational incident created with error code `PG_LOCK_TIMEOUT_504`.
- **Cause:** Concurrent writers attempting to update overlapping dimension keys.
- **Resolution:** The platform's WF08 Failure Recovery engine automatically catches deadlock timeouts, classifies them as `TRANSIENT`, and schedules jittered exponential backoff. No manual intervention is needed unless the incident exhausts 3 retries and enters `DEAD_LETTER`.

