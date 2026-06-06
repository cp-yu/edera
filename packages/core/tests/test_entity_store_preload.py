from __future__ import annotations

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.entity_query_result import EntityQueryResult
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_ordinary_entity, create_relation


@pytest.mark.asyncio
async def test_query_result_wrapper(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)

        result = await store.query_one_async("stock:test", session=session)

    assert isinstance(result, EntityQueryResult)
    assert result.entity.id == "stock:test"
    assert result.from_cache is False
    assert result.dag_run_id is None


@pytest.mark.asyncio
async def test_preload_for_dag(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)

        await store.preload_for_dag("run-1", ["stock:test"], session=session)

    assert store.memory_entities["run-1"]["stock:test"].id == "stock:test"


@pytest.mark.asyncio
async def test_preload_for_dag_caches_related_database_entities(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)
        await create_ordinary_entity(session, "rss-source", "source:rss", {"name": "rss"}, store.entity_types)
        await create_relation(session, "stock:TEST", "rss-source:rss", "uses-source", {}, store.entity_types)

        await store.preload_for_dag("run-1", ["stock:TEST"], session=session)

    assert store.related_refs("stock:TEST", "run-1") == ["rss-source:rss"]
    assert store.memory_entities["run-1"]["rss-source:rss"].id == "source:rss"


@pytest.mark.asyncio
async def test_query_from_cache(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)
        await store.preload_for_dag("run-1", ["stock:test"], session=session)

        result = await store.query_one_async("stock:test", dag_run_id="run-1", session=session)

    assert result.from_cache is True
    assert result.dag_run_id == "run-1"


@pytest.mark.asyncio
async def test_query_fallback_to_db(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)

        result = await store.query_one_async("stock:test", dag_run_id="run-1", session=session)

    assert result.from_cache is False
    assert "run-1" not in store.memory_entities


@pytest.mark.asyncio
async def test_query_without_dag_context(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)

        result = await store.query_one_async("stock:test", session=session)

    assert result.from_cache is False
    assert result.dag_run_id is None


@pytest.mark.asyncio
async def test_query_async_wraps_dag_cache_results(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)
        await store.preload_for_dag("run-1", ["stock:test"], session=session)

        results = await store.query_async("stock", dag_run_id="run-1", session=session)

    assert [(result.entity.id, result.from_cache, result.dag_run_id) for result in results] == [("stock:test", True, "run-1")]


@pytest.mark.asyncio
async def test_clear_cache(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, store.entity_types)
        await store.preload_for_dag("run-1", ["stock:test"], session=session)

    store.clear_cache_for_dag("run-1")

    assert "run-1" not in store.memory_entities


@pytest.mark.asyncio
async def test_preload_entity_not_found(tmp_path):
    store = _store()
    async with await _session(tmp_path) as session:
        with pytest.raises(ValueError, match="entity not found"):
            await store.preload_for_dag("run-1", ["missing:test"], session=session)


def test_loader_no_longer_loads_yaml_entities():
    import inspect

    from edera_core.config import loader

    source = inspect.getsource(loader._load_runtime_base_config)
    assert "load_entities_config(" not in source
    assert "load_entity_relations_config(" not in source
    assert "entity-relations.yaml" not in source


def _store() -> EntityStore:
    return EntityStore(
        EntitiesConfig(),
        {
            "stock": EntityTypeConfig.model_validate(
                {
                    "display_name": "Stock",
                    "business_id_field": "code",
                    "display_template": "{code}",
                    "storage_tier": "database",
                    "schema": {"properties": {"code": {"type": "string"}}},
                }
            ),
            "rss-source": EntityTypeConfig.model_validate(
                {
                    "display_name": "RSS",
                    "business_id_field": "name",
                    "display_template": "{name}",
                    "storage_tier": "database",
                    "schema": {"properties": {"name": {"type": "string"}}},
                }
            ),
        },
        EntityRelationsConfig(),
        None,
    )


async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    return session_factory(engine)()
