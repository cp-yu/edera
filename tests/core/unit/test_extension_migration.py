from pathlib import Path

import pytest

from edera_core.dag_controller import DagController
from edera_core.storage.repository import list_installed_extensions


@pytest.mark.asyncio
async def test_startup_does_not_migrate_existing_extensions(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir)
    extensions = tmp_path / "extensions"
    _write_manifest(extensions / "demo", "demo")
    (extensions / "demo" / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    controller = DagController(config_dir, extensions_dirs=[extensions])
    await controller.start(run_startup=False)
    try:
        async with controller._factory()() as session:
            rows = await list_installed_extensions(session)
        assert rows == []
        assert not (tmp_path / "data" / "handlers" / "demo").exists()
    finally:
        await controller.shutdown()


def _write_manifest(root: Path, name: str) -> None:
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(f"name: {name}\nversion: 0.1.0\n", encoding="utf-8")


def _write_config(root: Path) -> None:
    (root / "dags").mkdir(parents=True)
    (root / "nodes").mkdir()
    (root / "skills").mkdir()
    (root.parent / "schemas" / "entity-types").mkdir(parents=True)
    (root.parent / "schemas" / "entity-types" / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema: {}\n",
        encoding="utf-8",
    )
    (root / "entities.yaml").write_text("entities: []\n", encoding="utf-8")
    (root / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (root / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{root / "test.db"}"\n'
        f'handlers_dir = "{root.parent / "data" / "handlers"}"\n',
        encoding="utf-8",
    )
    (root / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
