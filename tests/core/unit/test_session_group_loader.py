import pytest

from edera_core.dag.session_loader import inject_implicit_session_resources
from edera_core.config.schema import DagNodeInstance, DagConfig


def test_inject_session_resource_for_same_dag_group():
    """C10: 验证隐式 resource 零配置注入"""
    instances = [
        DagNodeInstance(id="a", type="agent", config={"session": "task-1"}),
        DagNodeInstance(id="b", type="agent", config={"session": "task-1"}),
        DagNodeInstance(id="c", type="function", config={}),
    ]
    dag_config = DagConfig(name="test-dag", nodes=instances, edges=[])

    result = inject_implicit_session_resources(dag_config)

    # a 和 b 应该被注入 session:test-dag/task-1 resource
    assert result["a"].resource == "session:test-dag/task-1"
    assert result["b"].resource == "session:test-dag/task-1"
    # c 没有 session，不注入
    assert result["c"].resource is None or result["c"].resource == ""


def test_inject_cross_dag_session_resource():
    """C11: 验证跨 DAG 引用挂源组 resource"""
    instances = [
        DagNodeInstance(id="x", type="agent", config={"session": "relay-main/task-1@latest"}),
        DagNodeInstance(id="y", type="agent", config={"session": "relay-main/task-1@list"}),
    ]
    dag_config = DagConfig(name="relay-skill", nodes=instances, edges=[])

    result = inject_implicit_session_resources(dag_config)

    # x 和 y 应该挂载源 DAG 的 session resource
    assert result["x"].resource == "session:relay-main/task-1"
    assert result["y"].resource == "session:relay-main/task-1"


def test_inject_preserves_user_resources():
    """用户已配置 resource 应与隐式 resource 共存"""
    instances = [
        DagNodeInstance(
            id="a",
            type="agent",
            config={"session": "task-1"},
            resource="user-resource",
        ),
    ]
    dag_config = DagConfig(name="test-dag", nodes=instances, edges=[])

    result = inject_implicit_session_resources(dag_config)

    # 隐式和用户 resource 共存，按字母排序
    resources = result["a"].resource.split(",")
    assert set(resources) == {"session:test-dag/task-1", "user-resource"}


def test_inject_no_session_no_resource():
    """未声明 session 的节点不注入"""
    instances = [
        DagNodeInstance(id="a", type="function", config={}),
        DagNodeInstance(id="b", type="agent", config={}),
    ]
    dag_config = DagConfig(name="test-dag", nodes=instances, edges=[])

    result = inject_implicit_session_resources(dag_config)

    assert result["a"].resource is None or result["a"].resource == ""
    assert result["b"].resource is None or result["b"].resource == ""
