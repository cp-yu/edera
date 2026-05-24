"""pipeline retry metadata

Revision ID: 0006_pipeline_retry_of
Revises: 0005_node_outputs
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_pipeline_retry_of"
down_revision = "0005_node_outputs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pipeline_runs", sa.Column("retry_of", sa.String(), nullable=True))
    op.create_index("ix_pipeline_runs_retry_of", "pipeline_runs", ["retry_of"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_retry_of", table_name="pipeline_runs")
    op.drop_column("pipeline_runs", "retry_of")
