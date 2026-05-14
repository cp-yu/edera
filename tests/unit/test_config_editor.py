from pathlib import Path

import pytest

from stockimformation.config.editor import RuntimeConfigEditor
from stockimformation.errors import ConfigEditError


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
