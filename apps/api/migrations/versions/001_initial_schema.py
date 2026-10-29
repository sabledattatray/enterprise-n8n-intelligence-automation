"""001_initial_schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-29 11:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ingestion Runs
    op.create_table(
        "ingestion_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("batch_id", sa.String(length=128), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RECEIVED"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.UniqueConstraint("source", "batch_id", name="uq_ingestion_runs_source_batch"),
    )
    op.create_index("idx_ingestion_runs_status", "ingestion_runs", ["status"])
    op.create_index("idx_ingestion_runs_corr", "ingestion_runs", ["correlation_id"])

    # 2. Raw Orders
    op.create_table(
        "raw_orders",
        sa.Column("raw_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
    )
    op.create_index("idx_raw_orders_run_id", "raw_orders", ["run_id"])
    op.create_index("idx_raw_orders_hash", "raw_orders", ["content_hash"])
    op.create_index("idx_raw_orders_source_ext", "raw_orders", ["source", "external_id"])

    # 3. Rejected Records
    op.create_table(
        "rejected_records",
        sa.Column("reject_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=True),
        sa.Column("sanitized_excerpt", sa.Text(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_rejected_records_run_id", "rejected_records", ["run_id"])
    op.create_index("idx_rejected_records_reason", "rejected_records", ["reason_code"])

    # 4. Dim Date
    op.create_table(
        "dim_date",
        sa.Column("date_key", sa.Integer(), primary_key=True),
        sa.Column("full_date", sa.Date(), nullable=False, unique=True),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("quarter", sa.SmallInteger(), nullable=False),
        sa.Column("month", sa.SmallInteger(), nullable=False),
        sa.Column("day", sa.SmallInteger(), nullable=False),
    )

    # 5. Dim Product
    op.create_table(
        "dim_product",
        sa.Column("product_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("product_code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 6. Dim Geography
    op.create_table(
        "dim_geography",
        sa.Column("geography_key", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("country_code", "region", name="uq_dim_geography"),
    )

    # 7. Fact Orders
    op.create_table(
        "fact_orders",
        sa.Column("order_key", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_order_id", sa.String(length=128), nullable=False),
        sa.Column("order_date_key", sa.Integer(), sa.ForeignKey("dim_date.date_key"), nullable=False),
        sa.Column("product_key", sa.Integer(), sa.ForeignKey("dim_product.product_key"), nullable=False),
        sa.Column("geography_key", sa.Integer(), sa.ForeignKey("dim_geography.geography_key"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("discount_amount", sa.Numeric(precision=14, scale=4), nullable=False, server_default="0.00"),
        sa.Column("revenue", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("cost", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("profit", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("order_status", sa.String(length=32), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source", "external_order_id", "product_key", name="uq_fact_orders_grain"),
        sa.CheckConstraint("quantity > 0", name="chk_fact_orders_qty_positive"),
        sa.CheckConstraint("unit_price >= 0", name="chk_fact_orders_price_nonneg"),
        sa.CheckConstraint("discount_amount >= 0", name="chk_fact_orders_discount_nonneg"),
    )
    op.create_index("idx_fact_orders_date", "fact_orders", ["order_date_key"])
    op.create_index("idx_fact_orders_currency", "fact_orders", ["currency_code"])
    op.create_index("idx_fact_orders_status", "fact_orders", ["order_status"])

    # 8. KPI Snapshots
    op.create_table(
        "kpi_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency_code", sa.String(length=8), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("cost", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("profit", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("orders", sa.Integer(), nullable=False),
        sa.Column("margin_pct", sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column("quality_score", sa.Numeric(precision=5, scale=2), nullable=False, server_default="100.00"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.run_id"), nullable=True),
    )
    op.create_index("idx_kpi_snapshots_period", "kpi_snapshots", ["period_start", "period_end", "currency_code"])

    # 9. Anomaly Events
    op.create_table(
        "anomaly_events",
        sa.Column("anomaly_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("kpi_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("observed_value", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("baseline_value", sa.Numeric(precision=16, scale=4), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="WARNING"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_anomaly_events_rule", "anomaly_events", ["rule_id", "status"])

    # 10. Workflow Executions
    op.create_table(
        "workflow_executions",
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_name", sa.String(length=128), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.run_id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("sanitized_error_code", sa.String(length=64), nullable=True),
    )
    op.create_index("idx_wf_exec_corr", "workflow_executions", ["correlation_id"])
    op.create_index("idx_wf_exec_status", "workflow_executions", ["status"])

    # 11. Report Dispatches
    op.create_table(
        "report_dispatches",
        sa.Column("dispatch_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_id", sa.String(length=128), nullable=False),
        sa.Column("recipient_hash", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default="EMAIL"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="SENT"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("report_id", "recipient_hash", name="uq_report_dispatch"),
    )

    # 12. Integration Events
    op.create_table(
        "integration_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ingestion_runs.run_id"), nullable=True),
        sa.Column("integration_type", sa.String(length=64), nullable=False),
        sa.Column("external_request_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_integ_events_type_status", "integration_events", ["integration_type", "status"])


def downgrade() -> None:
    op.drop_table("integration_events")
    op.drop_table("report_dispatches")
    op.drop_table("workflow_executions")
    op.drop_table("anomaly_events")
    op.drop_table("kpi_snapshots")
    op.drop_table("fact_orders")
    op.drop_table("dim_geography")
    op.drop_table("dim_product")
    op.drop_table("dim_date")
    op.drop_table("rejected_records")
    op.drop_table("raw_orders")
    op.drop_table("ingestion_runs")

