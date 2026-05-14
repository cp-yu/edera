"""pipeline run records

Revision ID: 0002_pipeline_runs
Revises: 0001_initial
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_pipeline_runs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pipeline_runs_cycle_id"), "pipeline_runs", ["cycle_id"], unique=True)
    op.create_index(op.f("ix_pipeline_runs_started_at"), "pipeline_runs", ["started_at"], unique=False)
    op.create_index(op.f("ix_pipeline_runs_status"), "pipeline_runs", ["status"], unique=False)
    op.create_index(op.f("ix_pipeline_runs_trigger"), "pipeline_runs", ["trigger"], unique=False)
    op.create_table(
        "node_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_id", sa.String(), nullable=False),
        sa.Column("node_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["cycle_id"], ["pipeline_runs.cycle_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_node_runs_cycle_id"), "node_runs", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_node_runs_node_name"), "node_runs", ["node_name"], unique=False)
    op.create_index(op.f("ix_node_runs_status"), "node_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_node_runs_status"), table_name="node_runs")
    op.drop_index(op.f("ix_node_runs_node_name"), table_name="node_runs")
    op.drop_index(op.f("ix_node_runs_cycle_id"), table_name="node_runs")
    op.drop_table("node_runs")
    op.drop_index(op.f("ix_pipeline_runs_trigger"), table_name="pipeline_runs")
    op.drop_index(op.f("ix_pipeline_runs_status"), table_name="pipeline_runs")
    op.drop_index(op.f("ix_pipeline_runs_started_at"), table_name="pipeline_runs")
    op.drop_index(op.f("ix_pipeline_runs_cycle_id"), table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
