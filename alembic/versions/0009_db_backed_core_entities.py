"""db backed core entities

Revision ID: 0009_db_backed_core_entities
Revises: 0008_terminology_unification
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009_db_backed_core_entities"
down_revision = "0008_terminology_unification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not _has_table("entity_types"):
        op.create_table(
            "entity_types",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("display_name", sa.String(), nullable=False),
            sa.Column("business_id_field", sa.String(), nullable=False),
            sa.Column("display_template", sa.String(), nullable=False),
            sa.Column("storage_tier", sa.String(), nullable=False),
            sa.Column("table_name", sa.String(), nullable=True),
            sa.Column("schema_version", sa.Integer(), nullable=False),
            sa.Column("system_protected", sa.Boolean(), nullable=False),
            sa.Column("schema_json", sa.JSON(), nullable=False),
            sa.Column("field_permissions", sa.JSON(), nullable=False),
            sa.Column("validate", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
        op.create_index("ix_entity_types_name", "entity_types", ["name"])
        op.create_index("ix_entity_types_storage_tier", "entity_types", ["storage_tier"])
        op.create_index("ix_entity_types_table_name", "entity_types", ["table_name"])
    if not _has_table("entity_node"):
        op.create_table(
            "entity_node",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("entity_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("node_type", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("input_type", sa.String(), nullable=False),
            sa.Column("output_type", sa.String(), nullable=False),
            sa.Column("optional", sa.Boolean(), nullable=False),
            sa.Column("timeout_seconds", sa.Float(), nullable=True),
            sa.Column("handler", sa.String(), nullable=True),
            sa.Column("skills", sa.JSON(), nullable=False),
            sa.Column("system_prompt_file", sa.String(), nullable=True),
            sa.Column("system_prompt", sa.String(), nullable=True),
            sa.Column("tools", sa.JSON(), nullable=False),
            sa.Column("source_names", sa.JSON(), nullable=False),
            sa.Column("parameters", sa.JSON(), nullable=False),
            sa.Column("parameters_schema", sa.JSON(), nullable=False),
            sa.Column("input_binding", sa.String(), nullable=True),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("workdir", sa.String(), nullable=True),
            sa.Column("dag_ref", sa.String(), nullable=True),
            sa.Column("input_mapping", sa.JSON(), nullable=False),
            sa.Column("attributes_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("entity_id"),
            sa.UniqueConstraint("name", name="uq_entity_node_name"),
        )
        op.create_index("ix_entity_node_entity_id", "entity_node", ["entity_id"])
        op.create_index("ix_entity_node_name", "entity_node", ["name"])
        op.create_index("ix_entity_node_node_type", "entity_node", ["node_type"])
        op.create_index("ix_entity_node_role", "entity_node", ["role"])
        op.create_index("ix_entity_node_handler", "entity_node", ["handler"])
    if not _has_table("entity_dag"):
        op.create_table(
            "entity_dag",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("entity_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("inputs", sa.JSON(), nullable=False),
            sa.Column("nodes", sa.JSON(), nullable=False),
            sa.Column("edges", sa.JSON(), nullable=False),
            sa.Column("ui", sa.JSON(), nullable=False),
            sa.Column("attributes_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("entity_id"),
            sa.UniqueConstraint("name", name="uq_entity_dag_name"),
        )
        op.create_index("ix_entity_dag_entity_id", "entity_dag", ["entity_id"])
        op.create_index("ix_entity_dag_name", "entity_dag", ["name"])
    if not _has_table("entity_trigger"):
        op.create_table(
            "entity_trigger",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("entity_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("wait_for", sa.String(), nullable=False),
            sa.Column("target", sa.String(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("attributes_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("entity_id"),
            sa.UniqueConstraint("name", name="uq_entity_trigger_name"),
        )
        op.create_index("ix_entity_trigger_entity_id", "entity_trigger", ["entity_id"])
        op.create_index("ix_entity_trigger_name", "entity_trigger", ["name"])
    if not _has_table("entity_resource"):
        op.create_table(
            "entity_resource",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("entity_id", sa.String(), nullable=False),
            sa.Column("resource_id", sa.String(), nullable=False),
            sa.Column("permits", sa.Integer(), nullable=False),
            sa.Column("attributes_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("entity_id"),
            sa.UniqueConstraint("resource_id"),
        )
        op.create_index("ix_entity_resource_entity_id", "entity_resource", ["entity_id"])
        op.create_index("ix_entity_resource_resource_id", "entity_resource", ["resource_id"])
    if not _has_table("log_index"):
        op.create_table(
            "log_index",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("node_id", sa.String(), nullable=False),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("digest", sa.String(), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_log_index_run_id", "log_index", ["run_id"])
        op.create_index("ix_log_index_node_id", "log_index", ["node_id"])
        op.create_index("ix_log_index_digest", "log_index", ["digest"])
        op.create_index("ix_log_index_created_at", "log_index", ["created_at"])


def downgrade() -> None:
    for table_name in (
        "log_index",
        "entity_resource",
        "entity_trigger",
        "entity_dag",
        "entity_node",
        "entity_types",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)


def _has_table(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()
