from __future__ import annotations

from pathlib import Path

import pytest

from edera_core.resolver import DatabaseHandlerResolver, HandlerNotFoundError
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import save_installed_extension


@pytest.mark.asyncio
async def test_get_handler_from_installed_extension(tmp_path):
    async with await _session(tmp_path) as session:
        await _install(session)
        meta = await DatabaseHandlerResolver(session, tmp_path / "handlers").get("reader")

    assert meta.path == tmp_path / "handlers" / "demo-ext" / "handler.py"
    assert meta.function == "execute"


@pytest.mark.asyncio
async def test_handler_not_found(tmp_path):
    async with await _session(tmp_path) as session:
        await _install(session)
        with pytest.raises(HandlerNotFoundError):
            await DatabaseHandlerResolver(session, tmp_path / "handlers").get("missing")


@pytest.mark.asyncio
async def test_compute_handler_path(tmp_path):
    async with await _session(tmp_path) as session:
        await _install(session, entry="src/main.py")
        meta = await DatabaseHandlerResolver(session, tmp_path / "handlers").get("reader")

    assert meta.path == tmp_path / "handlers" / "demo-ext" / "src" / "main.py"


@pytest.mark.asyncio
async def test_default_function_name(tmp_path):
    async with await _session(tmp_path) as session:
        await _install(session, function=None)
        meta = await DatabaseHandlerResolver(session, tmp_path / "handlers").get("reader")

    assert meta.function == "run"


async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    return session_factory(engine)()


async def _install(session, entry: str = "handler.py", function: str | None = "execute") -> None:
    handler = {"name": "reader", "entry": entry}
    if function is not None:
        handler["function"] = function
    await save_installed_extension(
        session,
        name="demo-ext",
        version="1.0.0",
        manifest_snapshot={"name": "demo-ext", "version": "1.0.0", "handlers": [handler]},
    )
    await session.commit()
