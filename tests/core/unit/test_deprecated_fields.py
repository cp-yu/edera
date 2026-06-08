import pytest
from pydantic import ValidationError

from edera_core.config.schema import DagConfig, NodeConfig


def test_input_binding_error() -> None:
    with pytest.raises(ValidationError, match="input_binding.*sourceSharedInputs.*nodeInputs"):
        NodeConfig.model_validate(
            {
                "name": "source",
                "type": "function",
                "role": "source",
                "handler": "read",
                "input_type": "Any",
                "output_type": "Any",
                "input_binding": "symbol",
            }
        )


def test_dag_inputs_error() -> None:
    with pytest.raises(ValidationError, match="DAG.inputs.*sourceSharedInputs.*nodeInputs"):
        DagConfig.model_validate(
            {
                "name": "default",
                "inputs": [{"name": "symbol", "type": "string"}],
                "nodes": [{"id": "source", "type": "source"}],
                "edges": [],
            }
        )
