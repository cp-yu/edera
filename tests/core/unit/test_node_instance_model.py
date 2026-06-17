import pytest
from pydantic import ValidationError

from edera_core.config.schema import AgentNodeConfig, DagNodeInstance, FunctionNodeConfig, NodeConfig


def test_entities_field() -> None:
    instance = DagNodeInstance(
        id="node-1",
        type="rss-fetcher",
        config={"entities": ["stock:00700.HK"], "entity_permissions": {"stock": {"code": "read-write"}}},
    )
    assert instance.config["entities"] == ["stock:00700.HK"]


def test_function_node_config_has_no_tools_field() -> None:
    """D6: tools 字段收归 AgentNodeConfig，function 节点不携带 tools"""
    fields = FunctionNodeConfig.model_fields

    assert "tools" not in fields
    assert "model" not in fields


def test_agent_node_config_has_tools_field() -> None:
    """D6: tools 仅存在于 AgentNodeConfig"""
    fields = AgentNodeConfig.model_fields

    assert "tools" in fields


def test_function_node_rejects_tools_on_validate() -> None:
    """D6: function 节点加载时拒绝 tools 字段"""
    with pytest.raises(ValidationError):
        NodeConfig.model_validate(
            {
                "name": "reader",
                "type": "function",
                "handler": "reader",
                "input_type": "Any",
                "output_type": "Any",
                "tools": ["bash"],
            }
        )


def test_instance_config_accepts_session_tools_and_model() -> None:
    instance = DagNodeInstance(
        id="node-1",
        type="reader",
        config={
            "session": "task-1",
            "tools": ["bash", "read"],
            "model": "hf-share/deepseek-v4-flash",
        },
    )

    assert instance.config["tools"] == ["bash", "read"]
    assert instance.config["session"] == "task-1"


def test_instance_config_rejects_unknown_tool() -> None:
    with pytest.raises(ValidationError):
        DagNodeInstance(id="node-1", type="reader", config={"tools": ["network"]})


def test_session_field_accepts_group_name():
    """C2: 验证组名与跨 DAG 引用格式通过校验 - 组名部分"""
    instance = DagNodeInstance(
        id="test-node",
        type="agent",
        config={"session": "task-1"},
    )
    assert instance.config["session"] == "task-1"


def test_session_field_accepts_cross_dag_latest():
    """C2: 验证组名与跨 DAG 引用格式通过校验 - @latest 引用"""
    instance = DagNodeInstance(
        id="test-node",
        type="agent",
        config={"session": "relay-main/task-1@latest"},
    )
    assert instance.config["session"] == "relay-main/task-1@latest"


def test_session_field_accepts_cross_dag_list():
    """C2: 验证组名与跨 DAG 引用格式通过校验 - @list 引用"""
    instance = DagNodeInstance(
        id="test-node",
        type="agent",
        config={"session": "relay-main/task-1@list"},
    )
    assert instance.config["session"] == "relay-main/task-1@list"


def test_session_field_rejects_invalid_format_triple_slash():
    """C3: 验证非法格式被拒绝 - 三段路径"""
    with pytest.raises(ValidationError, match="session"):
        DagNodeInstance(
            id="test-node",
            type="agent",
            config={"session": "a/b/c@latest"},
        )


def test_session_field_rejects_unknown_mode():
    """C3: 验证非法格式被拒绝 - 未知模式"""
    with pytest.raises(ValidationError, match="session"):
        DagNodeInstance(
            id="test-node",
            type="agent",
            config={"session": "task-1@unknown"},
        )
