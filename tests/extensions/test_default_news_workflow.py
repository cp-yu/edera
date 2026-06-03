from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.bootstrap import scan_extensions
from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_runtime_app_config
from edera_core.dag.loader import load_graph
from edera_core.manifest import parse_manifest
from edera_core.storage import create_engine, init_db, sqlite_url


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

    assert manifest.depends == [
        "rss-fetcher",
        "api-fetcher",
        "reader",
        "advisor",
        "briefing-generator",
        "notifier",
    ]
    assert set(manifest.entity_imports) == {
        "entities/dags/default.yaml",
        "entities/nodes/rss-fetcher.yaml",
        "entities/nodes/api-fetcher.yaml",
        "entities/nodes/reader.yaml",
        "entities/nodes/advisor.yaml",
        "entities/nodes/briefing-generator.yaml",
        "entities/nodes/notifier.yaml",
        "entities/triggers/default-default-cron.yaml",
        "entities/sources/hn-rss.yaml",
        "entities/sources/cls-telegraph.yaml",
        "entities/sources/jqka.yaml",
        "entities/sources/solidot.yaml",
        "entities/sources/ithome.yaml",
        "entities/sources/github.yaml",
    }
    assert all("entity-relations" not in item and "stock" not in item for item in manifest.entity_imports)


def test_default_news_dependencies_are_declared() -> None:
    bootstrap = scan_extensions([Path("extensions")], Path("config"))

    assert any(manifest.name == "default-news-workflow" for manifest in bootstrap.manifests)


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
    config = await _runtime_config(tmp_path)
    store = EntityStore(config.entities, config.entity_types, config.entity_relations)

    for ref in DEFAULT_SOURCE_REFS:
        assert store.resolve(ref).type in {"rss-source", "api-source"}


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
    config = await _runtime_config(tmp_path)
    store = EntityStore(config.entities, config.entity_types, config.entity_relations)
    trigger = store.resolve("trigger:default-default-cron")

    assert trigger.attributes["wait_for"] == 'cron:"*/30 * * * *"'
    assert trigger.attributes["target"] == "dag:default"
    assert trigger.attributes["enabled"] is True


async def _runtime_config(tmp_path: Path):
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        return await load_runtime_app_config(Path("config"), engine, [Path("extensions")])
    finally:
        await engine.dispose()
