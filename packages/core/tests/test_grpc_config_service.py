from __future__ import annotations

import json

import asyncio
import grpc
import pytest

from edera_core.config_service import _ConfigService
from edera_core.proto import edera_pb2 as pb2

from service_fakes import AbortError


@pytest.mark.asyncio
async def test_reload_entity_types(tmp_path):
    service = _ConfigService(_Daemon(tmp_path / "config", _Controller({"stock": object()})))

    result = await service.ReloadEntityTypes(pb2.EmptyRequest(), _Context("admin:test"))

    assert json.loads(result.json) == {"reloaded": True, "count": 1}


@pytest.mark.asyncio
async def test_reload_entity_types_rejects_non_admin(tmp_path):
    service = _ConfigService(_Daemon(tmp_path / "config", _Controller({"stock": object()})))

    with pytest.raises(AbortError) as exc:
        await service.ReloadEntityTypes(pb2.EmptyRequest(), _Context("human:test"))

    assert exc.value.code == grpc.StatusCode.PERMISSION_DENIED


@pytest.mark.asyncio
async def test_reload_affects_new_dag(tmp_path):
    controller = _Controller({"stock": object()})
    service = _ConfigService(_Daemon(tmp_path / "config", controller))

    await service.ReloadEntityTypes(pb2.EmptyRequest(), _Context("admin:test"))

    assert controller.reloads == 1


@pytest.mark.asyncio
async def test_reload_isolation(tmp_path):
    running_snapshot = {"stock": object()}
    controller = _Controller({"stock": object(), "news": object()})
    service = _ConfigService(_Daemon(tmp_path / "config", controller))

    await service.ReloadEntityTypes(pb2.EmptyRequest(), _Context("admin:test"))

    assert set(running_snapshot) == {"stock"}


@pytest.mark.asyncio
async def test_reload_concurrent_calls(tmp_path):
    controller = _Controller({"stock": object(), "news": object()})
    service = _ConfigService(_Daemon(tmp_path / "config", controller))

    results = await asyncio.gather(
        service.ReloadEntityTypes(pb2.EmptyRequest(), _Context("admin:a")),
        service.ReloadEntityTypes(pb2.EmptyRequest(), _Context("admin:b")),
    )

    assert [json.loads(result.json)["count"] for result in results] == [2, 2]
    assert controller.reloads == 2


class _Daemon:
    def __init__(self, config_dir, controller) -> None:
        self.config_dir = config_dir
        self.controller = controller
        self.pb2 = pb2


class _Controller:
    def __init__(self, entity_types: dict[str, object]) -> None:
        self.entity_types = entity_types
        self.reloads = 0

    async def reload_entity_types(self) -> int:
        self.reloads += 1
        return len(self.entity_types)


class _Context:
    def __init__(self, identity: str) -> None:
        self.identity = identity

    def invocation_metadata(self) -> tuple[tuple[str, str], ...]:
        return (("x-edera-identity", self.identity),)

    async def abort(self, code: grpc.StatusCode, details: str) -> None:
        raise AbortError(code, details)
