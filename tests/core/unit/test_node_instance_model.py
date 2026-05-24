import pytest
from pydantic import ValidationError

from stockimformation_core.config.schema import DagNodeInstance, NodeConfig


def test_entities_field() -> None:
    instance = DagNodeInstance(
        id="node-1",
        type="rss-fetcher",
        config={"entities": ["stock:00700.HK"], "entity_permissions": {"stock": {"code": "read-write"}}},
    )
    assert instance.config["entities"] == ["stock:00700.HK"]


def test_node_config_has_tools_without_model() -> None:
    fields = NodeConfig.model_fields

    assert "tools" in fields
    assert "model" not in fields


def test_instance_config_accepts_session_tools_and_model() -> None:
    instance = DagNodeInstance(
        id="node-1",
        type="reader",
        config={
            "session_dir": "sandbox:reader:latest",
            "tools": ["bash", "read"],
            "model": "hf-share/deepseek-v4-flash",
        },
    )

    assert instance.config["tools"] == ["bash", "read"]


def test_instance_config_rejects_unknown_tool() -> None:
    with pytest.raises(ValidationError):
        DagNodeInstance(id="node-1", type="reader", config={"tools": ["network"]})
