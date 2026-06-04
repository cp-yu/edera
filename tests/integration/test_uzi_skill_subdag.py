from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_runtime_app_config
from edera_core.dag.loader import load_graph, validate_sub_dag_nesting
from edera_core.storage import create_engine, init_db, sqlite_url


@pytest.mark.asyncio
async def test_uzi_subdag_runtime_topology(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    main = load_graph(config.dags["uzi-skill-analysis"], config.nodes)
    data = load_graph(config.dags["uzi-data-collection"], config.nodes)
    scoring = load_graph(config.dags["uzi-scoring-synthesis"], config.nodes)

    assert len(main.nodes) == 5
    assert {node.id: node.dag_ref for node in config.dags["uzi-skill-analysis"].nodes if node.type == "dag"} == {
        "data_collection": "uzi-data-collection",
        "scoring_synthesis": "uzi-scoring-synthesis",
        "rendering": "uzi-rendering",
    }
    assert len(data.nodes) == 26
    assert data.reverse_edges["autofill_mx"] == ["0_basic"]
    assert data.reverse_edges["autofill_playwright"] == ["0_basic"]
    assert all(data.instances[node].optional for node in _FETCH_NODES)
    assert {node: data.instances[node].resource for node in ("7_industry", "10_valuation", "12_capital_flow")} == {
        "7_industry": "v8_isolate",
        "10_valuation": "v8_isolate",
        "12_capital_flow": "v8_isolate",
    }
    assert len(scoring.nodes) == 3
    assert sum(len(edges) for edges in scoring.edges.values()) == 2
    assert config.dags["uzi-rendering"].edges == []
    assert len(config.dags["uzi-rendering"].nodes) == 21
    validate_sub_dag_nesting(config.dags, 3)


@pytest.mark.asyncio
async def test_uzi_subdag_imports_aggregate_node(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    store = EntityStore(config.entities, config.entity_types, config.entity_relations)
    aggregate = store.resolve("node:uzi-aggregate-collection-results")

    assert aggregate.attributes["type"] == "function"
    assert aggregate.attributes["handler"] == "legacy-script-adapter"
    assert {"uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering"}.issubset(config.dags)


async def _runtime_config(tmp_path: Path):
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
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
