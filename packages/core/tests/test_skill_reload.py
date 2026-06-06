from __future__ import annotations

import json

import pytest

from edera_core.config_service import _ConfigService
from edera_core.proto import edera_pb2 as pb2


@pytest.mark.asyncio
async def test_reload_skills(tmp_path):
    controller = _Controller()
    service = _ConfigService(_Daemon(tmp_path / "config", controller))

    result = await service.ReloadSkills(pb2.EmptyRequest(), _Context("admin:test"))

    assert json.loads(result.json) == {"reloaded": True, "count": 2}
    assert controller.reloads == 1


class _Daemon:
    def __init__(self, config_dir, controller) -> None:
        self.config_dir = config_dir
        self.controller = controller
        self.pb2 = pb2


class _Controller:
    def __init__(self) -> None:
        self.reloads = 0

    async def reload_skills(self) -> int:
        self.reloads += 1
        return 2


class _Context:
    def __init__(self, identity: str) -> None:
        self.identity = identity

    def invocation_metadata(self) -> tuple[tuple[str, str], ...]:
        return (("x-edera-identity", self.identity),)

    async def abort(self, code, details: str) -> None:
        raise AssertionError(details)
