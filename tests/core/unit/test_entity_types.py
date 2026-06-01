from pathlib import Path

import pytest
from pydantic import ValidationError

from edera_core.config.schema import EntityTypeConfig, NodeConfig
from edera_core.config.loader import load_entity_type_configs
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.materialization import deprecated_cleanup_ready
from edera_core.storage.repository import (
    list_entity_type_configs,
    save_ordinary_entity,
    seed_entity_type_records,
)


def test_load_stock_schema() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    stock = schemas["stock"]
    assert stock.business_id_field == "code"
    assert stock.display_template
    assert stock.field_permissions["code"] == "read-only"
    assert stock.system_protected is False


def test_entity_type_capability_detection() -> None:
    schemas = load_entity_type_configs(Path("schemas/entity-types"))
    node = schemas["node"]
    dag = schemas["dag"]
    trigger = schemas["trigger"]
    run_metadata = schemas["run-metadata"]

    assert node.storage_tier == "filesystem"
    assert node.system_protected is True
    assert node.is_executable
    assert not node.is_dag
    assert dag.storage_tier == "filesystem"
    assert dag.system_protected is True
    assert dag.is_dag
    assert trigger.storage_tier == "filesystem"
    assert trigger.system_protected is True
    assert trigger.is_trigger
    assert run_metadata.storage_tier == "memory"
    assert run_metadata.system_protected is True


def test_emits_field() -> None:
    node = NodeConfig.model_validate(
        {
            "name": "sentiment",
            "type": "function",
            "handler": "sentiment",
            "input_type": "Any",
            "output_type": "Any",
            "emits": [{"event": "event:negative-news", "condition": "output.sentiment == 'negative'"}],
        }
    )

    assert node.emits[0].event == "event:negative-news"
    assert node.emits[0].condition == "output.sentiment == 'negative'"


def test_rejects_unsupported_materialized_field_type() -> None:
    with pytest.raises(ValidationError):
        EntityTypeConfig.model_validate(
            {
                "display_name": "Stock",
                "business_id_field": "code",
                "display_template": "{code}",
                "materialized_fields": {"raw": {"type": "blob"}},
                "schema": {"properties": {"raw": {"type": "string"}}},
            }
        )


@pytest.mark.asyncio
async def test_entity_type_materialization_metadata_round_trips(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "entity-types.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await seed_entity_type_records(session, {"stock": _stock_type()})
            await session.commit()
        async with factory() as session:
            entity_types = await list_entity_type_configs(session)

        stock = entity_types["stock"]
        assert stock.table_name == "entity_stock"
        assert stock.schema_version == 3
        assert stock.materialized_fields["code"].type == "text"
        assert stock.materialized_fields["code"].index is True
        assert stock.deprecated_fields == ["legacy_code"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_entity_type_seed_preserves_db_materialization_metadata(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "preserve.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await seed_entity_type_records(session, {"stock": _stock_type()})
            await session.commit()
        async with factory() as session:
            await seed_entity_type_records(session, {"stock": _stock_type_without_materialization()})
            await session.commit()
        async with factory() as session:
            stock = (await list_entity_type_configs(session))["stock"]

        assert stock.materialized_fields["code"].index is True
        assert stock.deprecated_fields == ["legacy_code"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_deprecated_field_write_and_cleanup_guardrail(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "deprecated.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            stock = _stock_type()
            await seed_entity_type_records(session, {"stock": stock})
            saved = await save_ordinary_entity(
                session,
                entity=_entity("stock-1", {"code": "00700", "name": "Tencent", "legacy_code": "OLD"}),
                entity_type=stock,
            )
            await session.commit()

        async with factory() as session:
            assert "legacy_code" not in saved.attributes
            assert await deprecated_cleanup_ready(session, "stock", _stock_type(), "legacy_code")
    finally:
        await engine.dispose()


def _stock_type() -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Stock",
            "business_id_field": "code",
            "display_template": "{code}",
            "storage_tier": "database",
            "schema_version": 3,
            "materialized_fields": {"code": {"type": "text", "index": True}},
            "deprecated_fields": ["legacy_code"],
            "schema": {
                "required": ["code", "name"],
                "properties": {
                    "code": {"type": "string"},
                    "name": {"type": "string"},
                    "legacy_code": {"type": "string"},
                },
            },
        }
    )


def _stock_type_without_materialization() -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Stock",
            "business_id_field": "code",
            "display_template": "{code}",
            "storage_tier": "database",
            "schema_version": 3,
            "schema": {
                "required": ["code", "name"],
                "properties": {
                    "code": {"type": "string"},
                    "name": {"type": "string"},
                },
            },
        }
    )


def _entity(entity_id: str, attributes: dict[str, object]):
    from edera_core.config.schema import EntityConfig

    return EntityConfig(id=entity_id, type="stock", attributes=attributes)
