# Platform Architecture: Enterprise Intelligence Automation Platform (EIAP)

**Document Version:** 1.0.0  
**Target Platform:** Enterprise n8n Intelligence Automation Platform  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Repository:** [https://github.com/sabledattatray/enterprise-n8n-intelligence-automation](https://github.com/sabledattatray/enterprise-n8n-intelligence-automation)  

---

## 1. System Topology & Integration Boundaries

The Enterprise Intelligence Automation Platform (EIAP) is an enterprise-grade, event-driven data engineering, business intelligence, and automated operations platform. The entire stack runs within reproducible, isolated Docker containers pinned to localhost (`127.0.0.1`), requiring zero paid cloud dependencies for full functional verification.

```mermaid
flowchart TB
    subgraph External Sources & Clients
        SRC1[CSV Enterprise Feeds]
        SRC2[External REST APIs]
        ADMIN[Data Ops & DevOps Engineers]
        BI_USER[Executive & BI Stakeholders]
    end

    subgraph Ingress & Gateway Layer
        API[FastAPI Gateway :8000<br/>Authentication & Middleware]
        AUTH[X-API-Key Validator & HMAC Checker]
        CORR[CorrelationIdMiddleware]
    end

    subgraph Workflow Orchestration Engine
        N8N[n8n Automation Engine :5678]
        TR[Isolated n8n Task Runners]
        WF01[WF01: Ingestion Engine]
        WF02[WF02: Quality Engine]
        WF03[WF03: SQL ETL Engine]
        WF04[WF04: Power BI Orchestrator]
        WF05[WF05: KPI Monitor & Anomaly Alert]
        WF06[WF06: AI Executive Intelligence]
        WF07[WF07: Report Dispatcher]
        WF08[WF08: Incident Recovery]
    end

    subgraph Storage & Analytics Warehouse
        PG[(PostgreSQL 16 Engine :5433)]
        subgraph Databases
            DB_ANALYTICS[business_analytics DB<br/>Star Schema & Operations]
            DB_N8N[n8n_internal DB<br/>Workflow State & Executions]
        end
    end

    subgraph Downstream Integration Gateways
        PBI_GATEWAY{Power BI Adapter}
        PBI_MOCK[Verified Mock Adapter]
        PBI_REAL[Microsoft Entra ID REST API]
        
        AI_GATEWAY{AI Intelligence Adapter}
        AI_MOCK[Deterministic Template Fallback]
        AI_REAL[External LLM Gateway]

        SMTP_GATEWAY[Mailpit SMTP Service :1025<br/>Web Inspection UI :8025]
    end

    SRC1 -->|File Ingestion| API
    SRC2 -->|Webhook Ingress| API
    ADMIN -->|Operations CLI & REST| API
    
    API --> AUTH
    AUTH --> CORR
    CORR --> N8N

    N8N --> TR
    TR --> WF01
    TR --> WF02
    TR --> WF03
    TR --> WF04
    TR --> WF05
    TR --> WF06
    TR --> WF07
    TR --> WF08

    WF01 & WF02 & WF03 -->|psycopg3 / Parameterized SQL| DB_ANALYTICS
    WF05 & WF06 & WF07 & WF08 -->|psycopg3 / Parameterized SQL| DB_ANALYTICS
    N8N -.->|Internal State| DB_N8N
    PG --- DB_ANALYTICS
    PG --- DB_N8N

    WF04 --> PBI_GATEWAY
    PBI_GATEWAY -->|Default| PBI_MOCK
    PBI_GATEWAY -.->|Configured| PBI_REAL

    WF06 --> AI_GATEWAY
    AI_GATEWAY -->|Default| AI_MOCK
    AI_GATEWAY -.->|Configured| AI_REAL

    WF07 -->|SMTP Port 1025| SMTP_GATEWAY
    SMTP_GATEWAY -->|View Executive HTML| BI_USER
```

---

## 2. Core Architectural Pillars

### 1. Decoupled Service Isolation
- **Microservices Stack:** Managed via `docker-compose.yml` with strict health check probes (`/health/live`, `pg_isready`).
- **Network Boundaries:** All container ports (`8000`, `5678`, `5433`, `8025`, `1025`) bind explicitly to `127.0.0.1`, completely preventing local area network or WAN ingress.
- **Port Non-Interference:** PostgreSQL uses host port `5433`, preventing collision with native Windows PostgreSQL on `5432`.

### 2. Dual Database Segregation
- `business_analytics`: Contains raw staging, validation quarantine, star schema (`fact_orders`, dimensions), KPI snapshots, anomaly events, report dispatches, and incident logs.
- `n8n_internal`: Houses n8n user sessions, encrypted workflow configurations, and task execution history.

### 3. End-to-End Traceability
- Every HTTP request, task execution, and automated retry carries an immutable `X-Correlation-ID` header.
- Correlated audit logs enable exact forensic investigation from webhook trigger to database upsert and email delivery.

### 4. Zero-Cost Developer Ergonomics
- The entire platform can be cloned and run on any developer machine (Windows, macOS, Linux) with Docker Desktop.
- Mock adapters for Power BI and AI services ensure that reviewers never encounter paywalls, expired API keys, or cloud subscription blockers.

