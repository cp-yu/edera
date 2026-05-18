from __future__ import annotations

import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from yaml import YAMLError
from pydantic import ValidationError

from stockimformation.config.loader import load_dag_configs, load_node_configs
from stockimformation.config.schema import DagConfig, NodeConfig, PortfolioConfig, SystemConfig
from stockimformation.dag.loader import load_graph
from stockimformation.errors import ConfigEditError, DagError

ConfigKind = Literal["system", "portfolio", "node", "dag", "skill"]


@dataclass(frozen=True)
class EditableFile:
    kind: ConfigKind
    name: str
    path: str
    content: str


class RuntimeConfigEditor:
    def __init__(self, config_dir: Path = Path("config"), skills_dir: Path = Path("skills")) -> None:
        self.config_dir = config_dir
        self.skills_dir = skills_dir

    def list_files(self) -> list[EditableFile]:
        files = [
            self._file("system", "system", self.config_dir / "system.toml"),
            self._file("portfolio", "portfolio", self.config_dir / "portfolio.yaml"),
        ]
        files.extend(
            self._file("node", path.stem, path)
            for path in sorted((self.config_dir / "nodes").glob("*.yaml"))
        )
        files.extend(
            self._file("dag", path.stem, path)
            for path in sorted((self.config_dir / "dags").glob("*.yaml"))
        )
        files.extend(
            self._file("skill", str(path.relative_to(self.skills_dir)), path)
            for path in sorted(self.skills_dir.glob("*/*.md"))
        )
        return files

    def read(self, kind: ConfigKind, name: str) -> EditableFile:
        return self._file(kind, name, self._path(kind, name))

    def save(self, kind: ConfigKind, name: str, content: str) -> EditableFile:
        path = self._path(kind, name)
        self._validate(kind, name, content)
        self._atomic_write(path, content)
        return self._file(kind, name, path)

    def _path(self, kind: ConfigKind, name: str) -> Path:
        if kind == "system":
            return self.config_dir / "system.toml"
        if kind == "portfolio":
            return self.config_dir / "portfolio.yaml"
        if kind == "node":
            return self.config_dir / "nodes" / f"{name}.yaml"
        if kind == "dag":
            return self.config_dir / "dags" / f"{name}.yaml"
        if kind == "skill":
            return self._skill_path(name)
        raise ConfigEditError(f"unsupported config kind: {kind}")

    def _skill_path(self, name: str) -> Path:
        root = self.skills_dir.resolve()
        path = (self.skills_dir / name).resolve()
        if root != path and root not in path.parents:
            raise ConfigEditError("skill path must stay under skills/")
        if path.suffix != ".md":
            raise ConfigEditError("skill file must be markdown")
        return path

    def _validate(self, kind: ConfigKind, name: str, content: str) -> None:
        try:
            if kind == "system":
                SystemConfig.model_validate(tomllib.loads(content))
            elif kind == "portfolio":
                PortfolioConfig.model_validate(_yaml_mapping(content))
            elif kind == "node":
                node = NodeConfig.model_validate(_yaml_mapping(content))
                self._validate_existing_dags(nodes={**load_node_configs(self.config_dir / "nodes"), node.name: node})
            elif kind == "dag":
                dag = DagConfig.model_validate(_yaml_mapping(content))
                nodes = load_node_configs(self.config_dir / "nodes")
                load_graph(dag, nodes)
            elif kind == "skill":
                if not content.strip():
                    raise ConfigEditError("skill document must not be empty")
            else:
                raise ConfigEditError(f"unsupported config kind: {kind}")
        except (tomllib.TOMLDecodeError, ValidationError, DagError, ValueError, YAMLError) as exc:
            raise ConfigEditError(str(exc)) from exc
    def _validate_existing_dags(self, nodes: dict[str, NodeConfig]) -> None:
        for dag in load_dag_configs(self.config_dir / "dags").values():
            load_graph(dag, nodes)

    def _file(self, kind: ConfigKind, name: str, path: Path) -> EditableFile:
        return EditableFile(kind, name, str(path), path.read_text())

    def _atomic_write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as tmp:
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
            os.replace(tmp_name, path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)


def _yaml_mapping(content: str) -> dict[str, Any]:
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise ConfigEditError("YAML content must be a mapping")
    return data
