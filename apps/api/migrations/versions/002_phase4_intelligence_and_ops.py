"""002_phase4_intelligence_and_ops

Revision ID: 002_phase4_intelligence_and_ops
Revises: 001_initial_schema
Create Date: 2026-10-29 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_phase4_intelligence_and_ops"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. AI Summaries Table
    op.create_table(
        "ai_summaries",
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kpi_snapshots.snapshot_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_provider", sa.String(length=64), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_status", sa.String(length=32), nullable=False),
        sa.Column("grounding_checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_summaries_snapshot_id", "ai_summaries", ["snapshot_id"])

    # 2. Operational Incidents Table
    op.create_table(
        "operational_incidents",
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_name", sa.String(length=128), nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("failure_category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="WARNING"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="OPEN"),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("error_details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_retried_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_operational_incidents_status", "operational_incidents", ["status"])
    op.create_index("ix_operational_incidents_correlation_id", "operational_incidents", ["correlation_id"])

    # 3. Extend report_dispatches with subject and metadata_json
    op.add_column("report_dispatches", sa.Column("subject", sa.String(length=255), nullable=True))
    op.add_column(
        "report_dispatches",
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("report_dispatches", "metadata_json")
    op.drop_column("report_dispatches", "subject")
    op.drop_index("ix_operational_incidents_correlation_id", table_name="operational_incidents")
    op.drop_index("ix_operational_incidents_status", table_name="operational_incidents")
    op.drop_table("operational_incidents")
    op.drop_index("ix_ai_summaries_snapshot_id", table_name="ai_summaries")
    op.drop_table("ai_summaries")

