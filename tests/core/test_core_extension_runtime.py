from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect
import yaml

from edera_core.bootstrap import create_extension_tables, discover_available_extensions, extension_table_name, load_installed_extensions
from edera_core.config.schema import EntityConfig, EntityTypeConfig
from edera_core.config.schema import NodeConfig, RuntimeSettings, SystemConfig
from edera_core.engine import Engine
from edera_core.node.executor import NodeExecutor
from edera_core.resolver import HandlerMeta, StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import save_installed_extension, save_ordinary_entity, seed_entity_type_records
from edera_types import NodeInput


@pytest.mark.asyncio
async def test_load_installed_extensions_registers_manifest_handlers(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_installed_extension(
                session,
                name="rss-fetcher",
                version="0.1.0",
                manifest_snapshot=_manifest_snapshot(Path("extensions/default-news-workflow/_providers/rss-fetcher/manifest.yaml")),
                import_records=[],
            )
            result = await load_installed_extensions(session, Path("handlers"))
        assert _handler_names(result) == {"fetch-rss"}
        assert _entity_type_names(result) == {"rss-source"}
    finally:
        await engine.dispose()


def test_extension_table_name_maps_declared_table_names(tmp_path: Path) -> None:
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

    manifest = discover_available_extensions([tmp_path])[0]

    assert extension_table_name(manifest.name, manifest.storage_tables[0].name) == "ext_demo_extension_raw_items"


@pytest.mark.asyncio
async def test_load_installed_extensions_parses_manifest_entity_imports(tmp_path: Path) -> None:
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

    manifest = discover_available_extensions([tmp_path])[0]
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_installed_extension(
                session,
                name=manifest.name,
                version=manifest.version,
                manifest_snapshot=_manifest_snapshot(extension / "manifest.yaml"),
                import_records=[],
            )
            result = await load_installed_extensions(session, tmp_path)

        assert manifest.entity_imports == ["dags/default/dag.yaml"]
        assert _handler_names(result) == {"demo"}
        assert _entity_type_names(result) == {"article"}
        assert result.table_names["demo-extension"]["raw_items"] == "ext_demo_extension_raw_items"
    finally:
        await engine.dispose()


@pytest.mark.parametrize("import_path", ["/etc/passwd", "../dag.yaml", "dags/../dag.yaml"])
def test_discover_available_extensions_rejects_invalid_entity_import_paths(tmp_path: Path, import_path: str) -> None:
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
        discover_available_extensions([tmp_path])


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
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_installed_extension(
                session,
                name="rss-fetcher",
                version="0.1.0",
                manifest_snapshot=_manifest_snapshot(extension / "manifest.yaml"),
                import_records=[],
            )
            bootstrap = await load_installed_extensions(session, tmp_path / "handlers")

        await create_extension_tables(engine, bootstrap.storage_tables)
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


@pytest.mark.asyncio
async def test_node_executor_calls_handler_context(tmp_path: Path) -> None:
    handler = tmp_path / "handler.py"
    handler.write_text(
        "async def run(ctx):\n"
        "    return {'payload': ctx.input.payload, 'node': ctx.node_name, 'param': ctx.params['x']}\n",
        encoding="utf-8",
    )
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
        _test_snapshot({"demo": HandlerMeta(handler)}),
    )
    output = await executor.execute("demo", NodeInput(run_id="run", payload={"ok": True}))
    assert output.ok
    assert output.payload == {"payload": {"ok": True}, "node": "demo", "param": 1}


@pytest.mark.asyncio
async def test_node_executor_exposes_declared_extension_table(tmp_path: Path) -> None:
    handler = tmp_path / "demo-extension" / "handler.py"
    handler.parent.mkdir()
    handler.write_text("async def run(ctx):\n    return ctx.storage.table('raw_items')\n", encoding="utf-8")
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
        _test_snapshot(
            {"demo": HandlerMeta(handler, extension_name="demo-extension")},
            extension_table_names={"demo-extension": {"raw_items": "ext_demo_extension_raw_items"}},
        ),
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


def _manifest_snapshot(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(data, dict)
    return data


def _handler_names(result) -> set[str]:
    return {handler.name for manifest in result.manifests for handler in manifest.handlers}


def _entity_type_names(result) -> set[str]:
    return {entity_type.name for manifest in result.manifests for entity_type in manifest.entity_types}


def _test_snapshot(
    handlers: dict[str, HandlerMeta],
    extension_table_names: dict[str, dict[str, str]] | None = None,
) -> DagExecutionSnapshot:
    return DagExecutionSnapshot(
        DagExecutionClosure("test", {}, {}),
        {},
        StaticHandlerResolver(handlers),
        extension_table_names or {},
        {},
    )
