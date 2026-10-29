# REST API Reference: Enterprise Intelligence Automation Platform (EIAP)

**API Version:** 1.0.0  
**Base URL:** `http://127.0.0.1:8000`  
**Authentication Header:** `X-API-Key: <token>`  
**Correlation Header:** `X-Correlation-ID: <string>` (optional, auto-generated if omitted)  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Repository:** [https://github.com/sabledattatray/enterprise-n8n-intelligence-automation](https://github.com/sabledattatray/enterprise-n8n-intelligence-automation)  

---

## 1. Global Request & Response Contracts

All responses follow a strictly typed API envelope:

### Success Envelope
```json
{
  "correlation_id": "corr_4d76a20e8b11",
  "status": "SUCCESS",
  "data": { ... },
  "errors": [],
  "metadata": {
    "timestamp": "2026-10-29T08:07:20.569Z"
  }
}
```

### Error Envelope
```json
{
  "correlation_id": "corr_4d76a20e8b11",
  "status": "ERROR",
  "data": null,
  "errors": [
    {
      "code": "BACKOFF_ACTIVE",
      "message": "Retry rejected: Backoff interval has not elapsed yet. 2.27s remaining."
    }
  ]
}
```

---

## 2. Core Endpoints Reference

### 2.1: Health & System Probes

#### `GET /health/live`
- **Purpose:** Kubernetes / Docker liveness probe verifying HTTP responsiveness.
- **Auth:** None required.
- **Response:** `200 OK` `{"status": "alive"}`

#### `GET /health/ready`
- **Purpose:** Readiness probe checking live PostgreSQL database connectivity.
- **Auth:** None required.
- **Response:** `200 OK` `{"status": "ready", "database": "connected"}`

---

### 2.2: Data Ingestion (`/v1/ingestion`)

#### `POST /v1/ingestion/batches`
- **Purpose:** Ingests a new batch of orders from a file path or JSON payload.
- **Headers:** `X-API-Key`
- **Request Body:**
  ```json
  {
    "file_path": "data/fixtures/orders_10k.csv"
  }
  ```
- **Response:** `200 OK`
  ```json
  {
    "run_id": "87c4f4d1-4cb5-4523-875f-ba92cf57d598",
    "status": "COMPLETED",
    "records_ingested": 10000,
    "content_sha256": "4b9e28f7a637c352a1d..."
  }
  ```

---

### 2.3: Data Quality & Validation (`/v1/quality`)

#### `POST /v1/quality/validate`
- **Purpose:** Evaluates records in `raw_orders` against validation rules.
- **Headers:** `X-API-Key`
- **Request Body:** `{"run_id": "<uuid>"}`
- **Response:** `200 OK`
  ```json
  {
    "run_id": "87c4f4d1-4cb5-4523-875f-ba92cf57d598",
    "total_records": 10000,
    "accepted_count": 8564,
    "rejected_count": 937,
    "duplicate_count": 499
  }
  ```

---

### 2.4: SQL ETL & Warehouse Loading (`/v1/etl`)

#### `POST /v1/etl/commit`
- **Purpose:** Atomically resolves dimensions and upserts valid records into `fact_orders`.
- **Headers:** `X-API-Key`
- **Request Body:** `{"run_id": "<uuid>"}`
- **Response:** `200 OK` `{"status": "COMMITTED", "fact_rows_loaded": 8564}`

---

### 2.5: Power BI Synchronization (`/v1/integrations/powerbi`)

#### `POST /v1/integrations/powerbi/refresh`
- **Purpose:** Initiates an asynchronous semantic model refresh (mock or real).
- **Headers:** `X-API-Key`
- **Response:** `202 Accepted` `{"refresh_id": "<uuid>", "status": "IN_PROGRESS"}`

#### `GET /v1/integrations/powerbi/status/{refresh_id}`
- **Purpose:** Polls the status of an active refresh operation.
- **Response:** `200 OK` `{"refresh_id": "<uuid>", "status": "COMPLETED"}`

---

### 2.6: KPIs & Analytics (`/v1/kpis`)

#### `POST /v1/kpis/compute`
- **Purpose:** Computes and materializes a single-currency star-schema KPI snapshot.
- **Headers:** `X-API-Key`
- **Request Body:**
  ```json
  {
    "period_start": "2026-07-01T00:00:00Z",
    "period_end": "2026-09-30T23:59:59Z",
    "currency_code": "USD"
  }
  ```
- **Response:** `200 OK` (Revenue, Margin %, Orders, AOV, Dimensions)

#### `GET /v1/kpis/latest`
- **Purpose:** Retrieves the most recently computed and materialized KPI snapshot.
- **Response:** `200 OK`

---

### 2.7: Anomaly Detection (`/v1/anomalies`)

#### `POST /v1/anomalies/evaluate/{snapshot_id}`
- **Purpose:** Evaluates rule-based statistical anomalies against a snapshot.
- **Response:** `200 OK` (Anomalies detected, suppression status)

#### `GET /v1/anomalies/open`
- **Purpose:** Returns list of unsuppressed active business anomalies.
- **Response:** `200 OK`

---

### 2.8: Grounded AI Executive Intelligence (`/v1/ai`)

#### `POST /v1/ai/generate`
- **Purpose:** Synthesizes a 7-section executive briefing with mathematical grounding.
- **Request Body:**
  ```json
  {
    "snapshot_id": "<uuid>",
    "provider": "mock"
  }
  ```
- **Response:** `200 OK` (7-section markdown document, grounding score = 100%)

---

### 2.9: Automated Report Distribution (`/v1/reports`)

#### `POST /v1/reports/dispatch`
- **Purpose:** Dispatches responsive HTML briefing via SMTP with idempotency protection.
- **Request Body:**
  ```json
  {
    "report_id": "rep_2026_q3_exec",
    "recipient_email": "executives@company.local"
  }
  ```
- **Response:** `200 OK` `{"status": "SENT", "message_id": "<uuid>@internal.local"}`

---

### 2.10: Operations & Incident Management (`/v1/operations`)

#### `POST /v1/operations/incidents`
- **Purpose:** Ingests and classifies a pipeline exception (`TRANSIENT`, `AUTH`, `VALIDATION`).
- **Response:** `201 Created`

#### `POST /v1/operations/incidents/{incident_id}/delayed-retry`
- **Purpose:** Executes a time-delayed retry. Enforces scheduled backoff; returns `HTTP 429` if called early.
- **Response:** `200 OK` (if elapsed) or `429 Too Many Requests` (if early)

#### `POST /v1/operations/incidents/{incident_id}/resolve`
- **Purpose:** Closes an incident with an operator resolution note.
- **Response:** `200 OK` `{"status": "RESOLVED"}`

#### `GET /v1/operations/health`
- **Purpose:** Returns platform health overview (total, open, dead-letter incidents).
- **Response:** `200 OK`

