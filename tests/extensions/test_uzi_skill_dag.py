from __future__ import annotations

from pathlib import Path

import pytest

from stockimformation_core.bootstrap import scan_extensions
from stockimformation_core.config.entities import EntityStore
from stockimformation_core.config.loader import load_app_config
from stockimformation_core.dag.loader import load_graph, topological_layers
from stockimformation_core.dag.runner import DagRunner
from stockimformation_core.node.executor import NodeExecutor
from stockimformation_types import NodeOutput


def test_extension_manifest_loads() -> None:
    result = scan_extensions([Path("extensions")], Path("config"))

    assert "legacy-script-adapter" in result.handler_registry
    assert any(item.name == "uzi-skill" for item in result.manifests)


def test_uzi_skill_dag_loads() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(config.dags["uzi-skill-analysis"], config.nodes)

    assert len(graph.nodes) >= 45
    assert "assemble_report" in graph.nodes
    assert topological_layers(graph)


def test_uzi_skill_dag_uses_business_node_types() -> None:
    config = load_app_config(Path("config"))
    instances = config.dags["uzi-skill-analysis"].nodes
    uzi_types = {name for name in config.nodes if name.startswith("uzi-")}

    assert len(uzi_types) == len(instances)
    assert all(instance.type in uzi_types for instance in instances)
    assert all(instance.type != "legacy-script-adapter" for instance in instances)
    assert all(instance.alias for instance in instances)
    assert {config.nodes[instance.type].handler for instance in instances} == {"legacy-script-adapter"}


def test_resource_entity_resolves() -> None:
    resource = EntityStore().resolve("v8_isolate")

    assert resource.attributes["permits"] == 1


def test_mini_racer_fetchers_use_v8_isolate_resource() -> None:
    config = load_app_config(Path("config"))
    graph = load_graph(config.dags["uzi-skill-analysis"], config.nodes)

    assert graph.instances["7_industry"].resource == "v8_isolate"
    assert graph.instances["10_valuation"].resource == "v8_isolate"
    assert graph.instances["12_capital_flow"].resource == "v8_isolate"


def _use_mock_script(graph, script: Path | str) -> None:
    for node_id, instance in graph.instances.items():
        parameters = instance.config.setdefault("parameters", {})
        parameters["module_path"] = str(script)
        parameters["function"] = _mock_function(node_id)


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
    config = load_app_config(Path("config"))
    bootstrap = scan_extensions([Path("extensions")], Path("config"))
    graph = load_graph(config.dags["uzi-skill-analysis"], config.nodes)
    _use_mock_script(graph, script)
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
        if node_name == "1_financials":
            return NodeOutput(node_name=node_name, ok=False, error="fetch failed")
        return await original_execute(node_name, node_input, context)

    executor.execute = execute_with_failure

    result = await DagRunner(executor).run(graph, "cycle", {"ticker": "00100.HK"})

    assert result.failures["1_financials"] == "fetch failed"
    assert result.node_outputs["score_dimensions"].ok is True
    assert score_log.read_text(encoding="utf-8") == "True"


@pytest.mark.asyncio
async def test_full_dag_mock() -> None:
    config = load_app_config(Path("config"))
    bootstrap = scan_extensions([Path("extensions")], Path("config"))
    graph = load_graph(config.dags["uzi-skill-analysis"], config.nodes)
    _use_mock_script(graph, Path("tests/extensions/fixtures/uzi_skill_mock.py"))
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

    result = await DagRunner(executor).run(graph, "cycle", {"ticker": "00100.HK"})

    assert result.failures == {}
    assert result.node_outputs["assemble_report"].ok is True
    assert result.node_outputs["assemble_report"].payload["report_path"]
