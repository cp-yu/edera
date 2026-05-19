"""raw item entity tags

Revision ID: 0004_raw_item_tags
Revises: 0003_event_records
Create Date: 2026-05-19
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0004_raw_item_tags"
down_revision = "0003_event_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE raw_items RENAME COLUMN stock_codes TO tags")
    bind = op.get_bind()
    for row_id, raw_tags in bind.execute(sa.text("SELECT id, tags FROM raw_items")):
        bind.execute(
            sa.text("UPDATE raw_items SET tags = :tags WHERE id = :id"),
            {"tags": json.dumps(_entity_tags(raw_tags), ensure_ascii=False), "id": row_id},
        )


def downgrade() -> None:
    op.execute("ALTER TABLE raw_items RENAME COLUMN tags TO stock_codes")
    bind = op.get_bind()
    for row_id, raw_tags in bind.execute(sa.text("SELECT id, stock_codes FROM raw_items")):
        bind.execute(
            sa.text("UPDATE raw_items SET stock_codes = :tags WHERE id = :id"),
            {"tags": json.dumps(_stock_codes(raw_tags), ensure_ascii=False), "id": row_id},
        )


def _entity_tags(raw_value: str | None) -> list[str]:
    values = _json_list(raw_value)
    return [value if ":" in value else f"stock:{value}" for value in values]


def _stock_codes(raw_value: str | None) -> list[str]:
    return [value.removeprefix("stock:") for value in _json_list(raw_value)]


def _json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    values = json.loads(raw_value)
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str)]
