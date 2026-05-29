"""trigger event tables

Revision ID: 0007_trigger_event_tables
Revises: 0006_pipeline_retry_of
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_trigger_event_tables"
down_revision = "0006_pipeline_retry_of"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_group_bits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event"),
    )
    op.create_index("ix_event_group_bits_created_at", "event_group_bits", ["created_at"])
    op.create_index("ix_event_group_bits_event", "event_group_bits", ["event"])
    op.create_table(
        "emit_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emit_records_created_at", "emit_records", ["created_at"])
    op.create_index("ix_emit_records_depth", "emit_records", ["depth"])
    op.create_index("ix_emit_records_event", "emit_records", ["event"])
    op.create_index("ix_emit_records_source", "emit_records", ["source"])


def downgrade() -> None:
    op.drop_index("ix_emit_records_source", table_name="emit_records")
    op.drop_index("ix_emit_records_event", table_name="emit_records")
    op.drop_index("ix_emit_records_depth", table_name="emit_records")
    op.drop_index("ix_emit_records_created_at", table_name="emit_records")
    op.drop_table("emit_records")
    op.drop_index("ix_event_group_bits_event", table_name="event_group_bits")
    op.drop_index("ix_event_group_bits_created_at", table_name="event_group_bits")
    op.drop_table("event_group_bits")
