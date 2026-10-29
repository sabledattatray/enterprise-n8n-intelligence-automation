# Zero-Cost Developer Quickstart Guide: EIAP

**Project:** Enterprise Intelligence Automation Platform (EIAP)  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Repository:** [https://github.com/sabledattatray/enterprise-n8n-intelligence-automation](https://github.com/sabledattatray/enterprise-n8n-intelligence-automation)  

This guide provides a reproducible, zero-cost developer setup from a completely clean machine. The entire platform runs locally in Docker containers on `127.0.0.1` and requires **zero cloud subscriptions, zero paid API keys, and zero external email accounts**.

---

## 1. Prerequisites

Before starting, ensure your system has the following installed:

| Tool | Minimum Version | Verified Stable Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Docker Desktop** | 24.0+ | Docker Engine 27.x / Compose v2.x | Microservices container execution |
| **Python** | 3.12+ | Python 3.12.10 | Local test execution and CLI scripts |
| **Git** | 2.40+ | Latest Git | Source code management |
| **Google Chrome** | Latest (Optional) | Chrome 120+ | Headless screenshot capture |

---

## 2. Step-by-Step Installation

### Step 2.1: Clone Repository Cleanly
```bash
git clone https://github.com/sabledattatray/enterprise-n8n-intelligence-automation.git
cd enterprise-n8n-intelligence-automation
```

### Step 2.2: Configure Environment Variables
Copy the provided `.env.example` file to create your local `.env`:
```bash
# Windows PowerShell:
Copy-Item .env.example .env

# Linux / macOS:
cp .env.example .env
```
> [!NOTE]
> `.env.example` comes pre-configured with secure, zero-cost development defaults:
> - `POWERBI_ADAPTER=mock`: Emulates Power BI refreshes locally without Microsoft Fabric.
> - `AI_PROVIDER=mock`: Generates grounded 7-section briefings with zero LLM API costs.
> - `SMTP_HOST=mailpit`: Routes all reports to local Mailpit (`127.0.0.1:1025`).
> - `API_KEY`: Configured with local development API key.

### Step 2.3: Set Up Local Python Virtual Environment
```bash
# Windows:
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r apps/api/requirements.txt

# Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r apps/api/requirements.txt
```

### Step 2.4: Launch Docker Microservices Stack
```bash
docker compose up -d --build
```

Verify that all 4 containers are healthy:
```bash
docker compose ps
```
**Expected Output:**
```text
NAME            STATUS                    PORTS
eiap_api        Up (healthy)              127.0.0.1:8000->8000/tcp
eiap_mailpit    Up (healthy)              127.0.0.1:1025->1025/tcp, 127.0.0.1:8025->8025/tcp
eiap_n8n        Up (healthy)              127.0.0.1:5678->5678/tcp
eiap_postgres   Up (healthy)              127.0.0.1:5433->5432/tcp
```

### Step 2.5: Apply Database Migrations
Apply version-controlled Alembic schema migrations:
```bash
# Windows:
.\.venv\Scripts\alembic.exe upgrade head

# Linux / macOS:
alembic upgrade head
```

---

## 3. End-to-End Pipeline Demonstration

### Step 3.1: Generate Deterministic Synthetic Datasets
Generate 100-row smoke fixtures and 10,000-row standard datasets:
```bash
python data/generators/seed_generator.py
```

### Step 3.2: Execute Core Data Pipeline (WF01 - WF03)
Trigger ingestion, data quality validation, and star-schema dimensional loading:
```bash
# Ingest 10,000 raw rows:
curl -X POST http://127.0.0.1:8000/v1/ingestion/batches \
  -H "X-API-Key: <your-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "data/fixtures/orders_10k.csv"}'
```

### Step 3.3: Execute Full Automated Test Suite
Run the 51-test regression suite covering contract, unit, and integration tests:
```bash
pytest -v
```
**Expected Output:** `51 passed in ~15s (0 failures, 0 warnings)`.

### Step 3.4: Inspect Outbound Executive Reports in Mailpit
Open your browser to:
[http://127.0.0.1:8025/](http://127.0.0.1:8025/)
- View the responsive HTML Executive Intelligence Briefing delivered via local SMTP.
- Inspect headers, rendered tables, and KPI breakdowns without external email delivery.

### Step 3.5: Run Disaster Recovery Parity Test
Test database restoration into an isolated sandbox database:
```bash
python scripts/verify_restore.py
```
**Expected Output:** `DISASTER RECOVERY VERIFICATION: SUCCESS (RTO: ~2.39s, Zero Data Loss)`.

---

## 4. Teardown & Resource Cleanup

To stop containers while preserving persistent database volumes:
```bash
docker compose down
```

To stop containers and completely purge all local database volumes:
```bash
docker compose down -v
```

