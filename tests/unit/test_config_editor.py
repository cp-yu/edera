from pathlib import Path

import pytest

from stockimformation.config.schema import DagConfig, NodeConfig
from stockimformation.config.editor import RuntimeConfigEditor
from stockimformation.errors import ConfigEditError
from stockimformation.web.routes import _graph_dag_payload, _graph_node_payload


def test_config_editor_rejects_invalid_system_without_writing(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    original = (root / "config" / "system.toml").read_text()
    with pytest.raises(ConfigEditError):
        editor.save("system", "system", original.replace('web_host = "127.0.0.1"', 'web_host = "0.0.0.0"'))
    assert (root / "config" / "system.toml").read_text() == original


def test_config_editor_rejects_invalid_dag(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    original = (root / "config" / "dags" / "default.yaml").read_text()
    invalid = original + "\n  - from: notifier\n    to: rss-fetcher\n"
    with pytest.raises(ConfigEditError):
        editor.save("dag", "default", invalid)
    assert (root / "config" / "dags" / "default.yaml").read_text() == original


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
            "type": "llm",
            "skills": [{"name": "summarize"}],
            "input_type": "list[RawItem]",
            "output_type": "list[AnalysisResult]",
            "parameters": {"confidence_threshold": 0.55, "signals": ["earnings", "guidance"]},
        }
    )
    assert node.parameters["confidence_threshold"] == 0.55


def test_node_config_rejects_credentials_in_parameters() -> None:
    with pytest.raises(ValueError, match="credentials"):
        NodeConfig.model_validate(
            {
                "name": "reader",
                "type": "llm",
                "skills": [{"name": "summarize"}],
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
    _copy_dir(source_root / "skills", root / "skills")
    return root


def _copy_dir(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        dest = target / relative
        if path.is_dir():
            dest.mkdir()
        else:
            dest.write_text(path.read_text())


def test_graph_dag_payload_round_trip_preserves_ui_metadata() -> None:
    payload = _graph_dag_payload(
        "test-dag",
        {
            "nodes": [{"name": "a", "type": "function"}, {"name": "b", "type": "llm"}],
            "edges": [{"from": "a", "to": "b", "fan_in": True}],
            "ui": {"nodes": {"a": {"x": 100, "y": 200}, "b": {"x": 300, "y": 400}}},
        },
    )
    assert payload["name"] == "test-dag"
    assert len(payload["nodes"]) == 2
    assert payload["nodes"] == ["a", "b"]
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["from"] == "a"
    assert payload["edges"][0]["to"] == "b"
    assert payload["edges"][0]["fan_in"] is True
    assert payload["ui"]["nodes"]["a"]["x"] == 100
    assert payload["ui"]["nodes"]["b"]["y"] == 400


def test_graph_dag_payload_validates_with_dag_config() -> None:
    payload = _graph_dag_payload(
        "default",
        {
            "nodes": ["rss-fetcher", "reader"],
            "edges": [{"from": "rss-fetcher", "to": "reader"}],
            "ui": {},
        },
    )
    DagConfig.model_validate(payload)


def test_graph_node_payload_round_trip() -> None:
    payload = _graph_node_payload(
        "reader",
        {
            "skills": ["summarize"],
            "model": "gpt-4",
            "source_names": ["source-a", "source-b"],
            "timeout_seconds": 30.0,
            "parameters": {"confidence_threshold": 0.55},
        },
    )
    assert payload["name"] == "reader"
    assert payload["skills"] == [{"name": "summarize"}]
    assert payload["model"] == "gpt-4"
    assert payload["source_names"] == ["source-a", "source-b"]
    assert payload["timeout_seconds"] == 30.0
    assert payload["parameters"]["confidence_threshold"] == 0.55


def test_graph_node_payload_rejects_credentials() -> None:
    with pytest.raises(ConfigEditError):
        _graph_node_payload(
            "reader",
            {
                "skills": ["summarize"],
                "parameters": {"api_secret": "secret123"},
            },
        )
