# Configuration & Environment Guide: EIAP

**Document Version:** 1.0.0  
**Target Platform:** Enterprise n8n Intelligence Automation Platform  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Repository:** [https://github.com/sabledattatray/enterprise-n8n-intelligence-automation](https://github.com/sabledattatray/enterprise-n8n-intelligence-automation)  

---

## 1. Environment Variables Dictionary

The platform is configured via environment variables defined in `.env` (derived from `.env.example`).

| Variable Name | Required | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Yes | `development` | Deployment environment (`development`, `staging`, `production`). |
| `LOG_LEVEL` | Yes | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `API_KEY` | Yes | `eiap_live_sec_key_...` | Ingress authentication token for all FastAPI endpoints. |
| `WEBHOOK_SECRET` | Yes | `eiap_local_webhook_secret_...` | Secret key for validating incoming webhook signatures. |
| `CORS_ORIGINS` | Yes | `["http://localhost:5678"]` | Allowed CORS origins for n8n frontend communication. |
| `POSTGRES_HOST` | Yes | `postgres` | Docker container hostname for PostgreSQL. |
| `POSTGRES_PORT` | Yes | `5433` | Host port mapped to PostgreSQL container port `5432`. |
| `POSTGRES_USER` | Yes | `eiap_admin` | Database superuser username. |
| `POSTGRES_PASSWORD` | Yes | `eiap_local_secure_pass_...` | Database password. |
| `POSTGRES_DB_ANALYTICS`| Yes | `business_analytics` | Primary database name for analytics star schema. |
| `POSTGRES_DB_N8N` | Yes | `n8n_internal` | Isolated database name for n8n workflow engine. |
| `N8N_HOST` | Yes | `127.0.0.1` | Local host interface for n8n. |
| `N8N_PORT` | Yes | `5678` | Host port mapped to n8n web interface. |
| `N8N_ENCRYPTION_KEY` | Yes | `eiap_n8n_dev_key_32chars_long_val!`| 32-character AES key for encrypting n8n credentials at rest. |
| `SMTP_HOST` | Yes | `mailpit` | Outbound email hostname (`mailpit` for local dev). |
| `SMTP_PORT` | Yes | `1025` | Outbound email port (Mailpit SMTP port). |
| `SMTP_FROM` | Yes | `eiap-reports@internal.local` | From address for automated executive reports. |
| `MAILPIT_WEB_PORT` | Yes | `8025` | Host port for inspecting captured emails in Mailpit UI. |
| `POWERBI_ADAPTER` | Yes | `mock` | Power BI adapter mode (`mock` or `real`). |
| `AI_PROVIDER` | Yes | `mock` | AI briefing generator mode (`mock` or `anthropic`/`gemini`). |

---

## 2. Port Mappings & Network Isolation

All exposed ports are explicitly bound to loopback `127.0.0.1` to prevent unauthorized external access.

```text
Host Interface       Container Port   Service Name       Description
---------------------------------------------------------------------------------
127.0.0.1:8000   ->  8000             eiap_api           FastAPI Backend Gateway
127.0.0.1:5678   ->  5678             eiap_n8n           n8n Workflow Automation
127.0.0.1:5433   ->  5432             eiap_postgres      PostgreSQL 16 Warehouse
127.0.0.1:8025   ->  8025             eiap_mailpit       Mailpit Web UI
127.0.0.1:1025   ->  1025             eiap_mailpit       Mailpit SMTP Port
```

---

## 3. Switching from Mock to Real Integrations

### Enabling Real Microsoft Power BI Integration
1. Set `POWERBI_ADAPTER=real` in `.env`.
2. Configure Microsoft Entra ID App Registration variables:
   ```bash
   POWERBI_TENANT_ID=<your-azure-tenant-id>
   POWERBI_CLIENT_ID=<your-entra-app-client-id>
   POWERBI_CLIENT_SECRET=<your-client-secret>
   POWERBI_WORKSPACE_ID=<your-fabric-workspace-id>
   POWERBI_DATASET_ID=<your-semantic-model-id>
   ```
3. Restart API and n8n: `docker compose restart api n8n`.

### Enabling Real External AI Services
1. Set `AI_PROVIDER=anthropic` or `AI_PROVIDER=gemini` in `.env`.
2. Provide your API key:
   ```bash
   ANTHROPIC_API_KEY=sk-ant-...
   # or
   GEMINI_API_KEY=AIzaSy...
   ```
3. The platform continues to enforce mathematical anti-hallucination guardrails; if the external LLM generates numerical values diverging $> 0.01\%$ from the SQL snapshot, it automatically falls back to the verified template.

