"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "raw_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("stock_codes", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_raw_items_url"),
    )
    op.create_index(op.f("ix_raw_items_url"), "raw_items", ["url"], unique=False)
    op.create_table(
        "analysis_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_item_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("sentiment", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_quote", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("rationale", sa.String(), nullable=True),
        sa.Column("contradiction", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["raw_item_id"], ["raw_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "advices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_code", sa.String(), nullable=False),
        sa.Column("stock_name", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("source_quotes", sa.JSON(), nullable=False),
        sa.Column("source_urls", sa.JSON(), nullable=False),
        sa.Column("portfolio_snapshot", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("low_confidence", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("data_window_start", sa.DateTime(), nullable=False),
        sa.Column("data_window_end", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "briefings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_briefings_cycle_id"), "briefings", ["cycle_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_briefings_cycle_id"), table_name="briefings")
    op.drop_table("briefings")
    op.drop_table("advices")
    op.drop_table("analysis_results")
    op.drop_index(op.f("ix_raw_items_url"), table_name="raw_items")
    op.drop_table("raw_items")
