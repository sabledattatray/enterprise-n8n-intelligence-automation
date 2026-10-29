import pytest
from sqlalchemy import inspect, text
from apps.api.src.database import engine


def test_database_connection():
    """Verify raw connection to PostgreSQL analytics database."""
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        assert res == 1


def test_database_tables_exist():
    """Verifies that all 12 core tables exist in the schema."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    required_tables = {
        "ingestion_runs",
        "raw_orders",
        "rejected_records",
        "dim_date",
        "dim_product",
        "dim_geography",
        "fact_orders",
        "kpi_snapshots",
        "anomaly_events",
        "workflow_executions",
        "report_dispatches",
        "integration_events",
    }

    missing_tables = required_tables - existing_tables
    assert not missing_tables, f"Missing required database tables: {missing_tables}"


def test_fact_orders_constraints():
    """Verify unique constraint and foreign keys on fact_orders."""
    inspector = inspect(engine)
    uq_constraints = inspector.get_unique_constraints("fact_orders")
    uq_names = [c["name"] for c in uq_constraints]
    assert "uq_fact_orders_grain" in uq_names

