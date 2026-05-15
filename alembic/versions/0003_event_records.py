"""event records

Revision ID: 0003_event_records
Revises: 0002_pipeline_runs
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_event_records"
down_revision = "0002_pipeline_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("normalized_keywords", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("heat_score", sa.Integer(), nullable=False),
        sa.Column("heat_score_components", sa.JSON(), nullable=False),
        sa.Column("contradiction", sa.Boolean(), nullable=False),
        sa.Column("evidence_analysis_ids", sa.JSON(), nullable=False),
        sa.Column("evidence_raw_item_ids", sa.JSON(), nullable=False),
        sa.Column("source_names", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_records_stock_code"), "event_records", ["stock_code"], unique=False)
    op.create_index(op.f("ix_event_records_status"), "event_records", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_records_status"), table_name="event_records")
    op.drop_index(op.f("ix_event_records_stock_code"), table_name="event_records")
    op.drop_table("event_records")
