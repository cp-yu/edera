from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.bootstrap import load_installed_extensions
from edera_core.config.entities import EntityStore
from edera_core.config.loader import _load_runtime_base_config, load_runtime_app_config
from edera_core.config.schema import EntitiesConfig, EntityConfig
from edera_core.dag.loader import load_graph, validate_sub_dag_nesting
from edera_core.dag.resources import clear_semaphore_cache
from edera_core.dag.runner import DagRunner
from edera_core.extension_manager import ExtensionManager
from edera_core.node.executor import NodeExecutor
from edera_core.resolver import HandlerMeta, StaticHandlerResolver
from edera_core.snapshot import DagExecutionClosure, DagExecutionSnapshot
from edera_core.storage import create_engine, init_db, sqlite_url
from edera_types import NodeOutput

_PROJECT_ROOT = Path(__file__).parents[3]
_CONFIG_DIR = _PROJECT_ROOT / "config"
_EXTENSIONS_DIR = _PROJECT_ROOT / "extensions"


@pytest.mark.asyncio
async def test_extension_runtime_fixture_loads_uzi(extension_runtime) -> None:
    assert "uzi-skill-analysis" in extension_runtime.dags
    assert "uzi-investor-analyst" in extension_runtime.nodes
    assert "resource" in extension_runtime.entity_types


@pytest.mark.asyncio
async def test_uzi_stage_dags_load(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    graphs = {dag_name: load_graph(config.dags[dag_name], config.nodes) for dag_name in ("uzi-skill-analysis", "uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering")}

    assert list(graphs["uzi-skill-analysis"].nodes) == ["data_collection", "scoring_synthesis", "rendering"]
    assert len(graphs["uzi-data-collection"].nodes) == 26
    assert len(graphs["uzi-scoring-synthesis"].nodes) == 6
    assert len(graphs["uzi-rendering"].nodes) == 22


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
    handlers = {getattr(config.nodes[instance.type], "handler", None) for instance in instances}
    assert handlers == {"uzi-skill.legacy-script-adapter", None}
    assert config.nodes["uzi-investor-analyst"].type == "agent"
    assert config.nodes["uzi-investor-analyst"].model == "newapi/GLM-5.1"


@pytest.mark.asyncio
async def test_resource_entity_resolves(tmp_path: Path) -> None:
    config = await _runtime_config(tmp_path)
    store = _store(config)

    assert "resource" in config.entity_types
    assert config.dags["uzi-data-collection"].nodes[7].resource == "v8_isolate"
    assert config.dags["uzi-scoring-synthesis"].nodes[2].resource == "pi_agent"
    assert store.resolve("pi_agent").attributes["permits"] == 8


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
    main_graph = load_graph(config.dags["uzi-skill-analysis"], config.nodes, config.dags)
    data_graph = load_graph(config.dags["uzi-data-collection"], config.nodes)
    scoring_graph = load_graph(config.dags["uzi-scoring-synthesis"], config.nodes)
    rendering_graph = load_graph(config.dags["uzi-rendering"], config.nodes)

    assert main_graph.edges["data_collection"] == ["scoring_synthesis"]
    assert main_graph.edges["scoring_synthesis"] == ["rendering"]
    assert main_graph.edges["rendering"] == []
    assert main_graph.instances["data_collection"].type == "dag"
    assert main_graph.instances["data_collection"].dag_ref == "uzi-data-collection"
    assert main_graph.instances["scoring_synthesis"].type == "dag"
    assert main_graph.instances["scoring_synthesis"].dag_ref == "uzi-scoring-synthesis"
    assert main_graph.instances["rendering"].type == "dag"
    assert main_graph.instances["rendering"].dag_ref == "uzi-rendering"
    assert len(data_graph.nodes) == 26
    assert data_graph.reverse_edges["0_basic"] == []
    assert data_graph.reverse_edges["autofill_mx"] == ["0_basic"]
    assert data_graph.reverse_edges["autofill_playwright"] == ["0_basic"]
    assert data_graph.edges["aggregate_results"] == []
    assert all(data_graph.instances[node].optional for node in _FETCH_NODES)
    analyst_nodes = [node for node in scoring_graph.nodes if node.startswith("analyst_")]
    assert len(scoring_graph.nodes) == 6
    assert len(analyst_nodes) == 3
    assert sum(len(edges) for edges in scoring_graph.edges.values()) == 8
    assert scoring_graph.reverse_edges["score_dimensions"] == []
    assert scoring_graph.edges["generate_panel"] == [*analyst_nodes, "generate_synthesis"]
    assert scoring_graph.edges["generate_synthesis"] == []
    assert all(scoring_graph.instances[node].type == "uzi-investor-analyst" for node in analyst_nodes)
    assert all(scoring_graph.instances[node].optional for node in analyst_nodes)
    assert all(scoring_graph.instances[node].resource == "pi_agent" for node in analyst_nodes)
    render_nodes = [node for node in rendering_graph.nodes if node.startswith("render_")]
    assert len(rendering_graph.nodes) == 22
    assert len(render_nodes) == 21
    assert all(rendering_graph.instances[node].optional for node in render_nodes)
    assert not rendering_graph.instances["assemble_report"].optional
    assert all(rendering_graph.edges[node] == ["assemble_report"] for node in render_nodes)
    assert rendering_graph.reverse_edges["assemble_report"] == render_nodes
    assert rendering_graph.edges["assemble_report"] == []
    validate_sub_dag_nesting(config.dags, 3)


def _use_mock_script(config, script: Path | str) -> None:
    for dag_name in ("uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering"):
        for instance in config.dags[dag_name].nodes:
            if instance.type in {"dag", "uzi-aggregate-collection-results", "uzi-investor-analyst"}:
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
    config, bootstrap = await _runtime_config_with_bootstrap(tmp_path)
    data_graph = load_graph(config.dags["uzi-data-collection"], config.nodes)
    scoring_graph = load_graph(config.dags["uzi-scoring-synthesis"], config.nodes)
    _use_mock_script(config, script)
    store = _store(config)
    data_executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        _snapshot(config, bootstrap, tmp_path / "handlers"),
        data_graph.instances,
        store,
    )
    original_execute = data_executor.execute

    async def execute_with_failure(node_name, node_input, context=None):
        if node_name == "1_financials":
            return NodeOutput(node_name=node_name, ok=False, error="fetch failed")
        return await original_execute(node_name, node_input, context)

    data_executor.execute = execute_with_failure

    data_result = await DagRunner(data_executor, dags=config.dags, nodes=config.nodes).run(
        data_graph, "run", source_shared_inputs={"ticker": "00100.HK"}
    )
    scoring_executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        _snapshot(config, bootstrap, tmp_path / "handlers"),
        scoring_graph.instances,
        store,
    )
    scoring_result = await DagRunner(scoring_executor, dags=config.dags, nodes=config.nodes).run(
        scoring_graph, "run", source_shared_inputs=data_result.payload, retry_nodes={"score_dimensions"}
    )

    assert data_result.failures["1_financials"] == "fetch failed"
    assert scoring_result.failures == {}
    assert score_log.read_text(encoding="utf-8") == "True"


@pytest.mark.asyncio
async def test_function_stage_dags_mock(tmp_path: Path) -> None:
    config, bootstrap = await _runtime_config_with_bootstrap(tmp_path)
    _use_mock_script(config, Path(__file__).with_name("uzi_skill_mock.py"))
    store = _store(config)
    payload = {"ticker": "00100.HK"}

    for dag_name in ("uzi-data-collection", "uzi-scoring-synthesis", "uzi-rendering"):
        graph = load_graph(config.dags[dag_name], config.nodes)
        executor = NodeExecutor(
            config.nodes,
            config.system,
            config.runtime,
            _snapshot(config, bootstrap, tmp_path / "handlers"),
            graph.instances,
            store,
        )
        retry_nodes = {"score_dimensions"} if dag_name == "uzi-scoring-synthesis" else None
        result = await DagRunner(executor, dags=config.dags, nodes=config.nodes).run(
            graph, "run", source_shared_inputs=payload, retry_nodes=retry_nodes
        )
        assert result.failures == {}
        payload = result.node_outputs["score_dimensions"].payload if dag_name == "uzi-scoring-synthesis" else result.payload

    assert payload["report_path"] == "/tmp/uzi-skill-report.html"
    assert len(payload["sections"]) == 21
    assert all(section["html"] == "<section>ok</section>" for section in payload["sections"].values())


@pytest.mark.asyncio
async def test_scoring_dag_runs_three_analyst_agents(tmp_path: Path) -> None:
    config, bootstrap = await _runtime_config_with_bootstrap(tmp_path)
    fake_pi = tmp_path / "pi"
    fake_pi.write_text(
        "#!/bin/sh\n"
        "node=${EDERA_IDENTITY#node:}\n"
        "printf '{\"investor_id\":\"%s\",\"signal\":\"skip\",\"score\":0}\\n' \"$node\"\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    config.runtime = config.runtime.model_copy(update={"pi_bin": str(fake_pi)})
    store = _store(config)
    graph = load_graph(config.dags["uzi-scoring-synthesis"], config.nodes)
    analyst_nodes = [node for node in graph.nodes if node.startswith("analyst_")]
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        _snapshot(config, bootstrap, tmp_path / "handlers"),
        graph.instances,
        store,
        daemon_data_dir=tmp_path / "agents",
    )
    prefilled = {
        "generate_panel": NodeOutput(
            node_name="generate_panel",
            ok=True,
            payload={"prompt": "Return the JSON object for your Runtime context node_id."},
        )
    }

    result = await DagRunner(executor, dags=config.dags, nodes=config.nodes).run(
        graph,
        "run",
        retry_nodes=set(analyst_nodes),
        prefilled_outputs=prefilled,
    )

    assert result.failures == {}
    assert set(result.node_outputs) == {"generate_panel", *analyst_nodes}
    assert all(result.node_outputs[node].ok for node in analyst_nodes)
    for node in analyst_nodes:
        assert f'"investor_id":"{node}"' in result.node_outputs[node].payload["stdout"]


@pytest.mark.asyncio
async def test_rendering_assembles_report(tmp_path: Path) -> None:
    config, bootstrap = await _runtime_config_with_bootstrap(tmp_path)
    graph = load_graph(config.dags["uzi-rendering"], config.nodes)
    _use_mock_script(config, Path(__file__).with_name("uzi_skill_mock.py"))
    store = _store(config)
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        _snapshot(config, bootstrap, tmp_path / "handlers"),
        graph.instances,
        store,
    )
    result = await DagRunner(executor, dags=config.dags, nodes=config.nodes).run(graph, "run", source_shared_inputs={"score": 1})

    assert result.failures == {}
    assert result.payload["report_path"] == "/tmp/uzi-skill-report.html"
    assert len(result.payload["sections"]) == 21
    assert all(section["html"] == "<section>ok</section>" for section in result.payload["sections"].values())


@pytest.mark.asyncio
async def test_rendering_omits_failed_optional_section(tmp_path: Path) -> None:
    config, bootstrap = await _runtime_config_with_bootstrap(tmp_path)
    graph = load_graph(config.dags["uzi-rendering"], config.nodes)
    _use_mock_script(config, Path(__file__).with_name("uzi_skill_mock.py"))
    store = _store(config)
    executor = NodeExecutor(
        config.nodes,
        config.system,
        config.runtime,
        _snapshot(config, bootstrap, tmp_path / "handlers"),
        graph.instances,
        store,
    )
    original_execute = executor.execute

    async def execute_with_failure(node_name, node_input, context=None):
        if node_name == "render_01_summary":
            return NodeOutput(node_name=node_name, ok=False, error="render failed")
        return await original_execute(node_name, node_input, context)

    executor.execute = execute_with_failure

    result = await DagRunner(executor, dags=config.dags, nodes=config.nodes).run(graph, "run", source_shared_inputs={"score": 1})

    assert result.failures["render_01_summary"] == "render failed"
    assert result.payload["report_path"] == "/tmp/uzi-skill-report.html"
    assert len(result.payload["sections"]) == 20


async def _runtime_config(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        await _install_uzi_extension(engine, tmp_path)
        return await load_runtime_app_config(_CONFIG_DIR, engine, [_EXTENSIONS_DIR])
    finally:
        await engine.dispose()


async def _runtime_config_with_bootstrap(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    engine = create_engine(sqlite_url(tmp_path / "runtime.db"))
    try:
        await init_db(engine)
        await _install_uzi_extension(engine, tmp_path)
        config = await load_runtime_app_config(_CONFIG_DIR, engine, [_EXTENSIONS_DIR])
        from edera_core.storage import session_factory

        async with session_factory(engine)() as session:
            bootstrap = await load_installed_extensions(session, tmp_path / "handlers")
        return config, bootstrap
    finally:
        await engine.dispose()


async def _install_uzi_extension(engine, tmp_path: Path) -> None:
    base = _load_runtime_base_config(_CONFIG_DIR)
    manager = ExtensionManager(
        extensions_dir=_EXTENSIONS_DIR,
        handlers_dir=tmp_path / "handlers",
        engine=engine,
        config_entity_types=base.entity_types,
    )
    await manager.install("uzi-skill", installed_by="test")


def _snapshot(config, bootstrap, handlers_dir: Path) -> DagExecutionSnapshot:
    handlers = {}
    for manifest in bootstrap.manifests:
        for handler in manifest.handlers:
            package = getattr(handler, "package", "") or handler.name
            handlers[handler.name] = HandlerMeta(handlers_dir / package / handler.entry, extension_name=manifest.name)
    return DagExecutionSnapshot(
        DagExecutionClosure("uzi-test", config.dags, config.nodes),
        config.entity_types,
        StaticHandlerResolver(handlers),
        bootstrap.table_names,
        config.skills,
    )


def _store(config) -> EntityStore:
    clear_semaphore_cache()
    entities = EntitiesConfig(
        entities=[
            *config.entities.entities,
            EntityConfig(id="v8_isolate", type="resource", attributes={"id": "v8_isolate", "permits": 1}),
            EntityConfig(id="pi_agent", type="resource", attributes={"id": "pi_agent", "permits": 8}),
        ]
    )
    return EntityStore(entities, config.entity_types, config.entity_relations)


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
