from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from edera_core.bootstrap import scan_extensions
from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.config.schema import NodeConfig, RuntimeSettings, SystemConfig
from edera_core.engine import Engine
from edera_core.node.executor import NodeExecutor
from edera_core.registry import HandlerRegistry
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import save_ordinary_entity, seed_entity_type_records
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


def test_scan_extensions_parses_manifest_entity_imports(tmp_path: Path) -> None:
    extension = tmp_path / "demo"
    extension.mkdir()
    (extension / "handler.py").write_text("async def run(ctx):\n    return {}\n", encoding="utf-8")
    (extension / "manifest.yaml").write_text(
        "name: demo-extension\n"
        "version: 0.1.0\n"
        "handlers:\n"
        "  - name: demo\n"
        "    role: source\n"
        "    input_type: Any\n"
        "    entry: handler.py\n"
        "entity_types:\n"
        "  - name: article\n"
        "    display_name: Article\n"
        "    business_id_field: slug\n"
        "storage:\n"
        "  tables:\n"
        "    - name: raw_items\n"
        "      columns:\n"
        "        - name: id\n"
        "          type: integer\n"
        "          primary_key: true\n"
        "imports:\n"
        "  entities:\n"
        "    - dags/default/dag.yaml\n",
        encoding="utf-8",
    )

    result = scan_extensions([tmp_path])
    manifest = result.manifests[0]

    assert manifest.entity_imports == ["dags/default/dag.yaml"]
    assert "demo" in result.handler_registry
    assert "article" in result.entity_type_registry
    assert result.table_names["demo-extension"]["raw_items"] == "ext_demo_extension_raw_items"


@pytest.mark.parametrize("import_path", ["/etc/passwd", "../dag.yaml", "dags/../dag.yaml"])
def test_scan_extensions_rejects_invalid_entity_import_paths(tmp_path: Path, import_path: str) -> None:
    extension = tmp_path / "demo"
    extension.mkdir()
    (extension / "manifest.yaml").write_text(
        "name: demo-extension\n"
        "version: 0.1.0\n"
        "imports:\n"
        "  entities:\n"
        f"    - {import_path}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid entity import path"):
        scan_extensions([tmp_path])


@pytest.mark.asyncio
async def test_entity_and_extension_table_names_do_not_collide(tmp_path: Path) -> None:
    extension = tmp_path / "extensions" / "rss-fetcher"
    extension.mkdir(parents=True)
    (extension / "manifest.yaml").write_text(
        "name: rss-fetcher\n"
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
    bootstrap = scan_extensions([tmp_path / "extensions"])
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        from edera_core.bootstrap import create_extension_tables

        await create_extension_tables(engine, bootstrap.storage_tables)
        factory = session_factory(engine)
        async with factory() as session:
            rss_source = EntityTypeConfig.model_validate(
                {
                    "display_name": "RSS Source",
                    "business_id_field": "url",
                    "display_template": "{url}",
                    "storage_tier": "database",
                    "schema": {"required": ["url"], "properties": {"url": {"type": "string"}}},
                }
            )
            await seed_entity_type_records(session, {"rss-source": rss_source})
            await save_ordinary_entity(
                session,
                EntityConfig(id="rss-1", type="rss-source", attributes={"url": "https://example.test/rss"}),
                rss_source,
            )
            await session.commit()

        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        assert "entity_rss_source" in tables
        assert "ext_rss_fetcher_raw_items" in tables
        assert "entity_raw_items" not in tables
    finally:
        await engine.dispose()


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
