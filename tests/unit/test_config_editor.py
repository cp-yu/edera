from pathlib import Path

import pytest

from stockimformation.config.schema import NodeConfig
from stockimformation.config.editor import RuntimeConfigEditor
from stockimformation.errors import ConfigEditError
from stockimformation.web.routes import _dag_payload, _save_dag


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


def test_structured_dag_payload_saves_yaml(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    payload = _dag_payload(
        "default",
        ["rss-fetcher", "reader", "advisor"],
        [
            {"from": "rss-fetcher", "to": "reader", "fan_in": True},
            {"from": "reader", "to": "advisor"},
        ],
    )
    saved = _save_dag(editor, "default", payload)
    content = Path(saved.path).read_text()
    assert "fan_in: true" in content
    assert "to: advisor" in content


def test_structured_dag_save_rejects_invalid_without_writing(tmp_path: Path) -> None:
    root = _copy_config_tree(tmp_path)
    editor = RuntimeConfigEditor(root / "config", root / "skills")
    dag_path = root / "config" / "dags" / "default.yaml"
    original = dag_path.read_text()
    payload = _dag_payload(
        "default",
        ["rss-fetcher", "reader"],
        [
            {"from": "rss-fetcher", "to": "reader"},
            {"from": "reader", "to": "rss-fetcher"},
        ],
    )
    with pytest.raises(ConfigEditError):
        _save_dag(editor, "default", payload)
    assert dag_path.read_text() == original


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
