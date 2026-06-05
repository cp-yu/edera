from __future__ import annotations

import asyncio

import pytest

from edera_core.config.schema import DagConfig, DagNodeInstance, RuntimeSettings, SystemConfig
from edera_core.dag.loader import DagPathStep
from edera_core.dag.runner import DagRunner
from edera_core.node.executor import NodeExecutor
from edera_core.node.models import NodeOutput


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
    from edera_core.dag.loader import validate_sub_dag_nesting
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
