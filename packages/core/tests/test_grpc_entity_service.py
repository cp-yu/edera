from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from edera_core.bootstrap import BootstrapResult
from edera_core.config.entities import EntityStore
from edera_core.config.loader import _runtime_entity_types
from edera_core.config.schema import AppConfig, EntitiesConfig, EntityConfig, EntityRelationsConfig, EntityTypeConfig, RuntimeSettings, SystemConfig
from edera_core.dag_controller import RuntimeSnapshot
from edera_core.proto import edera_pb2 as pb2
from edera_core.server import _EntityService
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import create_ordinary_entity, create_relation, list_relations

from service_fakes import AbortError, FakeContext


@pytest.mark.asyncio
async def test_create_entity_rpc(tmp_path):
    service = _EntityService(await _daemon(tmp_path))

    result = await service.Create(
        pb2.Entity(id="stock:test", type="stock", json=json.dumps({"code": "TEST"})),
        FakeContext(),
    )

    assert result.id == "stock:test"
    assert json.loads(result.json)["attributes"]["code"] == "TEST"


@pytest.mark.asyncio
async def test_list_with_filters_rpc(tmp_path):
    daemon = await _daemon(tmp_path)
    async with daemon.controller._factory()() as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, daemon.controller.runtime_snapshot().config.entity_types)
        await create_ordinary_entity(session, "stock", "stock:other", {"code": "OTHER"}, daemon.controller.runtime_snapshot().config.entity_types)
        await session.commit()
    await daemon.controller.refresh()
    service = _EntityService(daemon)

    result = await service.List(
        pb2.EntityQuery(type="stock", filters_json=json.dumps({"code": "TEST"})),
        FakeContext(),
    )

    assert [entity.id for entity in result.entities] == ["stock:test"]


@pytest.mark.asyncio
async def test_relation_list_filters_query_repository(tmp_path, monkeypatch):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        entity_types = daemon.controller.runtime_snapshot().config.entity_types
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:one", {"url": "https://example.test/one"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:two", {"url": "https://example.test/two"}, entity_types)
        await create_relation(session, "stock:test", "source:one", "uses-source", entity_types=entity_types)
        await create_relation(session, "stock:test", "source:two", "observes", entity_types=entity_types)
        await session.commit()
    await daemon.controller.refresh()
    import edera_core.storage.repository as repository

    original = repository.list_relations
    captured: dict[str, str | None] = {}

    async def wrapped(session, from_entity_id=None, to_entity_id=None, relation_type=None):
        captured.update(
            {
                "from_entity_id": from_entity_id,
                "to_entity_id": to_entity_id,
                "relation_type": relation_type,
            }
        )
        return await original(session, from_entity_id=from_entity_id, to_entity_id=to_entity_id, relation_type=relation_type)

    monkeypatch.setattr(repository, "list_relations", wrapped)

    result = await service.List(
        pb2.EntityQuery(
            type="relation",
            filters_json=json.dumps({"from_entity_id": "stock:test", "relation_type": "uses-source"}),
        ),
        FakeContext(),
    )

    assert captured == {"from_entity_id": "stock:test", "to_entity_id": None, "relation_type": "uses-source"}
    assert [json.loads(entity.json)["attributes"]["to_entity_id"] for entity in result.entities] == ["source:one"]


@pytest.mark.asyncio
async def test_relation_query_expression_reads_database_relations(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        entity_types = daemon.controller.runtime_snapshot().config.entity_types
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, entity_types)
        await create_ordinary_entity(session, "rss-source", "source:one", {"url": "https://example.test/one"}, entity_types)
        await create_relation(session, "stock:test", "source:one", "uses-source", entity_types=entity_types)
        await session.commit()

    result = await service.Query(
        pb2.QueryRequest(expression="type=relation AND from_entity_id=stock:test"),
        FakeContext(),
    )

    assert [json.loads(entity.json)["attributes"]["to_entity_id"] for entity in result.entities] == ["source:one"]


@pytest.mark.asyncio
async def test_entity_read_paths_query_database_without_snapshot_refresh(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, daemon.controller.runtime_snapshot().config.entity_types)
        await session.commit()

    listed = await service.List(pb2.EntityQuery(type="stock"), FakeContext())
    got = await service.Get(pb2.EntityRef(ref="stock:test"), FakeContext())
    exported = await service.Export(pb2.EntityQuery(type="stock"), FakeContext())

    assert [entity.id for entity in listed.entities] == ["stock:test"]
    assert got.id == "stock:test"
    assert "stock:test" in json.loads(exported.json)["content"]


@pytest.mark.asyncio
async def test_update_entity_rpc_queries_database_after_runtime_materialization(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, daemon.controller.runtime_snapshot().config.entity_types)
        await session.commit()
    await daemon.controller.refresh()

    result = await service.Update(
        pb2.Entity(id="stock:test", json=json.dumps({"field": "name", "value": "Updated"})),
        FakeContext(),
    )

    assert json.loads(result.json)["attributes"]["name"] == "Updated"


@pytest.mark.asyncio
async def test_create_relation_via_entity_rpc(tmp_path):
    daemon = await _daemon(tmp_path)
    async with daemon.controller._factory()() as session:
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, daemon.controller.runtime_snapshot().config.entity_types)
        await create_ordinary_entity(session, "rss-source", "source:test", {"url": "https://example.test/rss"}, daemon.controller.runtime_snapshot().config.entity_types)
        await session.commit()
    await daemon.controller.refresh()
    service = _EntityService(daemon)

    result = await service.Create(
        pb2.Entity(
            type="relation",
            json=json.dumps(
                {
                    "from_entity_id": "stock:test",
                    "to_entity_id": "source:test",
                    "relation_type": "uses-source",
                }
            ),
        ),
        FakeContext(),
    )

    assert result.type == "relation"
    assert json.loads(result.json)["attributes"]["relation_type"] == "uses-source"


@pytest.mark.asyncio
async def test_delete_relation_via_entity_rpc(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        await create_ordinary_entity(
            session,
            "stock",
            "stock:test",
            {"code": "TEST"},
            daemon.controller.runtime_snapshot().config.entity_types,
        )
        await create_ordinary_entity(
            session,
            "rss-source",
            "source:test",
            {"url": "https://example.test/rss"},
            daemon.controller.runtime_snapshot().config.entity_types,
        )
        await session.commit()
    await daemon.controller.refresh()
    created = await service.Create(
        pb2.Entity(
            type="relation",
            json=json.dumps(
                {
                    "from_entity_id": "stock:test",
                    "to_entity_id": "source:test",
                    "relation_type": "uses-source",
                }
            ),
        ),
        FakeContext(),
    )

    result = await service.Delete(pb2.EntityRef(ref=created.id), FakeContext())

    async with daemon.controller._factory()() as session:
        relations = await list_relations(session)
    assert result.deleted is True
    assert relations == []


@pytest.mark.asyncio
async def test_force_delete_entity_removes_relations(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        await create_ordinary_entity(
            session,
            "stock",
            "stock:test",
            {"code": "TEST"},
            daemon.controller.runtime_snapshot().config.entity_types,
        )
        await create_ordinary_entity(
            session,
            "rss-source",
            "source:test",
            {"url": "https://example.test/rss"},
            daemon.controller.runtime_snapshot().config.entity_types,
        )
        await session.commit()
    await daemon.controller.refresh()
    await service.Create(
        pb2.Entity(
            type="relation",
            json=json.dumps(
                {
                    "from_entity_id": "stock:test",
                    "to_entity_id": "source:test",
                    "relation_type": "uses-source",
                }
            ),
        ),
        FakeContext(),
    )

    result = await service.Delete(pb2.EntityRef(ref="stock:test", force=True), FakeContext())

    assert result.deleted is True


@pytest.mark.asyncio
async def test_entity_delete_blocked_by_relations_lists_relation_ids(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        await create_ordinary_entity(
            session,
            "stock",
            "stock:test",
            {"code": "TEST"},
            daemon.controller.runtime_snapshot().config.entity_types,
        )
        await create_ordinary_entity(
            session,
            "rss-source",
            "source:test",
            {"url": "https://example.test/rss"},
            daemon.controller.runtime_snapshot().config.entity_types,
        )
        await session.commit()
    await daemon.controller.refresh()
    created = await service.Create(
        pb2.Entity(
            type="relation",
            json=json.dumps(
                {
                    "from_entity_id": "stock:test",
                    "to_entity_id": "source:test",
                    "relation_type": "uses-source",
                }
            ),
        ),
        FakeContext(),
    )

    with pytest.raises(AbortError) as exc:
        await service.Delete(pb2.EntityRef(ref="stock:test"), FakeContext())

    assert exc.value.code.name == "FAILED_PRECONDITION"
    assert created.id in exc.value.details


@pytest.mark.asyncio
async def test_core_entity_delete_blocked_by_relations(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    async with daemon.controller._factory()() as session:
        from edera_core.storage.repository import save_core_entity

        await save_core_entity(
            session,
            EntityConfig(id="reader", type="node", attributes={"name": "reader", "input_type": "Any", "output_type": "Any"}),
        )
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, daemon.controller.runtime_snapshot().config.entity_types)
        await session.commit()
    await daemon.controller.refresh()
    await service.Create(
        pb2.Entity(type="relation", json=json.dumps({"from_entity_id": "node:reader", "to_entity_id": "stock:test", "relation_type": "uses-entity"})),
        FakeContext(),
    )

    with pytest.raises(AbortError) as exc:
        await service.Delete(pb2.EntityRef(ref="node:reader"), FakeContext())
    assert exc.value.code.name == "FAILED_PRECONDITION"


@pytest.mark.asyncio
async def test_entity_import_export_rpc(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    path = tmp_path / "entities.yaml"
    path.write_text("entities:\n- id: stock:test\n  type: stock\n  attributes:\n    code: TEST\n", encoding="utf-8")

    imported = await service.Import(pb2.JsonRequest(json=json.dumps({"file": str(path)})), FakeContext())
    await daemon.controller.refresh()
    exported = await service.Export(pb2.EntityQuery(type="stock"), FakeContext())

    assert json.loads(imported.json)["imported"] == 1
    assert "stock:test" in json.loads(exported.json)["content"]


@pytest.mark.asyncio
async def test_default_entity_export_import_round_trips_core_ordinary_and_relations(tmp_path):
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    source = await _daemon(source_root)
    source_service = _EntityService(source)
    async with source.controller._factory()() as session:
        from edera_core.storage.repository import save_core_entity

        await save_core_entity(
            session,
            EntityConfig(id="reader", type="node", attributes={"name": "reader", "input_type": "Any", "output_type": "Any"}),
        )
        await create_ordinary_entity(session, "stock", "stock:test", {"code": "TEST"}, source.controller.runtime_snapshot().config.entity_types)
        await create_ordinary_entity(
            session,
            "rss-source",
            "source:test",
            {"url": "https://example.test/rss"},
            source.controller.runtime_snapshot().config.entity_types,
        )
        await session.commit()
    await source.controller.refresh()
    await source_service.Create(
        pb2.Entity(
            type="relation",
            json=json.dumps({"from_entity_id": "stock:test", "to_entity_id": "source:test", "relation_type": "uses-source"}),
        ),
        FakeContext(),
    )
    exported = await source_service.Export(pb2.EntityQuery(), FakeContext())
    path = tmp_path / "entities.yaml"
    path.write_text(json.loads(exported.json)["content"], encoding="utf-8")
    target = await _daemon(target_root)
    target_service = _EntityService(target)

    imported = await target_service.Import(pb2.JsonRequest(json=json.dumps({"file": str(path)})), FakeContext())
    await target.controller.refresh()
    nodes = await target_service.List(pb2.EntityQuery(type="node"), FakeContext())
    stocks = await target_service.List(pb2.EntityQuery(type="stock"), FakeContext())
    relations = await target_service.List(pb2.EntityQuery(type="relation"), FakeContext())

    assert json.loads(imported.json)["imported"] == 4
    assert [entity.id for entity in nodes.entities] == ["reader"]
    assert [entity.id for entity in stocks.entities] == ["stock:test"]
    assert len(relations.entities) == 1


@pytest.mark.asyncio
async def test_list_uses_dag_run_cache(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    store = daemon.controller.runtime_snapshot().entity_store
    store.memory_entities["run-1"] = {
        "stock:test": EntityConfig(id="stock:test", type="stock", attributes={"code": "TEST"})
    }

    result = await service.List(pb2.EntityQuery(type="stock", dag_run_id="run-1"), FakeContext())

    assert [entity.id for entity in result.entities] == ["stock:test"]


@pytest.mark.asyncio
async def test_list_uses_active_run_store_for_dag_run_id(tmp_path):
    daemon = await _daemon(tmp_path)
    service = _EntityService(daemon)
    app = daemon.controller.runtime_snapshot().config
    run_store = EntityStore(app.entities, app.entity_types, app.entity_relations, None)
    run_store.memory_entities["run-1"] = {
        "stock:test": EntityConfig(id="stock:test", type="stock", attributes={"code": "TEST"})
    }
    daemon.controller.active_runs = {
        "demo": SimpleNamespace(
            run_id="run-1",
            task=SimpleNamespace(done=lambda: False),
            executor=SimpleNamespace(entity_store=run_store),
        )
    }

    result = await service.List(pb2.EntityQuery(type="stock", dag_run_id="run-1"), FakeContext())

    assert [entity.id for entity in result.entities] == ["stock:test"]


async def _daemon(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    controller = _Controller(engine)
    await controller.refresh()
    return type("Daemon", (), {"controller": controller, "pb2": pb2, "config_dir": tmp_path / "config"})()


class _Controller:
    def __init__(self, engine):
        self.engine = engine
        self.factory = session_factory(engine)
        self._snapshot = None

    def _factory(self):
        return self.factory

    def runtime_snapshot(self):
        return self._snapshot

    async def install_snapshot(self, config, bootstrap):
        store = EntityStore(config.entities, config.entity_types, config.entity_relations, None)
        self._snapshot = RuntimeSnapshot(config, bootstrap, store, None, None, {})

    async def refresh(self):
        async with self.factory() as session:
            from edera_core.storage.repository import list_core_entities, seed_entity_type_records

            entity_types = await seed_entity_type_records(session, _runtime_entity_types(_entity_types()))
            entities = await list_core_entities(session)
            await session.commit()
        await self.install_snapshot(
            AppConfig(
                system=SystemConfig(),
                entity_types=entity_types,
                entities=EntitiesConfig(entities=entities),
                entity_relations=EntityRelationsConfig(),
                runtime=RuntimeSettings(),
                nodes={},
                skills={},
                dags={},
            ),
            BootstrapResult([], {}, {}, {}),
        )

    async def emit(self, event, source="test"):
        return []


def _entity_types() -> dict[str, EntityTypeConfig]:
    return {
        "stock": _entity_type("code"),
        "rss-source": _entity_type("url"),
        "node": _entity_type("name"),
    }


def _entity_type(business_id_field: str) -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Entity",
            "business_id_field": business_id_field,
            "display_template": "{" + business_id_field + "}",
            "storage_tier": "database",
            "schema": {"properties": {business_id_field: {"type": "string"}}},
        }
    )
