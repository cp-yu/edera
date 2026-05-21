"""node output entities

Revision ID: 0005_node_outputs
Revises: 0004_raw_item_tags
Create Date: 2026-05-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_node_outputs"
down_revision = "0004_raw_item_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "node_outputs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("cycle_id", sa.String(), nullable=False),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id"),
        sa.UniqueConstraint("type", "url", name="uq_node_outputs_type_url"),
    )
    op.create_index("ix_node_outputs_created_at", "node_outputs", ["created_at"])
    op.create_index("ix_node_outputs_cycle_id", "node_outputs", ["cycle_id"])
    op.create_index("ix_node_outputs_node_id", "node_outputs", ["node_id"])
    op.create_index("ix_node_outputs_session_id", "node_outputs", ["session_id"])
    op.create_index("ix_node_outputs_type", "node_outputs", ["type"])


def downgrade() -> None:
    op.drop_index("ix_node_outputs_type", table_name="node_outputs")
    op.drop_index("ix_node_outputs_session_id", table_name="node_outputs")
    op.drop_index("ix_node_outputs_node_id", table_name="node_outputs")
    op.drop_index("ix_node_outputs_cycle_id", table_name="node_outputs")
    op.drop_index("ix_node_outputs_created_at", table_name="node_outputs")
    op.drop_table("node_outputs")
