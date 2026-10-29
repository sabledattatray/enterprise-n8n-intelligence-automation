-- ==============================================================================
-- Enterprise Intelligence Automation Platform (EIAP) - Baseline Warehouse Schema
-- Version: 1.0.0 | PostgreSQL 16
-- ==============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Ingestion Runs (Batch orchestration metadata & idempotency ledger)
CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(64) NOT NULL,
    batch_id VARCHAR(128) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    schema_version VARCHAR(16) NOT NULL DEFAULT '1.0',
    status VARCHAR(32) NOT NULL DEFAULT 'RECEIVED', -- RECEIVED, VALIDATED, COMMITTED, FAILED
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    total_rows INTEGER NOT NULL DEFAULT 0,
    accepted_rows INTEGER NOT NULL DEFAULT 0,
    rejected_rows INTEGER NOT NULL DEFAULT 0,
    duplicate_rows INTEGER NOT NULL DEFAULT 0,
    correlation_id VARCHAR(128) NOT NULL,
    CONSTRAINT uq_ingestion_runs_source_batch UNIQUE (source, batch_id)
);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status ON ingestion_runs(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_corr ON ingestion_runs(correlation_id);

-- 2. Raw Orders (Immutable staging with JSONB payload and row hash)
CREATE TABLE IF NOT EXISTS raw_orders (
    raw_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,
    external_id VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING' -- PENDING, VALIDATED, QUARANTINED, COMMITTED
);
CREATE INDEX IF NOT EXISTS idx_raw_orders_run_id ON raw_orders(run_id);
CREATE INDEX IF NOT EXISTS idx_raw_orders_hash ON raw_orders(content_hash);
CREATE INDEX IF NOT EXISTS idx_raw_orders_source_ext ON raw_orders(source, external_id);

-- 3. Rejected Records (Quarantine store for bad/malformed data)
CREATE TABLE IF NOT EXISTS rejected_records (
    reject_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES ingestion_runs(run_id) ON DELETE CASCADE,
    source VARCHAR(64) NOT NULL,
    external_id VARCHAR(128),
    reason_code VARCHAR(64) NOT NULL,
    field_name VARCHAR(64),
    sanitized_excerpt TEXT,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS idx_rejected_records_run_id ON rejected_records(run_id);
CREATE INDEX IF NOT EXISTS idx_rejected_records_reason ON rejected_records(reason_code);

-- 4. Date Dimension
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY, -- YYYYMMDD
    full_date DATE NOT NULL UNIQUE,
    year SMALLINT NOT NULL,
    quarter SMALLINT NOT NULL,
    month SMALLINT NOT NULL,
    day SMALLINT NOT NULL
);

-- 5. Product Dimension
CREATE TABLE IF NOT EXISTS dim_product (
    product_key SERIAL PRIMARY KEY,
    product_code VARCHAR(64) NOT NULL UNIQUE,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 6. Geography Dimension
CREATE TABLE IF NOT EXISTS dim_geography (
    geography_key SERIAL PRIMARY KEY,
    country_code VARCHAR(8) NOT NULL,
    region VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_dim_geography UNIQUE (country_code, region)
);

-- 7. Fact Orders (Curated transactional fact grain)
CREATE TABLE IF NOT EXISTS fact_orders (
    order_key UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(64) NOT NULL,
    external_order_id VARCHAR(128) NOT NULL,
    order_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),
    product_key INTEGER NOT NULL REFERENCES dim_product(product_key),
    geography_key INTEGER NOT NULL REFERENCES dim_geography(geography_key),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(14, 4) NOT NULL CHECK (unit_price >= 0),
    discount_amount NUMERIC(14, 4) NOT NULL DEFAULT 0.00 CHECK (discount_amount >= 0),
    revenue NUMERIC(14, 4) NOT NULL,
    cost NUMERIC(14, 4) NOT NULL,
    profit NUMERIC(14, 4) NOT NULL,
    currency_code VARCHAR(8) NOT NULL,
    order_status VARCHAR(32) NOT NULL,
    source_updated_at TIMESTAMPTZ,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT uq_fact_orders_grain UNIQUE (source, external_order_id, product_key)
);
CREATE INDEX IF NOT EXISTS idx_fact_orders_date ON fact_orders(order_date_key);
CREATE INDEX IF NOT EXISTS idx_fact_orders_currency ON fact_orders(currency_code);
CREATE INDEX IF NOT EXISTS idx_fact_orders_status ON fact_orders(order_status);

-- 8. KPI Snapshots (Curated aggregated business metrics)
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    currency_code VARCHAR(8) NOT NULL,
    revenue NUMERIC(16, 4) NOT NULL,
    cost NUMERIC(16, 4) NOT NULL,
    profit NUMERIC(16, 4) NOT NULL,
    orders INTEGER NOT NULL,
    margin_pct NUMERIC(8, 4) NOT NULL,
    quality_score NUMERIC(5, 2) NOT NULL DEFAULT 100.00,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    source_run_id UUID REFERENCES ingestion_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_kpi_snapshots_period ON kpi_snapshots(period_start, period_end, currency_code);

-- 9. Anomaly Events
CREATE TABLE IF NOT EXISTS anomaly_events (
    anomaly_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id UUID NOT NULL REFERENCES kpi_snapshots(snapshot_id) ON DELETE CASCADE,
    rule_id VARCHAR(64) NOT NULL,
    metric VARCHAR(64) NOT NULL,
    observed_value NUMERIC(16, 4) NOT NULL,
    baseline_value NUMERIC(16, 4) NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'WARNING', -- INFO, WARNING, CRITICAL
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN', -- OPEN, ACKNOWLEDGED, RESOLVED, SUPPRESSED
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    acknowledged_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_anomaly_events_rule ON anomaly_events(rule_id, status);

-- 10. Workflow Executions (Audit ledger for n8n executions & API steps)
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    correlation_id VARCHAR(128) NOT NULL,
    workflow_name VARCHAR(128) NOT NULL,
    run_id UUID REFERENCES ingestion_runs(run_id),
    status VARCHAR(32) NOT NULL, -- RUNNING, SUCCESS, FAILED, RETRIED
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER,
    sanitized_error_code VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS idx_wf_exec_corr ON workflow_executions(correlation_id);
CREATE INDEX IF NOT EXISTS idx_wf_exec_status ON workflow_executions(status);

-- 11. Report Dispatches
CREATE TABLE IF NOT EXISTS report_dispatches (
    dispatch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id VARCHAR(128) NOT NULL,
    recipient_hash VARCHAR(64) NOT NULL, -- SHA-256 of recipient email (PII protection)
    channel VARCHAR(32) NOT NULL DEFAULT 'EMAIL',
    status VARCHAR(32) NOT NULL DEFAULT 'SENT', -- SENT, FAILED, RETRYING
    attempts INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    sent_at TIMESTAMPTZ,
    CONSTRAINT uq_report_dispatch UNIQUE (report_id, recipient_hash)
);

-- 12. Integration Events (Power BI & External Adapter audit log)
CREATE TABLE IF NOT EXISTS integration_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES ingestion_runs(run_id),
    integration_type VARCHAR(64) NOT NULL, -- POWER_BI, AI_SUMMARY, SMTP
    external_request_id VARCHAR(128),
    status VARCHAR(32) NOT NULL, -- QUEUED, IN_PROGRESS, COMPLETED, FAILED
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS idx_integ_events_type_status ON integration_events(integration_type, status);

