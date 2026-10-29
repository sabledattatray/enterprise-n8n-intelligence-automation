# Credential Management Standard: Enterprise Intelligence Automation Platform (EIAP)

**Document Version:** 1.0.0  
**Target Platform:** Enterprise n8n Intelligence Automation Platform  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Audited & Verified:** October 2026  

---

## 1. Secret Hierarchy & Architecture

The Enterprise Intelligence Automation Platform (EIAP) implements strict cryptographic separation between code, runtime configuration, and persistent secrets.

```mermaid
graph TD
    subgraph Secret Storage & Environment
        ENV[".env (Strictly Excluded from Git)"]
        VAULT["Production Vault (Azure Key Vault / AWS KMS)"]
    end

    subgraph Service Injection
        API[FastAPI Container]
        N8N[n8n Workflow Engine]
        PG[PostgreSQL Container]
    end

    subgraph Workflow Execution
        W1[WF01 - WF08 HTTP Nodes]
        CRED[n8n Credential Store<br/>AES-256 Encrypted via N8N_ENCRYPTION_KEY]
    end

    ENV -.->|Local Dev| API
    ENV -.->|Local Dev| N8N
    ENV -.->|Local Dev| PG
    VAULT -.->|Production Cloud| API
    VAULT -.->|Production Cloud| N8N

    N8N --> CRED
    CRED --> W1
    N8N -->|={{ $env.API_KEY }}| W1
```

### Classification of Platform Secrets

| Secret Identifier | Classification | Scope | Storage Mechanism | Default in Production |
| :--- | :--- | :--- | :--- | :--- |
| `API_KEY` | High | API Ingress Authentication | `.env` / Process Env | Rotated 256-bit Hex Key |
| `WEBHOOK_SECRET` | High | Ingestion HMAC Validation | `.env` / Process Env | Cryptographic Secret String |
| `POSTGRES_PASSWORD` | Critical | Database Superuser Access | `.env` / Compose Secret | 32-Character Alphanumeric |
| `N8N_ENCRYPTION_KEY` | Critical | n8n Credential Store Key | `.env` / Compose Secret | 32-Character Fixed AES Key |
| `POWERBI_CLIENT_SECRET` | Critical | Microsoft Entra ID Token | `.env` (Optional) | Blank (Mock Adapter Active) |
| `ANTHROPIC_API_KEY` | High | External AI Briefing API | `.env` (Optional) | Blank (Template Mock Active) |

---

## 2. Zero Secret Exposure Guarantee

### Rule 1: No Hardcoded Secrets in Workflow Exports
Exported n8n workflow JSON files (`workflows/*.json`) must **never** contain inline API tokens, bearer keys, or database credentials.
- All HTTP Request nodes use dynamic expressions referencing container environment variables:
  ```json
  "headerParameters": {
    "parameters": [
      {
        "name": "X-API-Key",
        "value": "={{ $env.API_KEY }}"
      }
    ]
  }
  ```
- This architecture enables workflow definitions to be published to public GitHub repositories without redaction or security risk.

### Rule 2: Automated Pre-Commit Secret Scanning
The platform includes an automated scanning suite (`scripts/verify_workflow_sanitization.py`) that checks for:
- API key prefixes (`eiap_live_sec_key_`)
- Database passwords (`eiap_local_secure_pass_`)
- Webhook signatures
- Private cryptographic keys (`-----BEGIN PRIVATE KEY-----`)

---

## 3. Credential Rotation Procedures

### 3.1: API Key Rotation Runbook
To rotate the platform ingress API key with zero downtime:

1. **Generate Cryptographic Key:**
   ```powershell
   .\.venv\Scripts\python.exe -c "import secrets; print('eiap_live_sec_key_' + secrets.token_hex(16))"
   ```
2. **Update `.env` Configuration:**
   Replace the `API_KEY` entry with the newly generated value:
   ```bash
   API_KEY=eiap_live_sec_key_<new_token>
   ```
3. **Restart API and n8n Services:**
   ```powershell
   docker compose up -d --no-deps api n8n
   ```
4. **Verify Key Activation:**
   ```powershell
   # Test rejection of retired key (Expect HTTP 403)
   curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: <old_key>" http://127.0.0.1:8000/v1/operations/health
   # Test acceptance of active key (Expect HTTP 200)
   curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: <new_key>" http://127.0.0.1:8000/v1/operations/health
   ```
5. **Run Test Regression:**
   ```powershell
   .\.venv\Scripts\pytest.exe tests/unit/test_auth.py -v
   ```

### 3.2: Database Password Rotation Runbook
1. Update database role password inside running PostgreSQL instance:
   ```bash
   docker exec -it eiap_postgres psql -U eiap_admin -d business_analytics -c "ALTER USER eiap_admin WITH PASSWORD '<new_password>';"
   ```
2. Update `POSTGRES_PASSWORD` and connection strings in `.env`.
3. Restart `eiap_api` and `eiap_n8n` to establish new connection pools:
   ```powershell
   docker compose restart api n8n
   ```

---

## 4. Local Developer Ergonomics (Zero-Cost Design)

To allow reviewers, interviewers, and team members to clone and test the entire platform in seconds without requiring cloud accounts:
1. **`.env.example` Provided:** Contains functional local development defaults.
2. **Mock Adapters Enabled by Default:**
   - `POWERBI_ADAPTER=mock`: Emulates Entra ID token issuance and refresh polling without Azure subscription.
   - `AI_PROVIDER=mock`: Generates deterministic, mathematically grounded 7-section briefings with 0 token costs.
   - `SMTP_HOST=mailpit`: Traps all outbound HTML reports locally on `127.0.0.1:8025` without spam risk.

