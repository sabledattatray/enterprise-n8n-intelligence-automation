# Changelog: Enterprise Intelligence Automation Platform (EIAP)

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [v1.0.0] - 2026-10-29

### Added
- **Core Orchestration Stack:** Fully reproducible Docker Compose environment with PostgreSQL 16 Alpine, n8n v1.82.2, FastAPI 0.162, and Mailpit v1.23.
- **WF01 Enterprise Data Ingestion:** Automated batch ingestion supporting CSV and REST webhooks with SHA-256 batch content fingerprinting and idempotent replay protection.
- **WF02 Data Quality Engine:** Multi-tier deterministic validation rules isolating defective records (negative quantities, invalid currencies, missing keys) into `rejected_records`.
- **WF03 Transactional SQL ETL:** Dimensional star-schema loader for `dim_date`, `dim_product`, and `dim_geography` with atomic `ON CONFLICT DO UPDATE` upserts into `fact_orders`.
- **WF04 Power BI Refresh Orchestrator:** Asynchronous semantic dataset refresh polling with exponential backoff; includes both a local zero-cost mock adapter and production Microsoft Entra ID adapter.
- **WF05 KPI Monitoring & Anomaly Detection:** Single-currency parameterized SQL KPI engine evaluating revenue and margin anomalies with 24-hour alert suppression.
- **WF06 Grounded AI Executive Intelligence:** Structured 7-section executive briefing generation enforcing strict mathematical anti-hallucination verification ($\le 0.01\%$) with deterministic template fallback.
- **WF07 Automated Report Distribution:** Responsive HTML executive briefing rendering and SMTP distribution via local Mailpit with dispatch idempotency tracking.
- **WF08 Failure Recovery & Incident Management:** Failure classifier (`TRANSIENT`, `AUTH`, `VALIDATION`), time-aware delayed retry engine enforcing scheduled backoff with HTTP 429 early rejection, and 3-retry dead-letter quarantine.
- **Disaster Recovery Automation:** Point-in-time PostgreSQL custom-format dumps (`scripts/backup_database.py`) and automated isolated restore verification (`scripts/verify_restore.py`) achieving 2.39-second RTO and zero data loss.
- **Comprehensive Test Suite:** 51 passing automated tests across `tests/contract/`, `tests/unit/`, and `tests/integration/` with 0 failures and 0 warnings.
- **Performance Benchmarking Suite:** Automated latency, throughput, and query benchmarks (`scripts/benchmark_performance.py`) demonstrating sub-10ms core latencies and 1,792 rows/sec pipeline throughput.
- **Automated CI/CD Workflows:** GitHub Actions pipelines for automated test execution, dependency vulnerability audits (`pip-audit`), and workflow secret scanning.
- **Technical Documentation Package:** Complete architectural specifications, STRIDE threat models, security audits, disaster recovery runbooks, and portfolio case studies.

