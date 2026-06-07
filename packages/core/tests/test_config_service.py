from __future__ import annotations

import json

import grpc
import pytest

from edera_core.config_service import _ConfigService
from edera_core.proto import edera_pb2 as pb2
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import get_entity_type_config, upsert_entity_type_record
from edera_core.config.schema import EntityTypeConfig

from service_fakes import AbortError, FakeContext, FakeDaemon


@pytest.mark.asyncio
async def test_entity_type_crud_uses_database_and_emits_without_snapshot_rebuild(tmp_path):
    root = tmp_path / "config"
    controller = await _controller(tmp_path)
    service = _ConfigService(FakeDaemon(root, controller))

    try:
        create = await service.CreateEntityType(pb2.ConfigFileContentRequest(name="stock", content=_entity_type()), FakeContext())
        listed = json.loads((await service.ListEntityTypes(pb2.EmptyRequest(), FakeContext())).json)
        got = json.loads((await service.GetEntityType(pb2.NameRequest(name="stock"), FakeContext())).json)
        save = await service.SaveEntityType(pb2.ConfigFileContentRequest(name="stock", content=_entity_type(display_name="Stock V2")), FakeContext())
        delete = await service.DeleteEntityType(pb2.DeleteEntityTypeRequest(name="stock", cascade=False), FakeContext())
        async with controller._factory()() as session:
            stored = await get_entity_type_config(session, "stock")
    finally:
        await controller.engine.dispose()

    assert '"created": true' in create.json
    assert listed["types"]["stock"]["display_name"] == "Stock"
    assert got["content"].startswith("display_name: Stock\n")
    assert '"updated": true' in save.json
    assert '"deleted": true' in delete.json
    assert stored is None
    assert controller.emitted == ["event:config-changed", "event:config-changed", "event:config-changed"]


@pytest.mark.asyncio
async def test_save_system_protected(tmp_path):
    root = tmp_path / "config"
    controller = await _controller(tmp_path, protected=True)
    service = _ConfigService(FakeDaemon(root, controller))

    try:
        with pytest.raises(AbortError) as exc:
            await service.SaveEntityType(pb2.ConfigFileContentRequest(name="stock", content=_entity_type()), FakeContext())
    finally:
        await controller.engine.dispose()

    assert exc.value.code == grpc.StatusCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_save_invalid_system_config(tmp_path):
    root = tmp_path / "config"
    _write_config(root)
    service = _ConfigService(FakeDaemon(root))

    with pytest.raises(AbortError) as exc:
        await service.SaveSystemConfig(pb2.TextRequest(content="schedule_minutes = 0\n"), FakeContext())

    assert exc.value.code == grpc.StatusCode.INVALID_ARGUMENT


def _write_config(root, protected=False):
    (root / "dags").mkdir(parents=True)
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(_entity_type(protected), encoding="utf-8")
    (root / "system.toml").write_text("database_url = \"sqlite+aiosqlite:///tmp/test.db\"\nschedule_minutes = 1\n", encoding="utf-8")


def _entity_type(protected=False, display_name="Stock"):
    suffix = "system_protected: true\n" if protected else ""
    return f"display_name: {display_name}\nbusiness_id_field: code\ndisplay_template: '{{code}}'\nschema:\n  properties:\n    code: {{}}\n" + suffix


class Controller:
    def __init__(self, engine, factory):
        self.engine = engine
        self.factory = factory
        self.emitted: list[str] = []

    def _factory(self):
        return self.factory

    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0):
        self.emitted.append(event)
        return []

    async def install_snapshot(self, *_args, **_kwargs):
        raise AssertionError("EntityType CRUD must not rebuild RuntimeControlSnapshot")


async def _controller(tmp_path, protected=False) -> Controller:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    factory = session_factory(engine)
    if protected:
        async with factory() as session:
            await upsert_entity_type_record(
                session,
                "stock",
                EntityTypeConfig(
                    display_name="Stock",
                    business_id_field="code",
                    display_template="{code}",
                    system_protected=True,
                    schema_={"properties": {"code": {}}},
                ),
            )
            await session.commit()
    return Controller(engine, factory)
