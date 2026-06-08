from __future__ import annotations

import pytest

from edera_core.config.schema import DagConfig, NodeConfig, RuntimeSettings, SystemConfig
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeInput
from edera_core.resolver import HandlerMeta
from edera_core.resolver import HandlerNotFoundError
from edera_core.snapshot import DagExecutionClosure
from edera_core.snapshot import DagExecutionSnapshot


def test_executor_with_snapshot():
    snapshot = _snapshot(_Resolver({}))
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), snapshot)

    assert executor.snapshot is snapshot


@pytest.mark.asyncio
async def test_load_handler_from_snapshot(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return {'ok': True}\n", encoding="utf-8")
    resolver = _Resolver({"reader": HandlerMeta(handler)})
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(resolver))

    loaded = await executor._load_handler("reader")

    assert resolver.calls == ["reader"]
    assert callable(loaded)


@pytest.mark.asyncio
async def test_load_handler_from_database(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return ctx.input.payload\n", encoding="utf-8")
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(_Resolver({"reader": HandlerMeta(handler)})))

    output = await executor.execute("reader", NodeInput(run_id="run", payload={"value": 1}))

    assert output.ok
    assert output.payload == {"value": 1}


@pytest.mark.asyncio
async def test_missing_handler_returns_node_output():
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(_Resolver({})))

    output = await executor.execute("reader", NodeInput(run_id="run", payload={}))

    assert not output.ok
    assert output.error == "handler not found: reader"


@pytest.mark.asyncio
async def test_module_cache(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return ctx.input.payload\n", encoding="utf-8")
    resolver = _Resolver({"reader": HandlerMeta(handler)})
    executor = NodeExecutor(_nodes(), SystemConfig(), RuntimeSettings(), _snapshot(resolver))

    await executor.execute("reader", NodeInput(run_id="run-1", payload=1))
    await executor.execute("reader", NodeInput(run_id="run-2", payload=2))

    assert resolver.calls == ["reader"]


@pytest.mark.asyncio
async def test_handler_storage_uses_execution_snapshot(tmp_path):
    handler = tmp_path / "handler.py"
    handler.write_text("async def run(ctx):\n    return ctx.storage.table('items')\n", encoding="utf-8")
    resolver = _Resolver({"reader": HandlerMeta(handler, extension_name="reader_ext")})
    snapshot = _snapshot(resolver, {"reader_ext": {"items": "snapshot_items"}})
    executor = NodeExecutor(
        _nodes(),
        SystemConfig(),
        RuntimeSettings(),
        snapshot,
    )

    output = await executor.execute("reader", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload == "snapshot_items"


class _Resolver:
    def __init__(self, entries: dict[str, HandlerMeta]) -> None:
        self.entries = entries
        self.calls: list[str] = []

    async def get(self, name: str) -> HandlerMeta:
        self.calls.append(name)
        try:
            return self.entries[name]
        except KeyError as exc:
            raise HandlerNotFoundError(name) from exc


def _snapshot(
    resolver,
    extension_table_names: dict[str, dict[str, str]] | None = None,
) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("demo", {"demo": _dag()}, _nodes()),
        {},
        resolver,
        extension_table_names or {},
        {},
    )


def _dag() -> DagConfig:
    return DagConfig(name="demo", nodes=[], edges=[], ui={})


def _nodes() -> dict[str, NodeConfig]:
    return {
        "reader": NodeConfig(
            name="reader",
            type="function",
            handler="reader",
            input_type="Any",
            output_type="Any",
        )
    }
