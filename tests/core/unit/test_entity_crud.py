from __future__ import annotations

import pytest

from edera_core.proto import edera_pb2 as pb2
from edera_core.server import _EntityService
from edera_core.trigger import TriggerExpressionError


class _Daemon:
    pb2 = pb2

    def __init__(self, config_dir) -> None:
        self.config_dir = config_dir
        self.controller = _Controller()


class _Controller:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def emit(self, event: str, payload: object | None = None, *, source: str = "rpc", depth: int = 0) -> list[str]:
        self.events.append(event)
        return []


class _Context:
    def invocation_metadata(self):
        return ()

    def auth_context(self):
        return {"x509_common_name": [b"human:test"]}

    async def abort(self, _code, message):
        raise AssertionError(message)


@pytest.mark.asyncio
async def test_emit_entity_changed(tmp_path) -> None:
    _write_config(tmp_path)
    daemon = _Daemon(tmp_path)
    service = _EntityService(daemon)

    created = await service.Create(pb2.Entity(type="stock", json='{"code":"TEST","name":"Test"}'), _Context())
    await service.Update(pb2.Entity(id=created.id, json='{"field":"name","value":"Changed"}'), _Context())
    await service.Delete(pb2.EntityRef(ref="stock:TEST"), _Context())

    assert daemon.controller.events == [
        "event:entity-changed:stock:TEST",
        "event:entity-changed:stock:TEST",
        "event:entity-changed:stock:TEST",
    ]


@pytest.mark.asyncio
async def test_trigger_wait_for_rejects_manual_prefix(tmp_path) -> None:
    _write_config(tmp_path)
    daemon = _Daemon(tmp_path)
    service = _EntityService(daemon)

    with pytest.raises(TriggerExpressionError, match="manual prefix"):
        await service.Create(
            pb2.Entity(
                type="trigger",
                json='{"name":"bad","wait_for":"manual:dag:default","target":"dag:default"}',
            ),
            _Context(),
        )


def _write_config(root) -> None:
    (root.parent / "schemas" / "entity-types").mkdir(parents=True, exist_ok=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [code, name]\n"
        "  properties:\n"
        "    code: {type: string}\n"
        "    name: {type: string}\n",
        encoding="utf-8",
    )
    (root.parent / "schemas" / "entity-types" / "trigger.yaml").write_text(
        "display_name: Trigger\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, wait_for, target]\n"
        "  properties:\n"
        "    name: {type: string}\n"
        "    wait_for: {type: string}\n"
        "    target: {type: string}\n",
        encoding="utf-8",
    )
    (root / "dags").mkdir()
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text("database_url = \"sqlite+aiosqlite:///test.db\"\n", encoding="utf-8")
