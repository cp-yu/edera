from __future__ import annotations

import pytest

from edera_core.bootstrap import load_installed_extensions
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import save_installed_extension


@pytest.mark.asyncio
async def test_load_installed_extensions_returns_bootstrap_metadata(tmp_path):
    async with await _session(tmp_path) as session:
        await _install(session)
        result = await load_installed_extensions(session, tmp_path / "handlers")

    assert [manifest.name for manifest in result.manifests] == ["demo-ext"]
    assert result.storage_tables == {"demo-ext": []}
    assert result.table_names == {"demo-ext": {}}
    assert result.extension_roots == {"demo-ext": tmp_path / "handlers" / "demo-ext"}


@pytest.mark.asyncio
async def test_manifest_in_database(tmp_path):
    async with await _session(tmp_path) as session:
        row = await _install(session)

    assert row.manifest_data["handlers"][0]["name"] == "reader"


async def _session(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'edera.db'}")
    await init_db(engine)
    return session_factory(engine)()


async def _install(session):
    row = await save_installed_extension(
        session,
        name="demo-ext",
        version="1.0.0",
        manifest_snapshot={
            "name": "demo-ext",
            "version": "1.0.0",
            "handlers": [{"name": "reader", "role": "processor", "input_type": "Any", "entry": "handler.py"}],
        },
    )
    await session.commit()
    return row
