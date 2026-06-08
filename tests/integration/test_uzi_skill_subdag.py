from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.config.loader import _load_runtime_base_config, load_runtime_app_config
from edera_core.dag.loader import load_graph, validate_sub_dag_nesting
from edera_core.extension_manager import ExtensionManager
from edera_core.storage import create_engine, init_db, sqlite_url


@pytest.mark.asyncio
async def test_uzi_subdag_runtime_topology(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    main = load_graph(config.dags["uzi-skill-analysis"], config.nodes, config.dags)
    data = load_graph(config.dags["uzi-data-collection"], config.nodes)
    scoring = load_graph(config.dags["uzi-scoring-synthesis"], config.nodes)
    rendering = load_graph(config.dags["uzi-rendering"], config.nodes)

    assert list(main.nodes) == ["data_collection", "scoring_synthesis", "rendering"]
    assert main.edges["data_collection"] == ["scoring_synthesis"]
    assert main.edges["scoring_synthesis"] == ["rendering"]
    assert main.edges["rendering"] == []
    assert len(data.nodes) == 26
    assert data.reverse_edges["autofill_mx"] == ["0_basic"]
    assert data.reverse_edges["autofill_playwright"] == ["0_basic"]
    assert all(data.instances[node].optional for node in _FETCH_NODES)
    assert {node: data.instances[node].resource for node in ("7_industry", "10_valuation", "12_capital_flow")} == {
        "7_industry": "v8_isolate",
        "10_valuation": "v8_isolate",
        "12_capital_flow": "v8_isolate",
    }
    analyst_nodes = [node for node in scoring.nodes if node.startswith("analyst_")]
    assert len(scoring.nodes) == 6
    assert len(analyst_nodes) == 3
    assert sum(len(edges) for edges in scoring.edges.values()) == 8
    assert scoring.edges["generate_panel"] == [*analyst_nodes, "generate_synthesis"]
    assert all(scoring.instances[node].type == "uzi-investor-analyst" for node in analyst_nodes)
    assert all(scoring.instances[node].resource == "pi_agent" for node in analyst_nodes)
    render_nodes = [node for node in rendering.nodes if node.startswith("render_")]
    assert len(rendering.nodes) == 22
    assert len(render_nodes) == 21
    assert all(rendering.instances[node].optional for node in render_nodes)
    assert all(rendering.edges[node] == ["assemble_report"] for node in render_nodes)
    assert rendering.reverse_edges["assemble_report"] == render_nodes
    assert rendering.edges["assemble_report"] == []
    validate_sub_dag_nesting(config.dags, 3)


@pytest.mark.asyncio
async def test_uzi_subdag_imports_aggregate_node(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    aggregate = config.nodes["uzi-aggregate-collection-results"]

    assert aggregate.type == "function"
    assert aggregate.handler == "legacy-script-adapter"
    assert {"uzi-skill-analysis", "uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering"}.issubset(config.dags)


async def _runtime_config(tmp_path: Path):
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        base = _load_runtime_base_config(Path("config"))
        manager = ExtensionManager(
            extensions_dir=Path("extensions"),
            handlers_dir=tmp_path / "handlers",
            engine=engine,
            config_entity_types=base.entity_types,
        )
        await manager.install("uzi-skill", installed_by="test")
        return await load_runtime_app_config(Path("config"), engine, [Path("extensions")])
    finally:
        await engine.dispose()


_FETCH_NODES = {
    "1_financials",
    "2_news",
    "3_macro",
    "4_market",
    "5_shareholder",
    "6_technical",
    "7_industry",
    "8_sentiment",
    "9_futures",
    "10_valuation",
    "11_moneyflow",
    "12_capital_flow",
    "13_policy",
    "14_events",
    "15_competitors",
    "16_risk",
    "17_estimates",
    "18_insider",
    "19_dividend",
    "20_liquidity",
    "21_regulatory",
    "22_ownership",
}
