# Local Development Setup Guide (Windows 11)

This guide documents the reproduction steps for running the **Enterprise Intelligence Automation Platform (EIAP)** locally on Windows 11 with Docker Desktop.

---

## Prerequisites

1. **Windows 11 Pro / Enterprise (64-bit)**
2. **Docker Desktop v24+ with WSL 2 Backend**
   - Ensure Docker Desktop is running before launching services.
   - Resource allocation recommendation: >= 4 GB RAM, >= 2 CPU cores.
3. **Python 3.12 (64-bit)**
   - Verify via `py -3.12 --version`.
4. **Git CLI**
   - Verify via `git --version`.

---

## 5-Minute Quickstart

### 1. Clone & Navigate
```powershell
git clone <repository_url>
cd enterprise-n8n-intelligence-automation
```

### 2. Run Automated Bootstrap
The automated bootstrap script sets up the Python virtual environment, installs pinned dependencies, generates synthetic fixtures, initializes `.env`, and starts all Docker containers:

```powershell
.\scripts\bootstrap.ps1
```

### 3. Verify System Health
Run the comprehensive smoke test suite:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

Expected output:
```text
======================================================================
EIAP PHASE 1 FOUNDATION SMOKE TEST
======================================================================

[1/5] Checking API Liveness (/health/live)...
  --> PASSED: Service 'Enterprise-Intelligence-Automation-API' v1.0.0 is ALIVE

[2/5] Checking API Readiness & Database Connectivity (/health/ready)...
  --> PASSED: Analytics Database is UP (Latency: < 5 ms)

[3/5] Testing Ingestion Intake Endpoint (/v1/ingestion/batches)...
  --> PASSED: Batch accepted, created Run ID: ...
  --> PASSED: Idempotent replay detected correctly (matched Run ID)

[4/5] Checking Mailpit Local SMTP Service (Web UI & API)...
  --> PASSED: Mailpit HTTP API responding cleanly at http://127.0.0.1:8025

[5/5] Checking n8n Workflow Orchestrator (/healthz)...
  --> PASSED: n8n Engine is responding cleanly at http://127.0.0.1:5678
======================================================================
```

---

## Local Service Port Mappings

All services are securely bound **exclusively to `127.0.0.1` (localhost)**:

| Service | Port | Purpose | Health Endpoint |
| :--- | :--- | :--- | :--- |
| **FastAPI Microservice** | `127.0.0.1:8000` | Ingestion, Quality, Analytics API | `http://127.0.0.1:8000/health/live` |
| **n8n Orchestrator** | `127.0.0.1:5678` | Workflow Automation Canvas & Engine | `http://127.0.0.1:5678/healthz` |
| **PostgreSQL 16** | `127.0.0.1:5432` | Curated DW & n8n state | `pg_isready` |
| **Mailpit Web UI** | `127.0.0.1:8025` | Mock Email Viewer & Audit UI | `http://127.0.0.1:8025` |
| **Mailpit SMTP** | `127.0.0.1:1025` | Mock SMTP Delivery Port | SMTP Port |

---

## Running Database Migrations Locally

Migrations are managed with version-controlled Alembic scripts:

```powershell
# Upgrade schema to latest version
.\.venv\Scripts\alembic.exe upgrade head

# Roll back by one revision
.\.venv\Scripts\alembic.exe downgrade -1
```

---

## Running Automated Tests

```powershell
.\.venv\Scripts\pytest.exe -v
```

