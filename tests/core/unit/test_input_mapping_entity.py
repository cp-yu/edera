from __future__ import annotations

import grpc
import pytest
from sqlalchemy import inspect, text

from edera_core.config.schema import EntityConfig
from edera_core.config_service import _ConfigService
from edera_core.proto import edera_pb2 as pb2
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import get_core_entity, seed_entity_type_records, save_core_entity
from edera_core.config.loader import _default_core_entity_types


class _Daemon:
    pb2 = pb2

    def __init__(self, factory, config_dir) -> None:
        self.config_dir = config_dir
        self.controller = _Controller(factory)


class _Controller:
    def __init__(self, factory) -> None:
        self._session_factory = factory

    def _factory(self):
        return self._session_factory


class _Abort(Exception):
    def __init__(self, code, message: str) -> None:
        super().__init__(message)
        self.code = code


class _Context:
    async def abort(self, code, message: str) -> None:
        raise _Abort(code, message)


@pytest.mark.asyncio
async def test_create_input_mapping_entity(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            entity_types = await seed_entity_type_records(session, _default_core_entity_types())
            saved = await save_core_entity(
                session,
                EntityConfig(
                    id="mapping-default",
                    type="input_mapping",
                    attributes={
                        "name": "default",
                        "shared": {"topic": "payload.topic"},
                        "nodes": {"worker": {"limit": 5}},
                        "append_nodes": ["worker"],
                    },
                ),
            )
            await session.commit()

        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        assert "entity_input_mapping" in tables

        async with factory() as session:
            loaded = await get_core_entity(session, "input_mapping:default", entity_types)
        assert loaded == saved
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_delete_protected_type(tmp_path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await seed_entity_type_records(session, _default_core_entity_types())
            await session.commit()

        service = _ConfigService(_Daemon(factory, tmp_path))
        with pytest.raises(_Abort) as exc_info:
            await service.DeleteEntityType(pb2.DeleteEntityTypeRequest(name="input_mapping"), _Context())
        assert exc_info.value.code == grpc.StatusCode.PERMISSION_DENIED

        async with factory() as session:
            result = await session.exec(text("select count(*) from entity_types where name = 'input_mapping'"))
        assert result.one()[0] == 1
    finally:
        await engine.dispose()
