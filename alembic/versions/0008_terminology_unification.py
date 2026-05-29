"""terminology unification

Revision ID: 0008_terminology_unification
Revises: 0007_trigger_event_tables
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008_terminology_unification"
down_revision = "0007_trigger_event_tables"
branch_labels = None
depends_on = None


NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    if _has_table("pipeline_runs"):
        op.rename_table("pipeline_runs", "dag_runs")
    if _has_column("dag_runs", "cycle_id") or _has_column("dag_runs", "trigger"):
        with op.batch_alter_table("dag_runs") as batch:
            if _has_column("dag_runs", "cycle_id"):
                batch.alter_column("cycle_id", new_column_name="run_id", existing_type=sa.String())
            if _has_column("dag_runs", "trigger"):
                batch.alter_column("trigger", new_column_name="source", existing_type=sa.String())
    if _has_table("dag_runs") and not _has_column("dag_runs", "dag_name"):
        with op.batch_alter_table("dag_runs") as batch:
            batch.add_column(sa.Column("dag_name", sa.String(), nullable=False, server_default="default"))
            batch.create_index("ix_dag_runs_dag_name", ["dag_name"])
    if _has_column("node_runs", "cycle_id"):
        fk_name = _node_runs_fk_name("cycle_id")
        with op.batch_alter_table("node_runs", recreate="always", naming_convention=NAMING_CONVENTION) as batch:
            if fk_name is not None:
                batch.drop_constraint(fk_name, type_="foreignkey")
            batch.alter_column("cycle_id", new_column_name="run_id", existing_type=sa.String())
        with op.batch_alter_table("node_runs", recreate="always") as batch:
            batch.create_foreign_key("fk_node_runs_run_id_dag_runs", "dag_runs", ["run_id"], ["run_id"])
    if _has_table("node_runs") and not _has_column("node_runs", "failure_kind"):
        with op.batch_alter_table("node_runs") as batch:
            batch.add_column(sa.Column("failure_kind", sa.String(), nullable=True))
            batch.create_index("ix_node_runs_failure_kind", ["failure_kind"])
    if _has_table("node_runs") and not _has_column("node_runs", "metadata"):
        with op.batch_alter_table("node_runs") as batch:
            batch.add_column(sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    for table_name in ("briefings", "node_outputs", "edge_inputs", "source_recoveries"):
        if _has_column(table_name, "cycle_id"):
            with op.batch_alter_table(table_name) as batch:
                batch.alter_column("cycle_id", new_column_name="run_id", existing_type=sa.String())


def downgrade() -> None:
    for table_name in ("source_recoveries", "edge_inputs", "node_outputs", "briefings"):
        if _has_column(table_name, "run_id"):
            with op.batch_alter_table(table_name) as batch:
                batch.alter_column("run_id", new_column_name="cycle_id", existing_type=sa.String())
    if _has_column("node_runs", "run_id"):
        fk_name = _node_runs_fk_name("run_id")
        with op.batch_alter_table("node_runs", recreate="always", naming_convention=NAMING_CONVENTION) as batch:
            if fk_name is not None:
                batch.drop_constraint(fk_name, type_="foreignkey")
            if _has_column("node_runs", "failure_kind"):
                batch.drop_index("ix_node_runs_failure_kind")
                batch.drop_column("failure_kind")
            if _has_column("node_runs", "metadata"):
                batch.drop_column("metadata")
            batch.alter_column("run_id", new_column_name="cycle_id", existing_type=sa.String())
    if _has_column("dag_runs", "source") or _has_column("dag_runs", "run_id"):
        with op.batch_alter_table("dag_runs") as batch:
            if _has_column("dag_runs", "dag_name"):
                batch.drop_index("ix_dag_runs_dag_name")
                batch.drop_column("dag_name")
            if _has_column("dag_runs", "source"):
                batch.alter_column("source", new_column_name="trigger", existing_type=sa.String())
            if _has_column("dag_runs", "run_id"):
                batch.alter_column("run_id", new_column_name="cycle_id", existing_type=sa.String())
    if _has_table("dag_runs"):
        op.rename_table("dag_runs", "pipeline_runs")
    if _has_column("node_runs", "cycle_id") and _has_table("pipeline_runs"):
        with op.batch_alter_table("node_runs", recreate="always") as batch:
            batch.create_foreign_key("fk_node_runs_cycle_id_pipeline_runs", "pipeline_runs", ["cycle_id"], ["cycle_id"])


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _node_runs_fk_name(column_name: str) -> str | None:
    for foreign_key in inspect(op.get_bind()).get_foreign_keys("node_runs"):
        if foreign_key["constrained_columns"] == [column_name]:
            name = foreign_key.get("name")
            if isinstance(name, str) and name:
                return name
            referred = str(foreign_key["referred_table"])
            return f"fk_node_runs_{column_name}_{referred}"
    return None
