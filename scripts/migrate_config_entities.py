from __future__ import annotations

from pathlib import Path

import yaml


def migrate(config_dir: Path) -> None:
    _wrap_dir(config_dir / "nodes", "node")
    _wrap_dir(config_dir / "dags", "dag")


def _wrap_dir(path: Path, entity_type: str) -> None:
    if not path.exists():
        return
    for file in path.glob("*.yaml"):
        data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or data.get("type") == entity_type:
            continue
        name = str(data.get("name") or file.stem)
        file.write_text(
            yaml.safe_dump(
                {"id": name, "type": entity_type, "attributes": data},
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
