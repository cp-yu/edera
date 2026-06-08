from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.bootstrap import discover_available_extensions
from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_runtime_app_config
from edera_core.dag.loader import load_graph
from edera_core.extension_manager import ExtensionManager
from edera_core.manifest import parse_manifest
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import get_core_entity, get_ordinary_entity


DEFAULT_NODE_TYPES = {
    "rss-fetcher",
    "api-fetcher",
    "reader",
    "advisor",
    "briefing-generator",
    "notifier",
}
DEFAULT_SOURCE_REFS = {
    "rss-source:hn-rss",
    "api-source:cls-telegraph",
    "api-source:jqka",
    "api-source:solidot",
    "api-source:ithome",
    "api-source:github",
}


def test_default_news_manifest_imports() -> None:
    manifest = parse_manifest(Path("extensions/default-news-workflow/manifest.yaml"))

    assert manifest.type == "workflow_extension"
    assert manifest.depends == []
    assert manifest.entity_imports == ["entities/**/*.yaml"]
    assert manifest.provider_imports == ["_providers/*/manifest.yaml"]
    assert manifest.library_imports == ["_lib/common"]


def test_default_news_dependencies_are_declared() -> None:
    manifests = discover_available_extensions([Path("extensions")])

    manifest = next(item for item in manifests if item.name == "default-news-workflow")
    assert manifest.type == "workflow_extension"


def test_default_workflow_top_level_sources_removed() -> None:
    assert not Path("config/dags/default.yaml").exists()
    assert not Path("config/triggers/default-default-cron.yaml").exists()
    for name in DEFAULT_NODE_TYPES:
        assert not Path(f"config/nodes/{name}.yaml").exists()


@pytest.mark.asyncio
async def test_imported_default_workflow_loads(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    graph = load_graph(config.dags["default"], config.nodes)

    assert len(graph.nodes) == 6
    assert sum(len(edges) for edges in graph.edges.values()) == 5
    assert {node.type for node in graph.instances.values()} == DEFAULT_NODE_TYPES


@pytest.mark.asyncio
async def test_default_source_seeds_imported(tmp_path: Path) -> None:
    config, engine = await _runtime_config_with_engine(tmp_path)
    factory = session_factory(engine)

    try:
        async with factory() as session:
            for ref in DEFAULT_SOURCE_REFS:
                entity_type = ref.split(":", 1)[0]
                entity = await get_ordinary_entity(session, entity_type, ref, config.entity_types)
                assert entity is not None
                assert entity.type in {"rss-source", "api-source"}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_default_source_node_configs_preserved(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    instances = {node.type: node for node in config.dags["default"].nodes}

    assert instances["rss-fetcher"].config["entities"] == ["rss-source:hn-rss"]
    assert instances["api-fetcher"].config["entities"] == [
        "api-source:cls-telegraph",
        "api-source:jqka",
        "api-source:solidot",
        "api-source:ithome",
        "api-source:github",
    ]


@pytest.mark.asyncio
async def test_default_trigger_imported(tmp_path: Path) -> None:
    config, engine = await _runtime_config_with_engine(tmp_path)
    factory = session_factory(engine)
    try:
        async with factory() as session:
            trigger = await get_core_entity(session, "trigger:default-default-cron", config.entity_types)
    finally:
        await engine.dispose()

    assert trigger is not None
    assert trigger.attributes["wait_for"] == 'cron:"*/30 * * * *"'
    assert trigger.attributes["target"] == "dag:default"
    assert trigger.attributes["enabled"] is True


async def _runtime_config(tmp_path: Path):
    config, engine = await _runtime_config_with_engine(tmp_path)
    await engine.dispose()
    return config


async def _runtime_config_with_engine(tmp_path: Path):
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    await init_db(engine)
    from edera_core.config.loader import _load_runtime_base_config

    config = _load_runtime_base_config(Path("config"))
    manager = ExtensionManager(
        extensions_dir=Path("extensions"),
        handlers_dir=tmp_path / "handlers",
        engine=engine,
        config_entity_types=config.entity_types,
    )
    await manager.install("default-news-workflow", installed_by="test")
    return await load_runtime_app_config(Path("config"), engine, [Path("extensions")]), engine
