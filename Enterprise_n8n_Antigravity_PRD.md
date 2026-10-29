# MASTER PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Enterprise Intelligence Automation Platform (EIAP)
**Version:** 1.0 | **Date:** 2026-10-29 | **Target:** Google Antigravity implementation agent
**Repository:** `enterprise-n8n-intelligence-automation`
**Status:** Specification; not an assertion of completed implementation

## 0. Mandatory instructions to Antigravity
You are the lead solution architect, data engineer, n8n engineer, security engineer, QA engineer, technical writer, and DevOps engineer for this repository. Deliver a fully runnable, reproducible, documented open-source portfolio project. Do not fabricate screenshots, tests, performance metrics, integrations, or success claims. Do not deploy publicly, push to GitHub, spend money, create paid cloud resources, or touch existing production systems without explicit user approval. Work in small, reviewable phases; run tests and provide evidence before requesting authorization for the next stage. Never commit secrets, tokens, production data, personal information, or exported n8n credentials. Use synthetic datasets and mockable adapters by default. Confirm versions and capabilities from official documentation before choosing exact implementation details; pin tested versions and document the verification date.

## 1. Product vision and outcomes
Create an enterprise-grade, self-hosted automation platform that ingests business events and files, validates and normalizes records, loads a SQL analytics store idempotently, calculates trusted KPIs, orchestrates Power BI refresh when configured, detects business anomalies, produces grounded AI summaries, distributes approved reports, and monitors operational health. The repository must demonstrate business intelligence engineering, workflow automation, API integration, resilience, observability, testing, security, and professional documentation.

### Primary audience
- Recruiters and hiring managers evaluating Senior MIS, BI, Analytics Engineering, Data Engineering, and Automation Engineering skills.
- Engineers seeking a reproducible reference implementation.
- Portfolio reviewers who need to understand architecture and verify the demo in under 15 minutes.

### Success criteria
1. A reviewer can clone the repo, configure local sample environment, start services, seed synthetic data, and execute a full mock-mode pipeline using documented commands.
2. Each of eight n8n workflows can be imported or provisioned using a version-compatible, documented process and executes successfully in the supported local stack.
3. Ingestion is idempotent; replaying an identical batch does not duplicate accepted business records.
4. Validation, lineage, run IDs, reject reasons, reconciliation, retries, and alerts are observable.
5. SQL KPIs reconcile against independent expected values from deterministic fixture data.
6. Power BI and AI external integrations are optional, disabled by default, and use mocks for CI.
7. No secrets or private data appear in commits, logs, exports, screenshots, or demo outputs.
8. CI passes linting, unit tests, integration tests, security checks, workflow validation, and documentation link checks where practical.
9. All README feature claims are backed by tests, reproducible commands, or genuine screenshots.

### Non-goals for v1
- No multi-tenant SaaS, billing, user marketplace, or customer-facing authentication product.
- No production SLAs or guaranteed exactly-once delivery across third-party systems.
- No real customer records or public production endpoints.
- No mandatory paid AI, Microsoft Fabric capacity, Power BI license, or cloud deployment.
- No autonomous execution of destructive SQL or unapproved outbound AI actions.

## 2. Technology decisions
**Orchestrator:** n8n self-hosted, pinned to a tested stable version. Prefer PostgreSQL for n8n's own internal persistence; do not share internal n8n tables with business data.
**Business analytics database:** PostgreSQL as the zero-cost, cross-platform reference implementation; optional SQL Server 2022 adapter for the author's existing environment. Both must implement a documented common data contract. Do not assume n8n has native SQL Server functionality in the installed version; use a documented secure connector or API adapter if needed.
**Integration service:** Python 3.12+ FastAPI, Pydantic, SQLAlchemy, Alembic, pytest; use version pins. Provides ingestion, validation, metrics, health, report generation, optional SQL Server access, and Power BI integration endpoints.
**Queue:** Start with standard n8n execution mode. Introduce Redis/queue mode only as a documented, separately tested optional profile if justified by load tests and supported licensing/version.
**UI:** No custom dashboard is mandatory. Provide real n8n screenshots and optional Power BI report template or lightweight HTML status view only if time permits.
**Infrastructure:** Docker Compose with separate n8n, PostgreSQL, API, and optional observability services; use health checks, persistent volumes, least-privilege service accounts, and local-only port bindings by default.
**Automation:** GitHub Actions for static checks, container build verification, automated tests, dependency scans, and secret scanning. CI must never require live Microsoft or AI credentials.
**AI:** Provider abstraction with deterministic mock summarizer. Optional real provider only with explicit credentials, data minimization, budget controls, and manual opt-in.
**Reporting:** Email adapter with Mailpit or equivalent local SMTP capture in demo mode; real SMTP requires explicit opt-in.
**Power BI:** Optional Microsoft Entra ID service-principal or supported user authorization flow, REST API calls to refresh a supported semantic model, poll refresh status, and record outcome. Clearly document licensing, permissions, tenant settings, and capacity limitations; never promise an API action is universally available.

## 3. Architecture and data flow
Sources (CSV/XLSX, simulated REST API, synthetic webhook events) -> n8n intake -> FastAPI validation/normalization -> PostgreSQL raw staging -> quality/reject checks -> transactional upsert into curated fact/dimension tables -> KPI materialization -> anomaly rules -> optional AI summary -> report generation -> local SMTP capture/optional email -> audit tables.

The optional Power BI branch triggers refresh only after curated transaction commit and successful reconciliation. Refresh completion is asynchronous and must be polled with bounded backoff. Failure in external reporting must not roll back a successful data load. All workflows use correlation IDs and preserve source-to-output lineage.

### Trust boundaries
- Public/untrusted input ends at API validation; never execute untrusted SQL, shell commands, or prompt instructions.
- n8n stores only credential references, never exported secrets.
- AI receives only preapproved, aggregated, non-sensitive metrics.
- Outbound notifications require destination allowlisting and opt-in outside local demo mode.

## 4. Functional requirements and eight workflows
### WF01 — Scheduled and webhook ingestion
Triggers: cron schedule, manual run, authenticated webhook. Inputs: fixture CSV, generated XLSX, mock REST endpoint. Parse metadata (source, batch_id, checksum, event_time, schema_version); enforce payload size and content-type limits; create ingestion run; persist raw rows and lineage; deduplicate on source + external_id + version or content hash. Return accepted/rejected counts. Use pagination and bounded concurrency for APIs. Distinguish duplicate delivery from data conflict.

### WF02 — Data validation and quality gates
Validate schema version, required fields, dates, allowed currencies, nonnegative quantity, decimal precision, unique identifiers, referential keys, valid status enumerations, null thresholds, and configurable business rules. Quarantine invalid records with sanitized reason codes; publish quality score, rejection counts, and sample IDs. Block downstream KPI publication if critical gate fails. Never silently drop invalid records.

### WF03 — Transactional SQL ETL
Stage -> normalize -> merge/upsert into dimensions and fact tables; commit atomically per batch. Use parameterized SQL, migrations, constraints, unique keys, and retry-safe operations. Maintain batch ledger, counts, row hashes, lineage, and reconciliation metrics. Implement incremental watermark logic with safe overlap windows and late-arriving record handling. Include replay, backfill, and dry-run options.

### WF04 — Power BI refresh orchestrator
After ETL success, check feature flag, dataset/workspace configuration, authorization, and refresh eligibility. Submit refresh through documented Microsoft REST API, capture request identifier, poll with capped exponential backoff, detect success/failure/timeout, and store response metadata with sensitive fields redacted. Avoid duplicate refresh requests for the same batch. Mock this workflow in local and CI modes. Include tenant and capacity prerequisites, service principal permissions, and licensing caveats in documentation.

### WF05 — KPI monitoring and anomaly detection
Calculate revenue, cost, profit, profit margin, order count, average order value, delivered share, cancellation rate, and daily trend by currency or normalized reporting basis. Never aggregate unlike currencies without explicit FX conversion and provenance. Implement deterministic rule-based alerts (e.g., relative change vs 7-day baseline with minimum sample size), suppression windows, severity, and acknowledgment status. Label anomalies as indicators, not proven root causes.

### WF06 — Grounded AI executive summary
Construct a structured, versioned JSON KPI snapshot and rule-based anomalies. Generate a concise management summary with explicit metric values, period, currency, and uncertainty. Validate model output against a schema; reject fabricated metrics, unsupported causal claims, prompt injection, or leaking raw records. Fall back to deterministic template summary if AI is disabled, unavailable, or invalid. Log model name, prompt version, latency, token/cost estimate if available, and result status; redact prompt content where necessary.

### WF07 — Report distribution
Produce a report containing period, KPIs, trend, quality status, anomalies, data freshness, refresh status, and methodology. Export HTML and optionally PDF using a supported headless renderer if validated. In local demo mode send only to Mailpit; in production-compatible configuration require an allowlist and explicit opt-in. Prevent duplicate dispatch via report_id + recipient + period key. Record delivery attempt, outcome, and retry state.

### WF08 — Failure recovery and operations
Centralize n8n error workflow plus API exception handling. Record run_id, workflow_id, step, category, retryable flag, error code, timestamps, and sanitized details. Retry only transient failures with exponential backoff and jitter, maximum attempts, and dead-letter/quarantine behavior. Permanent validation failures are never retried blindly. Support operator replay after correction and an incident summary. No infinite loops or duplicate alert storms.

## 5. Data model
Implement migrations for at least:
- `ingestion_runs(run_id UUID PK, source, batch_id, checksum, schema_version, status, started_at, ended_at, total_rows, accepted_rows, rejected_rows, duplicate_rows, correlation_id)`; unique(source,batch_id).
- `raw_orders(raw_id UUID PK, run_id FK, source, external_id, payload JSONB, content_hash, received_at, status)`.
- `rejected_records(reject_id UUID PK, run_id FK, source, external_id, reason_code, field_name, sanitized_excerpt, rejected_at)`.
- `dim_date(date_key PK, full_date, year, quarter, month, day)`.
- `dim_product(product_key PK, product_code UNIQUE, product_name, category)`.
- `dim_geography(geography_key PK, country_code, region)`.
- `fact_orders(order_key PK, source, external_order_id, order_date_key FK, product_key FK, geography_key FK, quantity, unit_price, discount_amount, revenue, cost, profit, currency_code, order_status, source_updated_at, loaded_at)` with unique(source,external_order_id,product_key) or another documented grain that correctly supports line items.
- `kpi_snapshots(snapshot_id UUID PK, period_start, period_end, currency_code, revenue, cost, profit, orders, margin_pct, quality_score, computed_at, source_run_id)`.
- `anomaly_events(anomaly_id UUID PK, snapshot_id FK, rule_id, metric, observed_value, baseline_value, severity, status, created_at, acknowledged_at)`.
- `workflow_executions(execution_id UUID PK, correlation_id, workflow_name, run_id, status, started_at, ended_at, duration_ms, sanitized_error_code)`.
- `report_dispatches(dispatch_id UUID PK, report_id, recipient_hash, channel, status, attempts, created_at, sent_at)`.
- `integration_events(event_id UUID PK, run_id, integration_type, external_request_id, status, metadata JSONB, occurred_at)`.

Use numeric/decimal for money, UTC timestamptz for events, explicit ISO currency codes, CHECK constraints, indexed FKs, retention policies, and database role separation. Do not imply FX-normalized global totals unless real FX rate provenance exists. Include schema diagram and data dictionary.

## 6. Synthetic data and deterministic demonstration
Generate seeded synthetic orders spanning at least 90 days with products, geographies, currencies, order statuses, and known anomalies. Include 100-row smoke fixture, 10k-row standard fixture, and optional 100k-row stress fixture generated locally rather than committed as huge binaries. Embed controlled defects: duplicate IDs, null product, invalid date, negative quantity, malformed currency, delayed updates, and revenue spikes. Provide expected outputs for fixtures, a reproducible seed, and a reset script that affects only demo databases. Never mix with the author's 3M-row private/local project by default.

## 7. API contract
Document OpenAPI endpoints with authentication and request/response examples:
- `GET /health/live`, `GET /health/ready`
- `POST /v1/ingestion/batches` (idempotency key, source metadata, batch payload)
- `GET /v1/ingestion/runs/{run_id}`
- `POST /v1/quality/validate/{run_id}`
- `POST /v1/etl/commit/{run_id}`
- `GET /v1/kpis?period_start=&period_end=&currency=`
- `POST /v1/anomalies/evaluate`
- `POST /v1/reports/generate`
- `POST /v1/integrations/powerbi/refresh` (feature-gated)
- `GET /v1/operations/executions/{execution_id}`

Return consistent envelopes with correlation_id, status, data, errors, and UTC timestamp. Define JSON schemas, HTTP codes, pagination, rate limiting, idempotency semantics, and API versioning. Protect non-health endpoints with local demo API key or stronger service authentication, constant-time comparisons where appropriate, and no keys in query strings.

## 8. n8n implementation standards
Use clear workflow names, consistent node naming, annotations, error paths, and subworkflow reuse when supported. Avoid brittle inline scripts; place substantial business logic in tested API code. Validate workflow JSON exports with an automated import smoke test against the pinned n8n version. Do not rely on unstable node internals. All outbound HTTP calls must have explicit timeouts, retry policy, and safe error mapping. Add execution-level correlation IDs. Export workflows without credentials and provide an environment variable mapping guide. Include screenshots of each real workflow canvas and at least one successful and one failed/recovered execution with sensitive information removed.

## 9. Security and privacy
- `.env.example` contains placeholders only; `.env`, certificates, service tokens, database dumps, and n8n encryption key are gitignored.
- Secret scan all commits and CI; rotate any accidentally exposed secret and rewrite history if needed.
- Pin dependency versions and scan container images and Python dependencies.
- Local Compose binds service ports to 127.0.0.1; do not expose n8n publicly without TLS, authentication, firewall, reverse proxy, and documented hardening.
- Least-privilege DB roles; use separate application and migration credentials.
- Validate all uploads; reject unsupported formats, oversized payloads, formula injection in spreadsheet exports, unsafe URLs/SSRF, and arbitrary file paths.
- Apply webhook authentication, request size caps, rate limits, replay protection, and idempotency.
- Redact PII, tokens, credentials, request headers, and confidential data from logs and AI prompts.
- Establish log and raw-data retention defaults; document backups, restore verification, and data deletion.
- Restrict egress and outbound recipient addresses where practical; do not silently send emails.
- Provide `SECURITY.md`, threat model, and vulnerability disclosure guidance.

## 10. Reliability and performance
Target reliable at-least-once processing with idempotent writes. Explicitly describe where exactly-once guarantees do not exist. Support bounded retries, exponential backoff with jitter, dead-letter quarantine, partial failure handling, and manual replay. Define timeout budgets and prevent unbounded parallelism. Record run throughput, batch latency, failure rate, retry count, queue depth if relevant, validation pass rate, and data freshness. Suggested non-binding local benchmark goals: 10k rows within 5 minutes on documented hardware and at least 99% expected-rule detection on synthetic anomaly fixtures; treat these as targets, not achieved claims. Measure real results and report hardware, versions, dataset, commands, percentiles, and bottlenecks. Avoid meaningless or invented percentages.

## 11. Observability
Structured JSON logs with timestamp, level, service, correlation_id, run_id, workflow, step, duration_ms, status, and sanitized error_code. Add `/metrics` or structured metric exports if feasible, plus a documented monitoring dashboard or SQL queries. Include alert thresholds for stalled batches, high rejection rate, repeated failures, Power BI refresh timeout, and report delivery failure. Document how to troubleshoot a failed workflow from run ID to raw event, validation result, and final dispatch.

## 12. GitHub repository structure
```text
enterprise-n8n-intelligence-automation/
├── README.md
├── LICENSE
├── SECURITY.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── CHANGELOG.md
├── .env.example
├── .gitignore
├── .editorconfig
├── docker-compose.yml
├── docker-compose.optional.yml
├── Makefile
├── pyproject.toml
├── requirements.lock
├── .github/
│   ├── workflows/{ci.yml,security.yml,release.yml}
│   ├── ISSUE_TEMPLATE/
│   └── PULL_REQUEST_TEMPLATE.md
├── apps/api/
│   ├── Dockerfile
│   ├── src/{main.py,config.py,auth.py,schemas/,routes/,services/,adapters/,repositories/}
│   ├── migrations/
│   └── tests/
├── workflows/
│   ├── 01-data-ingestion.json
│   ├── 02-data-quality.json
│   ├── 03-sql-etl.json
│   ├── 04-powerbi-refresh.json
│   ├── 05-kpi-monitoring.json
│   ├── 06-ai-insights.json
│   ├── 07-report-distribution.json
│   └── 08-failure-recovery.json
├── sql/{schema/,views/,seed/,queries/}
├── data/{fixtures/,expected/,generators/}
├── scripts/{bootstrap.sh,bootstrap.ps1,seed.py,smoke_test.py,reset_demo.py,export_workflows.py}
├── tests/{unit/,integration/,e2e/,contract/,performance/}
├── docs/{architecture.md,requirements.md,setup-windows.md,setup-linux.md,workflows.md,data-dictionary.md,api.md,powerbi.md,ai-safety.md,security.md,operations.md,troubleshooting.md,benchmark.md,portfolio-case-study.md}
├── assets/{architecture/,screenshots/,diagrams/,demo/}
└── powerbi/{README.md,theme.json,measures.dax}
```
Adjust layout if needed but document deviations. Do not commit fabricated `.pbix` files, empty placeholder exports, or screenshots of unimplemented features.

## 13. README and visual identity
Create a premium, technically credible GitHub landing page: clear title and subtitle; authentic screenshot of n8n canvas; architecture diagram (Mermaid source + exported SVG if appropriate); capability matrix; tech stack; 5-minute quickstart; demo commands; sample KPI output; workflow catalog; security summary; testing evidence; benchmark methodology; project tree; optional integrations; roadmap; license; and author portfolio links. Use restrained professional styling and accessible contrast. Avoid exaggerated phrases like “100% production-ready” unless verified. Badges must reflect real CI/build status. All links and screenshots must resolve. Add meaningful alt text and no stale screenshots. The portfolio case study should explain business problem, design decisions, tradeoffs, failures, and measurable results.

## 14. Testing strategy and acceptance tests
### Unit
Validate schemas, currency-safe KPI math, discount calculations, dedup keys, rule thresholds, summary schema, idempotency and retry classification.
### Integration
Exercise API + PostgreSQL migrations, staging, quarantine, upsert, KPI materialization, and report capture using isolated disposable containers.
### Workflow
Import all eight JSON files into a clean n8n instance; run triggers or documented manual test harness; verify expected node paths, error handling, and correlation IDs.
### End-to-end
1. Seed fixed dataset and run ingestion -> validation -> ETL -> KPI -> anomaly -> report.
2. Re-run same batch: no duplicate facts, no duplicate reports.
3. Inject malformed records: quarantine with reasons, correct accepted count.
4. Inject temporary API outage: bounded retry then success or dead letter.
5. Inject permanent invalid payload: no endless retry.
6. Simulate Power BI failure: data commit remains valid and integration status is recorded.
7. Simulate AI timeout or hallucinated number: deterministic fallback used.
8. Attempt unauthorized webhook/API request: rejected and safely logged.
9. Attempt unsafe file/path or malicious prompt input: no code execution or credential exposure.
10. Run clean-room setup from README on a fresh environment.
### Quality gates
All mandatory tests pass, no critical/high unresolved security findings without documented exception, no leaked credentials, migrations reversible or safely forward-only, docs and screenshots accurate, CI green, and local demo verified.

## 15. Development phases and checkpoints
**Phase 0 — Discovery and architecture:** Inspect existing working directory and Git state; confirm user-selected repository and tools; verify official docs; write ADRs, dependency/version matrix, risk register, and phased backlog. Do not overwrite existing work.
**Phase 1 — Foundation:** Compose, env templates, API skeleton, PostgreSQL, migrations, fixture generator, health endpoints, CI foundation. Gate: clean startup and unit tests.
**Phase 2 — Core data pipeline:** WF01–WF03, idempotency, validation, reconciliation, lineage. Gate: end-to-end 10k-row fixture and replay tests.
**Phase 3 — Analytics and integrations:** WF04–WF05, KPI views, anomaly rules, mock Power BI adapter. Gate: independent KPI reconciliation and mock refresh tests.
**Phase 4 — Intelligence and delivery:** WF06–WF08, AI fallback, local SMTP, failure recovery. Gate: successful report and injected-failure recovery.
**Phase 5 — Hardening:** Threat model, load tests, metrics, backup/restore docs, vulnerability scan, clean-room Windows test. Gate: evidence and no critical defects.
**Phase 6 — Portfolio release:** Real screenshots, polished README, demo, case study, release notes, GitHub repository preparation. Gate: explicit approval before pushing, publishing, or deploying.

At each gate deliver: changed files, commands executed, test output, known limitations, security impact, unresolved issues, next proposed steps, and explicit approval request for consequential actions.

## 16. Definition of done
- Eight actual exported n8n workflows exist and import in the tested version.
- All documented local demo commands work on a clean clone.
- Database migrations and fixtures are reproducible.
- End-to-end mock mode works without external credentials.
- KPI calculations reconcile with deterministic expected values.
- Retry, quarantine, failure recovery, and idempotency are demonstrated.
- Optional real Power BI and AI adapters are documented and disabled by default.
- Security review and automated checks complete with no unaddressed critical findings.
- README screenshots are real, current, and consistent with implementation.
- Repository contains no sensitive data or misleading feature claims.
- Release is held until the user explicitly authorizes GitHub push and any deployment.

## 17. Specific instructions for Antigravity's first response
Before writing application code, provide:
1. Environment inspection summary and Git status.
2. Confirmed toolchain/version compatibility and any unverified assumptions.
3. Proposed architecture, data contracts, ADRs, and threat model.
4. Detailed implementation backlog with file-level deliverables and acceptance tests.
5. Risks, open questions, and a recommendation for the smallest runnable Phase 1 slice.
6. Request for approval to start Phase 1; do not deploy, push, or connect to production resources.

## 18. Project ownership and positioning
Author branding: Datta Sable, Business Intelligence and Analytics Engineering portfolio. Suggested portfolio link: https://dattasable.com/ . Optional related portfolio: https://fabric.dattasable.com/ . Existing analytics assets may be mentioned as related work but must not be copied, modified, connected, or represented as integrated without explicit permission and verification. Use a permissive license only after the user chooses one; MIT is a reasonable candidate. All project data must be synthetic and all public evidence authentic.

**END OF MASTER PRD**
