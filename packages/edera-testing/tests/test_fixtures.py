from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from edera_testing.fixtures import (
    create_mock_handler_context,
    create_mock_pi_binary,
    infer_extension_name,
    load_extension_runtime,
)


def test_auto_infer_extension_name() -> None:
    path = Path("extensions/test-ext/tests/test_foo.py")

    assert infer_extension_name(path) == "test-ext"


def test_override_extension_name() -> None:
    path = Path("extensions/test-ext/tests/test_foo.py")

    assert infer_extension_name(path, override="custom-name") == "custom-name"


@pytest.mark.asyncio
async def test_extension_runtime_initialization(tmp_path: Path) -> None:
    calls: list[str] = []

    class Engine:
        async def dispose(self) -> None:
            calls.append("dispose")

    class Manager:
        def __init__(self, **kwargs):
            calls.append(f"manager:{kwargs['extensions_dir']}")

        async def install(self, name: str, *, installed_by: str | None = None) -> None:
            calls.append(f"install:{name}:{installed_by}")

    async def create_engine(database_url: str):
        calls.append(f"engine:{database_url.endswith('/runtime.db')}")
        return Engine()

    async def init_db(engine: object) -> None:
        calls.append("init_db")

    async def load_config(config_dir: Path, engine: object, extensions_dirs: list[Path]):
        calls.append(f"load:{config_dir}:{extensions_dirs[0]}")
        return {"dags": {}, "nodes": {}, "entity_types": {}}

    class BaseConfig:
        entity_types = {"dag": object()}

    def load_base_config(config_dir: Path):
        calls.append(f"base:{config_dir}")
        return BaseConfig()

    config = await load_extension_runtime(
        extension_name="test-ext",
        tmp_path=tmp_path,
        config_dir=Path("config"),
        extensions_dir=Path("extensions"),
        create_engine_func=create_engine,
        init_db_func=init_db,
        extension_manager_cls=Manager,
        load_config_func=load_config,
        load_base_config_func=load_base_config,
    )

    assert config == {"dags": {}, "nodes": {}, "entity_types": {}}
    assert calls == [
        "engine:True",
        "init_db",
        "base:config",
        "manager:extensions",
        "install:test-ext:test",
        "load:config:extensions",
        "dispose",
    ]


@pytest.mark.asyncio
async def test_extension_runtime_returns_config(tmp_path: Path) -> None:
    class Engine:
        async def dispose(self) -> None:
            pass

    class Manager:
        def __init__(self, **kwargs):
            pass

        async def install(self, name: str, *, installed_by: str | None = None) -> None:
            pass

    class Config:
        dags = {}
        nodes = {}
        entity_types = {}
        system = object()
        runtime = object()

    async def create_engine(database_url: str):
        return Engine()

    async def init_db(engine: object) -> None:
        pass

    async def load_config(config_dir: Path, engine: object, extensions_dirs: list[Path]):
        return Config()

    class BaseConfig:
        entity_types = {}

    config = await load_extension_runtime(
        extension_name="test-ext",
        tmp_path=tmp_path,
        create_engine_func=create_engine,
        init_db_func=init_db,
        extension_manager_cls=Manager,
        load_config_func=load_config,
        load_base_config_func=lambda config_dir: BaseConfig(),
    )

    assert all(hasattr(config, name) for name in ("dags", "nodes", "entity_types", "system", "runtime"))


def test_mock_pi_binary_executable(tmp_path: Path) -> None:
    binary = create_mock_pi_binary(tmp_path)

    assert os.access(binary, os.X_OK)


def test_mock_pi_binary_captures_context(tmp_path: Path) -> None:
    binary = create_mock_pi_binary(tmp_path)

    subprocess.run([str(binary), "arg"], cwd=tmp_path, check=True)
    record = json.loads((tmp_path / "pi-calls.jsonl").read_text().splitlines()[0])

    assert record["argv"][1:] == ["arg"]
    assert record["cwd"] == str(tmp_path)
    assert "PATH" in record["environ"]


def test_mock_handler_context_default() -> None:
    ctx = create_mock_handler_context()

    assert ctx.input.run_id == "test-run"
    assert ctx.params == {}
    assert ctx.node_name == "test-node"
    assert ctx.node_type == "test"
    assert ctx.run_id == "test-run"


def test_mock_handler_context_custom() -> None:
    ctx = create_mock_handler_context(params={"key": "value"}, run_id="run-123")

    assert ctx.params == {"key": "value"}
    assert ctx.run_id == "run-123"
