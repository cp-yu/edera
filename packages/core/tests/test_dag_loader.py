from __future__ import annotations

import pytest

from edera_core.config.schema import DagConfig, DagNodeInstance
from edera_core.dag.loader import DagPathStep, validate_sub_dag_nesting, _visit_sub_dag, _format_cycle_error
from edera_core.errors import DagError


def _dag(name: str, nodes: list[dict[str, str]], edges: list[dict[str, str]] | None = None) -> DagConfig:
    return DagConfig(
        name=name,
        nodes=[DagNodeInstance(**n) for n in nodes],
        edges=edges or [],
        ui={},
    )


# --- C1: DagPathStep dataclass ---


def test_dag_path_step_fields():
    step = DagPathStep(dag_name="demo", via_node_id="sub-1")
    assert step.dag_name == "demo"
    assert step.via_node_id == "sub-1"

    root = DagPathStep(dag_name="root", via_node_id=None)
    assert root.dag_name == "root"
    assert root.via_node_id is None


# --- C2: Direct self-reference path tracking ---


def test_direct_self_reference_path():
    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])
    dags = {"demo": demo}

    with pytest.raises(DagError) as exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    msg = str(exc.value)
    assert "demo" in msg
    assert "sub-1" in msg


# --- C3: Multilayer cycle path tracking ---


def test_multilayer_cycle_path():
    a = _dag("pipeline-a", [{"id": "step-b", "type": "dag", "dag_ref": "pipeline-b"}])
    b = _dag("pipeline-b", [{"id": "step-c", "type": "dag", "dag_ref": "pipeline-c"}])
    c = _dag("pipeline-c", [{"id": "back-to-a", "type": "dag", "dag_ref": "pipeline-a"}])
    dags = {"pipeline-a": a, "pipeline-b": b, "pipeline-c": c}

    with pytest.raises(DagError) as exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    msg = str(exc.value)
    assert "step-b" in msg
    assert "step-c" in msg
    assert "back-to-a" in msg
    assert "pipeline-a" in msg
    assert "pipeline-b" in msg
    assert "pipeline-c" in msg


# --- C4: Error message title format ---


def test_error_message_title():
    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])
    dags = {"demo": demo}

    with pytest.raises(DagError) as exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    msg = str(exc.value)
    assert msg.startswith("无法保存 DAG 'demo'：检测到 Sub DAG 循环 (Sub DAG cycle detected)")


# --- C5: Error message cycle path format ---


def test_error_message_cycle_path():
    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])
    dags = {"demo": demo}

    with pytest.raises(DagError) as exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    msg = str(exc.value)
    assert "循环路径：" in msg
    assert "demo" in msg
    assert "sub-1" in msg


# --- C6: Error message problem description ---


def test_error_message_problem():
    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])
    dags = {"demo": demo}

    with pytest.raises(DagError) as exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    msg = str(exc.value)
    assert "问题：Sub DAG 引用形成了循环。" in msg


# --- C7: Error message fix suggestion ---


def test_error_message_fix_suggestion():
    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])
    dags = {"demo": demo}

    with pytest.raises(DagError) as exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    msg = str(exc.value)
    assert "修复建议" in msg
    assert "sub-1" in msg


# --- C8: Bilingual format ---


def test_error_message_bilingual():
    demo = _dag("demo", [{"id": "sub-1", "type": "dag", "dag_ref": "demo"}])
    dags = {"demo": demo}

    with pytest.raises(DagError) as exc:
        validate_sub_dag_nesting(dags, max_depth=10)

    msg = str(exc.value)
    assert "Sub DAG cycle detected" in msg
    assert "循环路径" in msg
