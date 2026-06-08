"""add input mapping entity type

Revision ID: 0012_add_input_mapping_entity_type
Revises: 0011_skills
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0012_add_input_mapping_entity_type"
down_revision = "0011_skills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if _has_table("entity_input_mapping"):
        return
    op.create_table(
        "entity_input_mapping",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("shared", sa.JSON(), nullable=False),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("append_nodes", sa.JSON(), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id"),
        sa.UniqueConstraint("name", name="uq_entity_input_mapping_name"),
    )
    op.create_index("ix_entity_input_mapping_entity_id", "entity_input_mapping", ["entity_id"])
    op.create_index("ix_entity_input_mapping_name", "entity_input_mapping", ["name"])
    op.create_index("ix_entity_input_mapping_created_at", "entity_input_mapping", ["created_at"])
    op.create_index("ix_entity_input_mapping_updated_at", "entity_input_mapping", ["updated_at"])


def downgrade() -> None:
    if _has_table("entity_input_mapping"):
        op.drop_table("entity_input_mapping")


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()
