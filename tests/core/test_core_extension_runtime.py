from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.bootstrap import scan_extensions
from edera_core.config.schema import NodeConfig, RuntimeSettings, SystemConfig
from edera_core.engine import Engine
from edera_core.node.executor import NodeExecutor
from edera_core.registry import HandlerRegistry
from edera_types import NodeInput


def test_scan_extensions_registers_manifest_handlers() -> None:
    result = scan_extensions([Path("extensions")], Path("config"))
    assert "fetch-rss" in result.handler_registry
    assert "rss-source" in result.entity_type_registry


def test_scan_extensions_maps_declared_table_names(tmp_path: Path) -> None:
    extension = tmp_path / "demo"
    extension.mkdir()
    (extension / "manifest.yaml").write_text(
        "name: demo-extension\n"
        "version: 0.1.0\n"
        "storage:\n"
        "  tables:\n"
        "    - name: raw_items\n"
        "      columns:\n"
        "        - name: id\n"
        "          type: integer\n"
        "          primary_key: true\n",
        encoding="utf-8",
    )

    result = scan_extensions([tmp_path])

    assert result.table_names["demo-extension"]["raw_items"] == "ext_demo_extension_raw_items"


def test_handler_registry_rejects_duplicate_names() -> None:
    registry = HandlerRegistry()
    registry.register("x", "/tmp/a.py")
    with pytest.raises(ValueError, match="duplicate handler"):
        registry.register("x", "/tmp/b.py")


@pytest.mark.asyncio
async def test_node_executor_calls_handler_context(tmp_path: Path) -> None:
    handler = tmp_path / "handler.py"
    handler.write_text(
        "async def run(ctx):\n"
        "    return {'payload': ctx.input.payload, 'node': ctx.node_name, 'param': ctx.params['x']}\n",
        encoding="utf-8",
    )
    registry = HandlerRegistry()
    registry.register("demo", handler)
    executor = NodeExecutor(
        {
            "demo": NodeConfig(
                name="demo",
                type="function",
                role="processor",
                handler="demo",
                input_type="Any",
                output_type="Any",
                parameters={"x": 1},
            )
        },
        SystemConfig(),
        RuntimeSettings(),
        registry.seal(),
    )
    output = await executor.execute("demo", NodeInput(run_id="run", payload={"ok": True}))
    assert output.ok
    assert output.payload == {"payload": {"ok": True}, "node": "demo", "param": 1}


@pytest.mark.asyncio
async def test_node_executor_exposes_declared_extension_table(tmp_path: Path) -> None:
    handler = tmp_path / "demo-extension" / "handler.py"
    handler.parent.mkdir()
    handler.write_text("async def run(ctx):\n    return ctx.storage.table('raw_items')\n", encoding="utf-8")
    registry = HandlerRegistry()
    registry.register("demo", handler)
    executor = NodeExecutor(
        {
            "demo": NodeConfig(
                name="demo",
                type="function",
                role="processor",
                handler="demo",
                input_type="Any",
                output_type="Any",
            )
        },
        SystemConfig(),
        RuntimeSettings(),
        registry.seal(),
        extension_tables={"demo-extension": {"raw_items": "ext_demo_extension_raw_items"}},
    )

    output = await executor.execute("demo", NodeInput(run_id="run", payload={}))

    assert output.ok
    assert output.payload == "ext_demo_extension_raw_items"


@pytest.mark.asyncio
async def test_engine_provides_start_run_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object, object]] = []

    async def start(self, run_startup: bool = True) -> None:
        calls.append(("start", run_startup, None))

    async def run_now(self, source: str = "manual", dag_name: str = "default", payload: object | None = None) -> str:
        calls.append(("run", source, dag_name))
        return "run"

    async def shutdown(self) -> None:
        calls.append(("shutdown", None, None))

    monkeypatch.setattr("edera_core.dag_controller.DagController.start", start)
    monkeypatch.setattr("edera_core.dag_controller.DagController.run_now", run_now)
    monkeypatch.setattr("edera_core.dag_controller.DagController.shutdown", shutdown)

    engine = Engine(Path("config"), [Path("extensions")])
    await engine.start()
    run_id = await engine.run("manual", "default")
    await engine.shutdown()

    assert run_id == "run"
    assert calls == [("start", False, None), ("run", "manual", "default"), ("shutdown", None, None)]
