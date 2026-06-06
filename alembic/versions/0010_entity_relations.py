"""entity relations

Revision ID: 0010_entity_relations
Revises: 0009_db_backed_core_entities
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0010_entity_relations"
down_revision = "0009_db_backed_core_entities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if _has_table("entity_relations"):
        return
    op.create_table(
        "entity_relations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("from_entity_id", sa.String(), nullable=False),
        sa.Column("to_entity_id", sa.String(), nullable=False),
        sa.Column("relation_type", sa.String(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("from_entity_id", "to_entity_id", "relation_type", name="uq_entity_relations_from_to_type"),
    )
    op.create_index("ix_entity_relations_from_entity_id", "entity_relations", ["from_entity_id"])
    op.create_index("ix_entity_relations_to_entity_id", "entity_relations", ["to_entity_id"])
    op.create_index("ix_entity_relations_relation_type", "entity_relations", ["relation_type"])
    op.create_index("ix_entity_relations_created_at", "entity_relations", ["created_at"])
    op.create_index("ix_entity_relations_updated_at", "entity_relations", ["updated_at"])


def downgrade() -> None:
    if _has_table("entity_relations"):
        op.drop_table("entity_relations")


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()
