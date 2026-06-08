from pathlib import Path

import pytest

from edera_core.bootstrap import discover_available_extensions, load_installed_extensions
from edera_core.storage import create_engine, init_db, session_factory, sqlite_url
from edera_core.storage.repository import save_installed_extension


@pytest.mark.asyncio
async def test_no_auto_scan(tmp_path: Path) -> None:
    extensions = tmp_path / "extensions"
    _write_extension(extensions / "demo", "demo", "0.1.0")

    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            bootstrap = await load_installed_extensions(session, tmp_path / "handlers")

        assert bootstrap.manifests == []
        assert [manifest.name for manifest in discover_available_extensions([extensions])] == ["demo"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_load_installed(tmp_path: Path) -> None:
    handlers = tmp_path / "handlers"
    (handlers / "demo.demo-handler").mkdir(parents=True)
    (handlers / "demo.demo-handler" / "handler.py").write_text("def run(payload):\n    return payload\n", encoding="utf-8")
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_installed_extension(
                session,
                name="demo",
                version="0.1.0",
                manifest_snapshot=_manifest("demo", "0.1.0"),
                import_records=[],
                installed_by="test",
            )
            await session.commit()

        async with factory() as session:
            bootstrap = await load_installed_extensions(session, handlers)

        assert bootstrap.extension_roots["demo"] == handlers / "demo"
        assert bootstrap.manifests[0].handlers[0].name == "demo.demo-handler"
        assert bootstrap.manifests[0].entity_types[0].name == "demo_entity"
        assert [manifest.name for manifest in bootstrap.manifests] == ["demo"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_skip_disabled(tmp_path: Path) -> None:
    engine = create_engine(sqlite_url(tmp_path / "edera.db"))
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            await save_installed_extension(
                session,
                name="demo",
                version="0.1.0",
                manifest_snapshot=_manifest("demo", "0.1.0"),
                import_records=[],
                enabled=False,
            )
            await session.commit()

        async with factory() as session:
            bootstrap = await load_installed_extensions(session, tmp_path / "handlers")

        assert bootstrap.manifests == []
        assert bootstrap.extension_roots == {}
    finally:
        await engine.dispose()


def _write_extension(root: Path, name: str, version: str) -> None:
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        f"name: {name}\nversion: {version}\ndescription: Demo\n",
        encoding="utf-8",
    )


def _manifest(name: str, version: str) -> dict[str, object]:
    return {
        "name": name,
        "version": version,
        "handlers": [
            {
                "name": "demo.demo-handler",
                "package": "demo.demo-handler",
                "role": "processor",
                "input_type": "Any",
                "output_type": "Any",
                "entry": "handler.py",
            }
        ],
        "entity_types": [
            {
                "name": "demo_entity",
                "display_name": "Demo Entity",
                "business_id_field": "name",
                "storage_tier": "database",
                "schema": {"required": ["name"], "properties": {"name": {"type": "string"}}},
            }
        ],
    }
