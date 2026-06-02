from __future__ import annotations

import pytest
from pydantic import ValidationError

from edera_core.config.schema import AgentNodeConfig, DagNodeConfig, FunctionNodeConfig, NodeConfig, WaitNodeConfig


def test_variant_deserializes_wait_node() -> None:
    config = NodeConfig.model_validate(
        {
            "name": "gate",
            "type": "wait",
            "input_type": "Any",
            "output_type": "Any",
            "wait_for": "event:approve:abc",
        }
    )

    assert isinstance(config, WaitNodeConfig)
    assert config.consume is True


def test_blank_wait_for_rejected() -> None:
    with pytest.raises(ValidationError):
        NodeConfig.model_validate(
            {
                "name": "gate",
                "type": "wait",
                "input_type": "Any",
                "output_type": "Any",
                "wait_for": " ",
            }
        )


def test_existing_variants_unchanged() -> None:
    function = NodeConfig.model_validate(
        {"name": "reader", "type": "function", "handler": "reader", "input_type": "Any", "output_type": "Any"}
    )
    agent = NodeConfig.model_validate(
        {"name": "agent", "type": "agent", "model": "gpt", "input_type": "Any", "output_type": "Any"}
    )
    dag = NodeConfig.model_validate(
        {"name": "child", "type": "dag", "dag_ref": "child", "input_type": "Any", "output_type": "Any"}
    )

    assert isinstance(function, FunctionNodeConfig)
    assert isinstance(agent, AgentNodeConfig)
    assert isinstance(dag, DagNodeConfig)
