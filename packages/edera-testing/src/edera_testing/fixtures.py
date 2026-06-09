from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from edera_testing.mocks import FakePIBinary
from edera_types import HandlerContext, NodeInput


def infer_extension_name(test_path: Path, override: str | None = None) -> str:
    if override:
        return override
    parts = test_path.parts
    for index, part in enumerate(parts):
        if part == "extensions" and index + 2 < len(parts) and parts[index + 2] == "tests":
            return parts[index + 1]
    raise ValueError(f"cannot infer extension name from {test_path}")


async def load_extension_runtime(
    *,
    extension_name: str,
    tmp_path: Path,
    config_dir: Path = Path("config"),
    extensions_dir: Path = Path("extensions"),
    handlers_dir: Path | None = None,
    create_engine_func: Callable[[str], Any] | None = None,
    init_db_func: Callable[[Any], Awaitable[None]] | None = None,
    extension_manager_cls: type | None = None,
    load_config_func: Callable[[Path, Any, list[Path]], Awaitable[Any]] | None = None,
    load_base_config_func: Callable[[Path], Any] | None = None,
) -> Any:
    if create_engine_func is None:
        from edera_core.storage import create_engine, sqlite_url

        def create_engine_func(database_url: str) -> Any:
            return create_engine(database_url)

        database_url = sqlite_url(tmp_path / "runtime.db")
    else:
        database_url = f"sqlite+aiosqlite:///{tmp_path / 'runtime.db'}"
    if init_db_func is None:
        from edera_core.storage import init_db as init_db_func
    if extension_manager_cls is None:
        from edera_core.extension_manager import ExtensionManager as extension_manager_cls
    if load_config_func is None:
        from edera_core.config.loader import load_runtime_app_config as load_config_func
    if load_base_config_func is None:
        from edera_core.config.loader import _load_runtime_base_config as load_base_config_func

    engine = create_engine_func(database_url)
    if hasattr(engine, "__await__"):
        engine = await engine
    try:
        await init_db_func(engine)
        base_config = load_base_config_func(config_dir)
        manager = extension_manager_cls(
            extensions_dir=extensions_dir,
            handlers_dir=handlers_dir or tmp_path / "handlers",
            engine=engine,
            config_entity_types=base_config.entity_types,
        )
        await manager.install(extension_name, installed_by="test")
        return await load_config_func(config_dir, engine, [extensions_dir])
    finally:
        await engine.dispose()


@pytest.fixture
def extension_name(request: pytest.FixtureRequest) -> str:
    return infer_extension_name(Path(str(request.node.fspath)))


@pytest.fixture
async def extension_runtime(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    extension_name: str,
) -> Any:
    return await load_extension_runtime(
        extension_name=extension_name,
        tmp_path=tmp_path,
        config_dir=Path("config"),
        extensions_dir=Path("extensions"),
    )


def create_mock_pi_binary(tmp_path: Path, content: str | None = None) -> Path:
    return FakePIBinary(script=content).write(tmp_path)


@pytest.fixture
def mock_pi_binary(tmp_path: Path) -> Callable[[str | None], Path]:
    return lambda content=None: create_mock_pi_binary(tmp_path, content)


def create_mock_handler_context(
    *,
    input_payload: Any = None,
    input_metadata: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    node_name: str = "test-node",
    node_type: str = "test",
    run_id: str = "test-run",
    entity_store: Any | None = None,
    storage: Any | None = None,
    runtime: Any | None = None,
) -> HandlerContext:
    return HandlerContext(
        input=NodeInput(run_id=run_id, payload=input_payload, metadata=input_metadata or {}),
        params=params or {},
        node_name=node_name,
        node_type=node_type,
        run_id=run_id,
        entity_store=entity_store or EmptyEntityStore(),
        storage=storage,
        runtime=runtime,
    )


@pytest.fixture
def mock_handler_context() -> Callable[..., HandlerContext]:
    return create_mock_handler_context


class EmptyEntityStore:
    def query(self, type: str | None = None) -> list[Any]:
        return []

    def resolve(self, ref: str) -> Any:
        raise KeyError(ref)

    def related_refs(self, ref: str) -> list[str]:
        return []
