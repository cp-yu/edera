from __future__ import annotations

import asyncio
from pathlib import Path
from threading import Thread

import pytest

from edera_core.grpc_client import GrpcClient
from edera_core.server import Server


@pytest.fixture(scope="module")
def running_server(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("edera-server")
    config_dir = _minimal_config(root)
    loop = asyncio.new_event_loop()
    thread = Thread(target=loop.run_forever, daemon=True)
    thread.start()

    async def start() -> dict[str, object]:
        server = Server(root / "data", "127.0.0.1:0", config_dir)
        await server.start()
        bootstrap = GrpcClient(f"127.0.0.1:{server.bootstrap_bound_port}", force_insecure=True)
        try:
            certs = await bootstrap.init_client("human:test")
        finally:
            await bootstrap.close()
        return {"server": server, "certs": certs}

    state = asyncio.run_coroutine_threadsafe(start(), loop).result()
    server = state["server"]
    try:
        yield {
            "server": server,
            "addr": f"127.0.0.1:{server.bound_port}",
            "config_dir": config_dir,
            "certs": state["certs"],
        }
    finally:
        asyncio.run_coroutine_threadsafe(server.stop(), loop).result()
        loop.call_soon_threadsafe(loop.stop)
        thread.join()


def _minimal_config(root: Path) -> Path:
    config_dir = root / "config"
    config_dir.mkdir()
    schema_dir = root / "schemas" / "entity-types"
    schema_dir.mkdir(parents=True)
    (schema_dir / "stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "storage_tier: database\n"
        "schema:\n"
        "  type: object\n"
        "  required: [code, name]\n"
        "  properties:\n"
        "    code:\n"
        "      type: string\n"
        "    name:\n"
        "      type: string\n"
        "    secret:\n"
        "      type: string\n"
        "field_permissions:\n"
        "  code: read-only\n"
        "  secret: none\n",
        encoding="utf-8",
    )
    (schema_dir / "relation.yaml").write_text(
        "display_name: Relation\n"
        "business_id_field: relation_type\n"
        "display_template: '{from} -> {to}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [from, to, relation_type]\n"
        "  properties:\n"
        "    from:\n"
        "      type: string\n"
        "    to:\n"
        "      type: string\n"
        "    relation_type:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "node.yaml").write_text(
        "display_name: Node\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name]\n"
        "  properties:\n"
        "    name:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "dag.yaml").write_text(
        "display_name: DAG\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name]\n"
        "  properties:\n"
        "    name:\n"
        "      type: string\n",
        encoding="utf-8",
    )
    (config_dir / "entities.yaml").write_text(
        "entities:\n"
        "- id: stock-test\n"
        "  type: stock\n"
        "  attributes:\n"
        "    code: TEST\n"
        "    name: Test\n"
        "    secret: hidden\n",
        encoding="utf-8",
    )
    (config_dir / "entity-relations.yaml").write_text(
        "relations:\n"
        "- id: rel-1\n"
        "  entities: [stock:TEST, stock:TEST]\n"
        "  type: reflects\n",
        encoding="utf-8",
    )
    (config_dir / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{root / "test.db"}"\n',
        encoding="utf-8",
    )
    (config_dir / "dags").mkdir()
    (config_dir / "dags" / "default.yaml").write_text(
        "name: default\n"
        "nodes:\n"
        "- id: reader\n"
        "  type: reader\n"
        "  config:\n"
        "    entity_permissions:\n"
        "      stock:\n"
        "        code: read-only\n"
        "edges: []\n",
        encoding="utf-8",
    )
    (config_dir / "nodes").mkdir()
    (config_dir / "nodes" / "reader.yaml").write_text(
        "name: reader\n"
        "type: function\n"
        "handler: reader\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (config_dir / "skills").mkdir()
    return config_dir
