from pathlib import Path

import pytest

from edera_core.config.schema import DagConfig, EntitiesConfig, EntityTypeConfig, NodeConfig, SkillConfig
from edera_core.config.editor import RuntimeConfigEditor
from edera_core.errors import ConfigEditError
from edera_core.service_common import build_inspector_schema, graph_dag_payload, graph_node_payload


def test_config_editor_rejects_invalid_system_without_writing(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    original = (root / "config" / "system.toml").read_text()
    with pytest.raises(ConfigEditError):
        editor.save("system", "system", original.replace("schedule_minutes = 30", "schedule_minutes = 0"))
    assert (root / "config" / "system.toml").read_text() == original


def test_config_editor_rejects_invalid_dag(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    original = (root / "config" / "dags" / "default.yaml").read_text()
    invalid = original + "\n  - from: notifier\n    to: rss-fetcher\n"
    with pytest.raises(ConfigEditError):
        editor.save("dag", "default", invalid)
    assert (root / "config" / "dags" / "default.yaml").read_text() == original


def test_config_editor_rejects_invalid_dag_entity_permissions(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    path = root / "config" / "dags" / "default.yaml"
    original = path.read_text()
    invalid = original.replace(
        "    model: hf-share/deepseek-v4-flash\n",
        "    model: hf-share/deepseek-v4-flash\n"
        "    entity_permissions:\n"
        "      stock:\n"
        "        holding: read-only\n",
    )
    with pytest.raises(ConfigEditError):
        editor.save("dag", "default", invalid)
    assert path.read_text() == original


def test_config_editor_rejects_skill_path_traversal(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    with pytest.raises(ConfigEditError):
        editor.save("skill", "../outside.md", "x")


def test_config_editor_saves_skill_atomically(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    saved = editor.save("skill", "fetch-rss/skill.md", "# skill\n")
    assert Path(saved.path).read_text() == "# skill\n"


def test_node_config_accepts_json_like_parameters() -> None:
    node = NodeConfig.model_validate(
        {
            "name": "reader",
            "type": "function",
            "handler": "summarize",
            "input_type": "list[RawItem]",
            "output_type": "list[AnalysisResult]",
            "parameters": {"confidence_threshold": 0.55, "signals": ["earnings", "guidance"]},
        }
    )
    assert node.parameters["confidence_threshold"] == 0.55


def test_node_config_accepts_parameters_schema() -> None:
    node = NodeConfig.model_validate(
        {
            "name": "reader",
            "type": "function",
            "handler": "summarize",
            "input_type": "list[RawItem]",
            "output_type": "list[AnalysisResult]",
            "parameters_schema": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "default": 0.2},
                },
            },
        }
    )
    assert node.parameters_schema["properties"]["temperature"]["type"] == "number"


def test_node_config_rejects_invalid_parameters_schema() -> None:
    with pytest.raises(ValueError):
        NodeConfig.model_validate(
            {
                "name": "reader",
                "type": "function",
                "handler": "summarize",
                "input_type": "list[RawItem]",
                "output_type": "list[AnalysisResult]",
                "parameters_schema": "not-a-dict",
            }
        )


def test_node_config_rejects_credentials_in_parameters() -> None:
    with pytest.raises(ValueError, match="credentials"):
        NodeConfig.model_validate(
            {
                "name": "reader",
                "type": "function",
                "handler": "summarize",
                "input_type": "list[RawItem]",
                "output_type": "list[AnalysisResult]",
                "parameters": {"api_token": "secret"},
            }
        )


def test_config_editor_rejects_unknown_node_parameter_without_writing(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    original = (root / "config" / "nodes" / "reader.yaml").read_text()
    with pytest.raises(ConfigEditError):
        editor.save("node", "reader", f"{original}\nunsupported_parameter: 1\n")
    assert (root / "config" / "nodes" / "reader.yaml").read_text() == original




def _copy_config_tree(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    source_root = Path.cwd()
    _copy_dir(source_root / "config", root / "config")
    _copy_dir(source_root / "schemas", root / "schemas")
    _copy_dir(source_root / "extensions", root / "extensions")
    _copy_dir(source_root / "prompts", root / "prompts")
    _copy_dir(source_root / "skills", root / "skills")
    return root


def _copy_dir(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for path in source.rglob("*"):
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(source)
        dest = target / relative
        if path.is_dir():
            dest.mkdir()
        else:
            dest.write_text(path.read_text())


def test_graph_dag_payload_round_trip_preserves_ui_metadata() -> None:
    payload = graph_dag_payload(
        "test-dag",
        {
            "nodes": [
                {"id": "instance-a", "type": "rss-fetcher", "alias": "a", "config": {}},
                {"id": "instance-b", "type": "reader", "alias": "b", "config": {}},
            ],
            "edges": [{"from": "instance-a", "to": "instance-b", "fan_in": True}],
            "ui": {"nodes": {"instance-a": {"x": 100, "y": 200}, "instance-b": {"x": 300, "y": 400}}},
        },
    )
    assert payload["name"] == "test-dag"
    assert len(payload["nodes"]) == 2
    assert payload["nodes"][0]["id"] == "instance-a"
    assert payload["nodes"][0]["type"] == "rss-fetcher"
    assert payload["nodes"][0]["alias"] == "a"
    assert payload["nodes"][1]["id"] == "instance-b"
    assert payload["nodes"][1]["type"] == "reader"
    assert payload["nodes"][1]["alias"] == "b"
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["from"] == "instance-a"
    assert payload["edges"][0]["to"] == "instance-b"
    assert payload["edges"][0]["fan_in"] is True
    assert payload["ui"]["nodes"]["instance-a"]["x"] == 100
    assert payload["ui"]["nodes"]["instance-b"]["y"] == 400


def test_graph_dag_payload_validates_with_dag_config() -> None:
    payload = graph_dag_payload(
        "default",
        {
            "nodes": [
                {"id": "source-instance", "type": "rss-fetcher", "alias": "rss-fetcher", "config": {}},
                {"id": "reader-instance", "type": "reader", "alias": "reader", "config": {}},
            ],
            "edges": [{"from": "source-instance", "to": "reader-instance"}],
            "ui": {},
        },
    )
    DagConfig.model_validate(payload)


def test_graph_node_payload_round_trip() -> None:
    payload = graph_node_payload(
        "reader",
        {
            "skills": ["summarize"],
            "source_names": ["source-a", "source-b"],
            "timeout_seconds": 30.0,
            "parameters": {"confidence_threshold": 0.55},
        },
    )
    assert payload["name"] == "reader"
    assert payload["skills"] == ["summarize"]
    assert "model" not in payload
    assert payload["source_names"] == ["source-a", "source-b"]
    assert payload["timeout_seconds"] == 30.0
    assert payload["parameters"]["confidence_threshold"] == 0.55


def test_graph_dag_payload_splits_schema_fields() -> None:
    payload = graph_dag_payload(
        "default",
        {
            "nodes": [
                {
                    "id": "reader-instance",
                    "type": "reader",
                    "alias": "reader",
                    "config": {
                        "model": "gpt-4",
                        "param.temperature": 0.2,
                        "parameters": {"existing": True},
                    },
                }
            ],
            "edges": [],
            "ui": {},
        },
    )
    config = payload["nodes"][0]["config"]
    assert config["model"] == "gpt-4"
    assert config["parameters"] == {"existing": True, "temperature": 0.2}


def test_build_inspector_schema_merges_dynamic_and_parameter_fields() -> None:
    node = NodeConfig.model_validate(
        {
            "name": "reader",
            "type": "function",
            "role": "processor",
            "handler": "summarize",
            "input_type": "Any",
            "output_type": "Any",
            "parameters_schema": {
                "type": "object",
                "properties": {
                    "temperature": {"type": "number", "default": 0.2},
                },
            },
        }
    )
    schema = build_inspector_schema(
        node,
        {"summarize": SkillConfig(name="summarize", description="", handler="summarize")},
        {"stock": EntityTypeConfig.model_validate({"display_name": "Stock", "business_id_field": "code", "display_template": "{code}"})},
        EntitiesConfig.model_validate({"entities": []}),
        ["gpt-4", "gpt-5"],
    )
    assert schema["properties"]["param.temperature"]["default"] == 0.2


def test_graph_node_payload_rejects_credentials() -> None:
    with pytest.raises(ConfigEditError):
        graph_node_payload(
            "reader",
            {
                "skills": ["summarize"],
                "parameters": {"api_secret": "secret123"},
            },
        )
