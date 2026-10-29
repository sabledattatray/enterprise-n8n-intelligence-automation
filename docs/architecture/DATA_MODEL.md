# Data Architecture & Star Schema Model: EIAP

**Document Version:** 1.0.0  
**Target Platform:** Enterprise n8n Intelligence Automation Platform  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Repository:** [https://github.com/sabledattatray/enterprise-n8n-intelligence-automation](https://github.com/sabledattatray/enterprise-n8n-intelligence-automation)  

---

## 1. Relational Star Schema Entity Relationship Diagram

The analytical warehouse (`business_analytics`) employs a dimensional star schema optimized for fast analytical aggregations, financial precision, and referential integrity.

```mermaid
erDiagram
    fact_orders }o--|| dim_date : "order_date_key -> date_key"
    fact_orders }o--|| dim_product : "product_key -> product_key"
    fact_orders }o--|| dim_geography : "geography_key -> geography_key"
    
    ingestion_runs ||--o{ raw_orders : "run_id -> run_id"
    ingestion_runs ||--o{ rejected_records : "run_id -> run_id"
    ingestion_runs ||--o{ kpi_snapshots : "run_id -> source_run_id"
    
    kpi_snapshots ||--o{ anomaly_events : "snapshot_id -> snapshot_id"
    kpi_snapshots ||--o{ ai_summaries : "snapshot_id -> snapshot_id"
    kpi_snapshots ||--o{ report_dispatches : "snapshot_id -> snapshot_id"

    dim_date {
        int date_key PK "YYYYMMDD integer surrogate"
        date full_date "Unique calendar date"
        smallint year "Calendar year"
        smallint quarter "1 - 4"
        smallint month "1 - 12"
        smallint day "1 - 31"
    }

    dim_product {
        int product_key PK "Autoincrement surrogate"
        varchar product_code UK "PROD-ENT-001"
        varchar product_name "Product title"
        varchar category "Software, AI, Security"
        timestamptz created_at
    }

    dim_geography {
        int geography_key PK "Autoincrement surrogate"
        varchar country_code "US, GB, DE, SG, JP, AU"
        varchar region "North America, Europe, APAC"
        timestamptz created_at
    }

    fact_orders {
        uuid order_key PK "UUID surrogate"
        varchar source "CSV or REST_API"
        varchar external_order_id "Business order ID"
        int order_date_key FK "References dim_date"
        int product_key FK "References dim_product"
        int geography_key FK "References dim_geography"
        int quantity "Order quantity > 0"
        numeric unit_price "Numeric(14,4)"
        numeric discount_amount "Numeric(14,4) >= 0"
        numeric revenue "Numeric(14,4) = (qty * price) - discount"
        numeric cost "Numeric(14,4)"
        numeric profit "Numeric(14,4) = revenue - cost"
        varchar currency_code "USD, EUR, GBP, JPY, SGD"
        varchar order_status "COMPLETED, CANCELLED, REFUNDED"
        timestamptz loaded_at
    }

    kpi_snapshots {
        uuid snapshot_id PK "UUID primary key"
        timestamptz period_start
        timestamptz period_end
        varchar currency_code "Single currency code"
        numeric revenue "Numeric(16,4)"
        numeric cost "Numeric(16,4)"
        numeric profit "Numeric(16,4)"
        int orders "Total order count"
        numeric margin_pct "Numeric(8,4)"
        numeric quality_score "Numeric(5,2)"
        timestamptz computed_at
    }

    anomaly_events {
        uuid anomaly_id PK
        uuid snapshot_id FK
        varchar rule_id "ANOM_REVENUE_SPIKE"
        varchar metric "total_revenue"
        numeric observed_value
        numeric baseline_value
        numeric deviation_pct
        varchar severity "HIGH / CRITICAL"
        varchar status "OPEN / SUPPRESSED"
    }

    operational_incidents {
        uuid incident_id PK
        varchar workflow_name
        varchar failure_category "TRANSIENT / AUTH / VALIDATION"
        varchar severity "WARNING / CRITICAL"
        varchar status "OPEN / RETRIED / RESOLVED / DEAD_LETTER"
        int retry_count "0 to 3"
        int max_retries "Default: 3"
        jsonb error_details "Audit trail & scheduled backoffs"
        timestamptz created_at
        timestamptz resolved_at
    }
```

---

## 2. Dimensional Grain & Integrity Constraints

### 1. Fact Table Grain
- **Grain:** One row per individual product item within an external business order event.
- **Uniqueness Constraint (`uq_fact_orders_grain`):**
  ```sql
  UNIQUE (source, external_order_id, product_key)
  ```
  Guarantees that re-running ingestion or ETL pipelines cannot produce duplicate fact rows. Subsequent deliveries execute idempotent `ON CONFLICT DO UPDATE`.

### 2. Strict Currency Isolation
To prevent financial distortion caused by summing across distinct exchange rates:
- `fact_orders` records the currency code directly on every transaction (`USD`, `EUR`, `GBP`, `JPY`, `SGD`).
- All analytical aggregations in `kpi_snapshots` enforce single-currency isolation:
  ```sql
  WHERE f.currency_code = :currency
  ```
- Cross-currency aggregations are strictly prevented at both the database layer and the API contract layer.

### 3. Referential Integrity & Foreign Keys
- `fact_orders.order_date_key` $\to$ `dim_date.date_key`
- `fact_orders.product_key` $\to$ `dim_product.product_key`
- `fact_orders.geography_key` $\to$ `dim_geography.geography_key`
- `anomaly_events.snapshot_id` $\to$ `kpi_snapshots.snapshot_id` (ON DELETE CASCADE)
- `rejected_records.run_id` $\to$ `ingestion_runs.run_id`

