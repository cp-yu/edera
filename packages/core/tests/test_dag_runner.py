from __future__ import annotations

import pytest

from edera_core.config.schema import DagConfig, DagNodeConfig, DagNodeInstance, RuntimeSettings, SystemConfig
from edera_core.dag.loader import DagPathStep, load_graph, validate_sub_dag_nesting
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor


def _dag(name: str, nodes: list[dict[str, str]], edges: list[dict[str, str]] | None = None) -> DagConfig:
    return DagConfig(
        name=name,
        nodes=[DagNodeInstance(**n) for n in nodes],
        edges=edges or [],
        ui={},
    )


# --- C10: Runtime cycle error format ---


@pytest.mark.asyncio
async def test_runtime_cycle_error_format():
    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])
    nodes = {}
    executor = NodeExecutor(nodes, system=SystemConfig(), runtime=RuntimeSettings())
    executor.dag_executor = lambda *a: None

    runner = DagRunner(
        executor,
        dags={"demo": demo},
        nodes=nodes,
        depth=1,
        path=(DagPathStep(dag_name="demo"),),
    )

    output = await runner._execute_sub_dag(
        demo.nodes[0],
        "demo",
        {},
        type("Input", (), {"run_id": "r1", "payload": None, "metadata": {}})(),
    )

    assert not output.ok
    assert "Sub DAG cycle detected" in output.error
    assert "节点 'sub-1'" in output.error
    assert "修复建议" in output.error


# --- C11: Runtime and save-time message consistency ---


@pytest.mark.asyncio
async def test_runtime_save_error_consistency():
    from edera_core.errors import DagError

    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])

    # Save-time error
    with pytest.raises(DagError) as save_exc:
        validate_sub_dag_nesting({"demo": demo}, max_depth=10)
    save_msg = str(save_exc.value)

    # Runtime error
    nodes = {}
    executor = NodeExecutor(nodes, system=SystemConfig(), runtime=RuntimeSettings())
    executor.dag_executor = lambda *a: None

    runner = DagRunner(
        executor,
        dags={"demo": demo},
        nodes=nodes,
        depth=1,
        path=(DagPathStep(dag_name="demo"),),
    )
    output = await runner._execute_sub_dag(
        demo.nodes[0],
        "demo",
        {},
        type("Input", (), {"run_id": "r1", "payload": None, "metadata": {}})(),
    )

    assert save_msg == output.error


@pytest.mark.asyncio
async def test_runtime_save_error_consistency_multilayer_run():
    from edera_core.errors import DagError

    pipeline_a = _dag("pipeline-a", [{"id": "step-b", "type": "pipeline-b"}])
    pipeline_b = _dag("pipeline-b", [{"id": "step-c", "type": "pipeline-c"}])
    pipeline_c = _dag("pipeline-c", [{"id": "back-to-a", "type": "pipeline-a"}])
    dags = {dag.name: dag for dag in (pipeline_a, pipeline_b, pipeline_c)}
    nodes = {
        dag.name: DagNodeConfig(
            name=dag.name,
            type="dag",
            dag_ref=dag.name,
            input_type="Any",
            output_type="Any",
        )
        for dag in dags.values()
    }

    with pytest.raises(DagError) as save_exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    executor = NodeExecutor(nodes, system=SystemConfig(), runtime=RuntimeSettings())
    result = await DagRunner(executor, dags=dags, nodes=nodes).run(
        load_graph(pipeline_a, nodes, dags),
        "run-1",
        None,
    )

    assert result.failures["step-b"] == str(save_exc.value)


@pytest.mark.asyncio
async def test_runtime_save_error_consistency_nested_non_root_cycle():
    from edera_core.errors import DagError

    pipeline_a = _dag("pipeline-a", [{"id": "step-b", "type": "pipeline-b"}])
    pipeline_b = _dag("pipeline-b", [{"id": "step-c", "type": "pipeline-c"}])
    pipeline_c = _dag("pipeline-c", [{"id": "back-to-b", "type": "pipeline-b"}])
    dags = {dag.name: dag for dag in (pipeline_a, pipeline_b, pipeline_c)}
    nodes = {
        dag.name: DagNodeConfig(
            name=dag.name,
            type="dag",
            dag_ref=dag.name,
            input_type="Any",
            output_type="Any",
        )
        for dag in dags.values()
    }

    with pytest.raises(DagError) as save_exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    executor = NodeExecutor(nodes, system=SystemConfig(), runtime=RuntimeSettings())
    result = await DagRunner(executor, dags=dags, nodes=nodes).run(
        load_graph(pipeline_a, nodes, dags),
        "run-1",
        None,
    )

    assert result.failures["step-b"] == str(save_exc.value)
