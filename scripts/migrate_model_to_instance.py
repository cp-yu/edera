from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", default="config")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    changes = migrate(Path(args.config_dir), args.dry_run)
    for line in changes:
        print(line)


def migrate(config_dir: Path, dry_run: bool = False) -> list[str]:
    models = _node_models(config_dir / "nodes")
    changes: list[str] = []
    for path in sorted((config_dir / "dags").glob("*.yaml")):
        data = _read_yaml(path)
        touched = False
        for node in data.get("nodes", []):
            if not isinstance(node, dict):
                continue
            config = node.setdefault("config", {})
            if not isinstance(config, dict):
                continue
            node_type = node.get("type")
            if isinstance(node_type, str) and node_type in models and "model" not in config:
                config["model"] = models[node_type]
                touched = True
        if touched:
            changes.append(f"dag {path}")
            if not dry_run:
                _write_yaml(path, data)
    for path in sorted((config_dir / "nodes").glob("*.yaml")):
        data = _read_yaml(path)
        if "model" not in data:
            continue
        changes.append(f"node {path}")
        if not dry_run:
            data.pop("model", None)
            _write_yaml(path, data)
    return changes


def _node_models(path: Path) -> dict[str, str]:
    models: dict[str, str] = {}
    for file in sorted(path.glob("*.yaml")):
        data = _read_yaml(file)
        model = data.get("model")
        name = data.get("name", file.stem)
        if isinstance(model, str) and model:
            models[str(name)] = model
    return models


def _read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config file must contain a mapping: {path}")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
