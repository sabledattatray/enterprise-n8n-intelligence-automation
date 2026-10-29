import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from apps.api.src.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(64), nullable=False)
    batch_id = Column(String(128), nullable=False)
    checksum = Column(String(64), nullable=False)
    schema_version = Column(String(16), nullable=False, default="1.0")
    status = Column(String(32), nullable=False, default="RECEIVED")
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    total_rows = Column(Integer, nullable=False, default=0)
    accepted_rows = Column(Integer, nullable=False, default=0)
    rejected_rows = Column(Integer, nullable=False, default=0)
    duplicate_rows = Column(Integer, nullable=False, default=0)
    correlation_id = Column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("source", "batch_id", name="uq_ingestion_runs_source_batch"),
    )

    raw_orders = relationship("RawOrder", back_populates="run", cascade="all, delete-orphan")
    rejected_records = relationship("RejectedRecord", back_populates="run", cascade="all, delete-orphan")


class RawOrder(Base):
    __tablename__ = "raw_orders"

    raw_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"), nullable=False)
    source = Column(String(64), nullable=False)
    external_id = Column(String(128), nullable=False)
    payload = Column(JSONB, nullable=False)
    content_hash = Column(String(64), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    status = Column(String(32), nullable=False, default="PENDING")

    run = relationship("IngestionRun", back_populates="raw_orders")


class RejectedRecord(Base):
    __tablename__ = "rejected_records"

    reject_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.run_id", ondelete="CASCADE"), nullable=False)
    source = Column(String(64), nullable=False)
    external_id = Column(String(128), nullable=True)
    reason_code = Column(String(64), nullable=False)
    field_name = Column(String(64), nullable=True)
    sanitized_excerpt = Column(Text, nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    run = relationship("IngestionRun", back_populates="rejected_records")


class DimDate(Base):
    __tablename__ = "dim_date"

    date_key = Column(Integer, primary_key=True)  # YYYYMMDD
    full_date = Column(Date, nullable=False, unique=True)
    year = Column(SmallInteger, nullable=False)
    quarter = Column(SmallInteger, nullable=False)
    month = Column(SmallInteger, nullable=False)
    day = Column(SmallInteger, nullable=False)


class DimProduct(Base):
    __tablename__ = "dim_product"

    product_key = Column(Integer, primary_key=True, autoincrement=True)
    product_code = Column(String(64), nullable=False, unique=True)
    product_name = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class DimGeography(Base):
    __tablename__ = "dim_geography"

    geography_key = Column(Integer, primary_key=True, autoincrement=True)
    country_code = Column(String(8), nullable=False)
    region = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("country_code", "region", name="uq_dim_geography"),
    )


class FactOrder(Base):
    __tablename__ = "fact_orders"

    order_key = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(64), nullable=False)
    external_order_id = Column(String(128), nullable=False)
    order_date_key = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False)
    product_key = Column(Integer, ForeignKey("dim_product.product_key"), nullable=False)
    geography_key = Column(Integer, ForeignKey("dim_geography.geography_key"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(14, 4), nullable=False)
    discount_amount = Column(Numeric(14, 4), nullable=False, default=0.00)
    revenue = Column(Numeric(14, 4), nullable=False)
    cost = Column(Numeric(14, 4), nullable=False)
    profit = Column(Numeric(14, 4), nullable=False)
    currency_code = Column(String(8), nullable=False)
    order_status = Column(String(32), nullable=False)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    loaded_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("source", "external_order_id", "product_key", name="uq_fact_orders_grain"),
    )


class KPISnapshot(Base):
    __tablename__ = "kpi_snapshots"

    snapshot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    currency_code = Column(String(8), nullable=False)
    revenue = Column(Numeric(16, 4), nullable=False)
    cost = Column(Numeric(16, 4), nullable=False)
    profit = Column(Numeric(16, 4), nullable=False)
    orders = Column(Integer, nullable=False)
    margin_pct = Column(Numeric(8, 4), nullable=False)
    quality_score = Column(Numeric(5, 2), nullable=False, default=100.00)
    computed_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    source_run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.run_id"), nullable=True)

    anomalies = relationship("AnomalyEvent", back_populates="snapshot", cascade="all, delete-orphan")


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    anomaly_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("kpi_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False)
    rule_id = Column(String(64), nullable=False)
    metric = Column(String(64), nullable=False)
    observed_value = Column(Numeric(16, 4), nullable=False)
    baseline_value = Column(Numeric(16, 4), nullable=False)
    severity = Column(String(16), nullable=False, default="WARNING")
    status = Column(String(32), nullable=False, default="OPEN")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    snapshot = relationship("KPISnapshot", back_populates="anomalies")


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    execution_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False)
    workflow_name = Column(String(128), nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.run_id"), nullable=True)
    status = Column(String(32), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    sanitized_error_code = Column(String(64), nullable=True)


class ReportDispatch(Base):
    __tablename__ = "report_dispatches"

    dispatch_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(String(128), nullable=False)
    recipient_hash = Column(String(64), nullable=False)
    channel = Column(String(32), nullable=False, default="EMAIL")
    subject = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="SENT")
    attempts = Column(Integer, nullable=False, default=1)
    metadata_json = Column(JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    sent_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("report_id", "recipient_hash", name="uq_report_dispatch"),
    )


class IntegrationEvent(Base):
    __tablename__ = "integration_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.run_id"), nullable=True)
    integration_type = Column(String(64), nullable=False)
    external_request_id = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False)
    metadata_json = Column(JSONB, nullable=False, default={})
    occurred_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class AISummary(Base):
    __tablename__ = "ai_summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("kpi_snapshots.snapshot_id", ondelete="CASCADE"), nullable=False)
    model_provider = Column(String(64), nullable=False)
    model_name = Column(String(64), nullable=False)
    prompt_version = Column(String(32), nullable=False)
    content_json = Column(JSONB, nullable=False)
    validation_status = Column(String(32), nullable=False)
    grounding_checks = Column(JSONB, nullable=False)
    token_count = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class OperationalIncident(Base):
    __tablename__ = "operational_incidents"

    incident_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_name = Column(String(128), nullable=False)
    execution_id = Column(String(64), nullable=True)
    correlation_id = Column(String(128), nullable=False)
    failure_category = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False, default="WARNING")
    status = Column(String(32), nullable=False, default="OPEN")
    error_code = Column(String(64), nullable=False)
    error_message = Column(Text, nullable=False)
    error_details = Column(JSONB, nullable=False, default={})
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    last_retried_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


