"""skills

Revision ID: 0011_skills
Revises: 0010_entity_relations
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0011_skills"
down_revision = "0010_entity_relations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if _has_table("skills"):
        return
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("config_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_skills_name", "skills", ["name"])
    op.create_index("ix_skills_created_at", "skills", ["created_at"])
    op.create_index("ix_skills_updated_at", "skills", ["updated_at"])


def downgrade() -> None:
    if _has_table("skills"):
        op.drop_table("skills")


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()
