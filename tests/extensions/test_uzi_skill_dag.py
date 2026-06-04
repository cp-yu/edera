from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.bootstrap import scan_extensions
from edera_core.config.entities import EntityStore
from edera_core.config.loader import load_runtime_app_config
from edera_core.dag.loader import load_graph, validate_sub_dag_nesting
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.storage import create_engine, init_db, sqlite_url
from edera_types import NodeOutput


def test_extension_manifest_loads() -> None:
    result = scan_extensions([Path("extensions")], Path("config"))

    assert "legacy-script-adapter" in result.handler_registry
    assert any(item.name == "uzi-skill" for item in result.manifests)


@pytest.mark.asyncio
async def test_uzi_stage_dags_load(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    graphs = {
        dag_name: load_graph(config.dags[dag_name], config.nodes)
        for dag_name in ("uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering")
    }

    assert "uzi-skill-analysis" not in config.dags
    assert len(graphs["uzi-data-collection"].nodes) == 26
    assert len(graphs["uzi-scoring-synthesis"].nodes) == 3
    assert len(graphs["uzi-rendering"].nodes) == 21


@pytest.mark.asyncio
async def test_uzi_skill_dag_uses_business_node_types(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    instances = [
        instance
        for dag_name in ("uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering")
        for instance in config.dags[dag_name].nodes
        if instance.type != "dag"
    ]
    uzi_types = {name for name in config.nodes if name.startswith("uzi-")}

    assert all(instance.type in uzi_types for instance in instances)
    assert all(instance.type != "legacy-script-adapter" for instance in instances)
    assert all(instance.alias for instance in instances)
    assert {config.nodes[instance.type].handler for instance in instances} == {"legacy-script-adapter"}


@pytest.mark.asyncio
async def test_resource_entity_resolves(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    resource = EntityStore(config.entities, config.entity_types, config.entity_relations).resolve("v8_isolate")

    assert resource.attributes["permits"] == 1


@pytest.mark.asyncio
async def test_mini_racer_fetchers_use_v8_isolate_resource(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    graph = load_graph(config.dags["uzi-data-collection"], config.nodes)

    assert graph.instances["7_industry"].resource == "v8_isolate"
    assert graph.instances["10_valuation"].resource == "v8_isolate"
    assert graph.instances["12_capital_flow"].resource == "v8_isolate"


@pytest.mark.asyncio
async def test_uzi_sub_dag_topology(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    data_graph = load_graph(config.dags["uzi-data-collection"], config.nodes)
    scoring_graph = load_graph(config.dags["uzi-scoring-synthesis"], config.nodes)
    rendering = config.dags["uzi-rendering"]

    assert len(data_graph.nodes) == 26
    assert data_graph.reverse_edges["0_basic"] == []
    assert data_graph.reverse_edges["autofill_mx"] == ["0_basic"]
    assert data_graph.reverse_edges["autofill_playwright"] == ["0_basic"]
    assert data_graph.edges["aggregate_results"] == []
    assert all(data_graph.instances[node].optional for node in _FETCH_NODES)
    assert len(scoring_graph.nodes) == 3
    assert sum(len(edges) for edges in scoring_graph.edges.values()) == 2
    assert scoring_graph.reverse_edges["score_dimensions"] == []
    assert scoring_graph.edges["generate_synthesis"] == []
    assert len(rendering.nodes) == 21
    assert all(node.optional for node in rendering.nodes)
    assert rendering.edges == []
    validate_sub_dag_nesting(config.dags, 3)


def _use_mock_script(config, script: Path | str) -> None:
    for dag_name in ("uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering"):
        for instance in config.dags[dag_name].nodes:
            if instance.type in {"dag", "uzi-aggregate-collection-results"}:
                continue
            _set_mock_parameters(config, instance.type, str(script), _mock_function(instance.id))


def _set_mock_parameters(config, node_type: str, script: str, function: str) -> None:
    config.nodes[node_type].parameters["module_path"] = script
    config.nodes[node_type].parameters["function"] = function
    for entity in config.entities.entities:
        if entity.type == "node" and entity.attributes.get("name") == node_type:
            parameters = entity.attributes.setdefault("parameters", {})
            parameters["module_path"] = script
            parameters["function"] = function


def _mock_function(node_id: str) -> str:
    if node_id == "preflight":
        return "preflight"
    if node_id == "score_dimensions":
        return "score"
    if node_id == "assemble_report":
        return "assemble"
    if node_id.startswith("render_"):
        return "render"
    if node_id in {"3_macro", "7_industry", "9_futures", "13_policy"}:
        return "fetch_by_industry"
    if node_id in {"autofill_mx", "autofill_playwright", "generate_panel", "generate_synthesis"}:
        return "passthrough"
    return "fetch"


@pytest.mark.asyncio
async def test_optional_fetcher_failure_reaches_score_as_none(tmp_path: Path) -> None:
    score_log = tmp_path / "score.log"
    script = tmp_path / "uzi_optional.py"
    script.write_text(
        "from pathlib import Path\n"
        f"SCORE_LOG = Path({str(score_log)!r})\n"
        "def preflight(ticker): return {'ticker': ticker, 'data': {'industry': 'AI'}}\n"
        "def fetch(ticker): return {'ticker': ticker, 'data': {'industry': 'AI'}}\n"
        "def fetch_by_industry(industry): return {'industry': industry}\n"
        "def passthrough(payload): return payload\n"
        "def fail(ticker): raise RuntimeError('fetch failed')\n"
        "def score(payload):\n"
        "    values = payload.values() if isinstance(payload, dict) else payload\n"
        "    SCORE_LOG.write_text(str(any(item is None for item in values)), encoding='utf-8')\n"
        "    return {'score': 1}\n"
        "def render(payload): return {'html': 'ok'}\n"
        "def assemble(payload): return {'report_path': '/tmp/uzi-skill-report.html'}\n",
        encoding="utf-8",
    )
    config = await _runtime_config(tmp_path)
    bootstrap = scan_extensions([Path("extensions")], Path("config"))
    data_graph = load_graph(config.dags["uzi-data-collection"], config.nodes)
    scoring_graph = load_graph(config.dags["uzi-scoring-synthesis"], config.nodes)
    _use_mock_script(config, script)
    store = EntityStore(config.entities, config.entity_types, config.entity_relations)
    data_executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        bootstrap.handler_registry,
        data_graph.instances,
        store,
        extension_tables=bootstrap.table_names,
    )
    original_execute = data_executor.execute

    async def execute_with_failure(node_name, node_input, context=None):
        if node_name == "1_financials":
            return NodeOutput(node_name=node_name, ok=False, error="fetch failed")
        return await original_execute(node_name, node_input, context)

    data_executor.execute = execute_with_failure

    data_result = await DagRunner(data_executor, dags=config.dags, nodes=config.nodes).run(
        data_graph, "run", {"ticker": "00100.HK"}
    )
    scoring_executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        bootstrap.handler_registry,
        scoring_graph.instances,
        store,
        extension_tables=bootstrap.table_names,
    )
    scoring_result = await DagRunner(scoring_executor, dags=config.dags, nodes=config.nodes).run(
        scoring_graph, "run", data_result.payload
    )

    assert data_result.failures["1_financials"] == "fetch failed"
    assert scoring_result.failures == {}
    assert score_log.read_text(encoding="utf-8") == "True"


@pytest.mark.asyncio
async def test_stage_dags_mock(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    bootstrap = scan_extensions([Path("extensions")], Path("config"))
    _use_mock_script(config, Path("tests/extensions/fixtures/uzi_skill_mock.py"))
    store = EntityStore(config.entities, config.entity_types, config.entity_relations)
    payload = {"ticker": "00100.HK"}

    for dag_name in ("uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering"):
        graph = load_graph(config.dags[dag_name], config.nodes)
        executor = NodeExecutor(
            config.nodes,
            config.system,
            config.runtime,
            bootstrap.handler_registry,
            graph.instances,
            store,
            extension_tables=bootstrap.table_names,
        )
        result = await DagRunner(executor, dags=config.dags, nodes=config.nodes).run(graph, "run", payload)
        assert result.failures == {}
        payload = result.payload

    assert len(payload) == 21


@pytest.mark.asyncio
async def test_rendering_sub_dag_omits_failed_optional_sink(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    bootstrap = scan_extensions([Path("extensions")], Path("config"))
    graph = load_graph(config.dags["uzi-rendering"], config.nodes)
    _use_mock_script(config, Path("tests/extensions/fixtures/uzi_skill_mock.py"))
    store = EntityStore(config.entities, config.entity_types, config.entity_relations)
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        bootstrap.handler_registry,
        graph.instances,
        store,
        extension_tables=bootstrap.table_names,
    )
    original_execute = executor.execute

    async def execute_with_failure(node_name, node_input, context=None):
        if node_name == "render_01_summary":
            return NodeOutput(node_name=node_name, ok=False, error="render failed")
        return await original_execute(node_name, node_input, context)

    executor.execute = execute_with_failure

    result = await DagRunner(executor, dags=config.dags, nodes=config.nodes).run(graph, "run", {"score": 1})

    assert result.failures["render_01_summary"] == "render failed"
    assert len(result.payload) == 20
    assert None not in result.payload


@pytest.mark.asyncio
async def test_uzi_workflow_import_boundary(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    store = EntityStore(config.entities, config.entity_types, config.entity_relations)

    assert not Path("config/dags/uzi-skill-analysis.yaml").exists()
    assert not Path("config/triggers/uzi-skill-analysis-default-cron.yaml").exists()
    assert not any(Path("config/nodes").glob("uzi-*.yaml"))
    imported = {entity.id for entity in store.query()}
    assert "uzi-skill-analysis" not in imported
    assert "trigger:uzi-skill-analysis-default-cron" not in imported
    assert {"uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering", "uzi-aggregate-collection-results"}.issubset(imported)


async def _runtime_config(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
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
