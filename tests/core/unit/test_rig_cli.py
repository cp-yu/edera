import os
from pathlib import Path

import pytest

from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import store_node_output_entities, upsert_edge_input, upsert_source_recovery
from edera_core.rig_cli import _grpc_client_init, _inject_human_cert_env, main


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("RIG_DAEMON_ADDR", raising=False)
    monkeypatch.delenv("RIG_DAEMON_BOOTSTRAP_ADDR", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "home")


def test_rig_entity_update_denies_node_without_permission(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--identity",
            "node:reader",
            "entity",
            "update",
            "stock:00700.HK",
            "--field",
            "code",
            "--value",
            "001",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "Permission denied: node:reader cannot write stock.code" in capsys.readouterr().err


def test_rig_entity_query_lists_matching_entities(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["rig", "entity", "query", "type=stock"])

    main()

    assert "stock:00700.HK" in capsys.readouterr().out


def test_rig_entity_update_human_writes_field(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    schema_dir = tmp_path / "schemas" / "entity-types"
    schema_dir.mkdir(parents=True)
    (schema_dir / "stock.yaml").write_text(
        "display_name: Stock\n"
        "business_id_field: code\n"
        "display_template: '{code}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [code, name]\n"
        "  properties:\n"
        "    code:\n"
        "      type: string\n"
        "    name:\n"
        "      type: string\n"
        "field_permissions:\n"
        "  code: read-only\n",
        encoding="utf-8",
    )
    (schema_dir / "node.yaml").write_text(
        "display_name: Node\n"
        "business_id_field: name\n"
        "display_template: '{name}'\n"
        "schema:\n"
        "  type: object\n"
        "  required: [name, type, input_type, output_type]\n"
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
        "  required: [name, nodes, edges]\n"
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
        "    name: Test\n",
        encoding="utf-8",
    )
    (config_dir / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (config_dir / "system.toml").write_text(
        'database_url = "sqlite+aiosqlite:///data/test.db"\nweb_host = "127.0.0.1"\n',
        encoding="utf-8",
    )
    (config_dir / "dags").mkdir()
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    (config_dir / "nodes").mkdir()
    (config_dir / "nodes" / "node-a.yaml").write_text(
        "name: node-a\n"
        "type: function\n"
        "handler: node-a\n"
        "input_type: Any\n"
        "output_type: Any\n",
        encoding="utf-8",
    )
    (config_dir / "skills").mkdir()
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--config-dir",
            str(config_dir),
            "entity",
            "update",
            "stock:TEST",
            "--field",
            "sentiment",
            "--value",
            "bearish",
        ],
    )

    main()

    assert '"sentiment": "bearish"' in capsys.readouterr().out


def test_rig_entity_create_delete(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--config-dir",
            str(config_dir),
            "entity",
            "create",
            "--type",
            "stock",
            "--attributes",
            '{"code":"NEW","name":"New"}',
        ],
    )

    main()

    assert "stock:NEW" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["rig", "--config-dir", str(config_dir), "entity", "delete", "stock:NEW"])

    main()

    assert '"deleted": true' in capsys.readouterr().out


def test_rig_node_status_uses_http_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: Path("/tmp/no-rig-cli-config"))
    monkeypatch.setattr("sys.argv", ["rig", "node", "status", "reader"])
    monkeypatch.setattr("edera_core.rig_cli._post", lambda api_url, path, payload, method="POST": {"node_id": "reader", "status": "idle"})

    main()

    assert '"status": "idle"' in capsys.readouterr().out


def test_rig_dag_trigger_sends_payload(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, object, str]] = []

    def fake_post(api_url: str, path: str, payload: object, method: str = "POST") -> object:
        calls.append((path, payload, method))
        return {"cycle_id": "cycle-1"}

    monkeypatch.setattr("pathlib.Path.home", lambda: Path("/tmp/no-rig-cli-config"))
    monkeypatch.setattr("sys.argv", ["rig", "dag", "trigger", "default", "--payload", '{"x": 1}'])
    monkeypatch.setattr("edera_core.rig_cli._post", fake_post)

    main()

    assert calls == [("/api/pipeline/dag/default/run", {"payload": {"x": 1}}, "POST")]
    assert '"cycle_id": "cycle-1"' in capsys.readouterr().out


def test_rig_dag_status_uses_http_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("pathlib.Path.home", lambda: Path("/tmp/no-rig-cli-config"))
    monkeypatch.setattr("sys.argv", ["rig", "dag", "status", "default"])
    monkeypatch.setattr("edera_core.rig_cli._post", lambda api_url, path, payload, method="POST": {"dag_name": "default"})

    main()

    assert '"dag_name": "default"' in capsys.readouterr().out


def test_rig_dag_edit_add_node(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--config-dir",
            str(config_dir),
            "dag",
            "edit",
            "default",
            "add-node",
            "--id",
            "reader-1",
            "--type",
            "reader",
        ],
    )

    main()

    assert '"updated": true' in capsys.readouterr().out
    assert "reader-1" in (config_dir / "dags" / "default.yaml").read_text(encoding="utf-8")


def test_rig_node_resume_sends_prompt(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, object, str]] = []

    def fake_post(api_url: str, path: str, payload: object, method: str = "POST") -> object:
        calls.append((path, payload, method))
        return {"cycle_id": "cycle-2"}

    monkeypatch.setattr("pathlib.Path.home", lambda: Path("/tmp/no-rig-cli-config"))
    monkeypatch.setattr("sys.argv", ["rig", "node", "resume", "reader", "--prompt", "adjust"])
    monkeypatch.setattr("edera_core.rig_cli._post", fake_post)

    main()

    assert calls == [("/api/node/reader/resume", {"prompt": "adjust"}, "POST")]
    assert '"cycle_id": "cycle-2"' in capsys.readouterr().out


def test_rig_get_filters_unreadable_fields(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    monkeypatch.setattr("sys.argv", ["rig", "--config-dir", str(config_dir), "--identity", "node:reader", "entity", "get", "stock:TEST"])

    main()

    output = capsys.readouterr().out
    assert '"name": "Test"' in output
    assert '"secret":' not in output


def test_rig_query_supports_relations(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "entity-relations.yaml").write_text(
        "relations:\n"
        "- id: rel-1\n"
        "  entities: [stock:TEST, stock:TEST]\n"
        "  type: reflects\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["rig", "--config-dir", str(config_dir), "entity", "query", "relation_type=reflects AND to=stock:TEST"],
    )

    main()

    assert '"relation_type": "reflects"' in capsys.readouterr().out


def test_rig_query_supports_node_output_history(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    import asyncio

    async def seed() -> None:
        await init_db(engine)
        try:
            factory = session_factory(engine)
            async with factory() as session:
                await store_node_output_entities(session, "cycle-1", "reader", "analysis", {"summary": "done"}, "session-1")
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    monkeypatch.setattr("sys.argv", ["rig", "--config-dir", str(config_dir), "entity", "query", "node_id=reader"])

    main()

    assert '"summary": "done"' in capsys.readouterr().out


def test_rig_node_output_queries_history(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    import asyncio

    async def seed() -> None:
        await init_db(engine)
        try:
            factory = session_factory(engine)
            async with factory() as session:
                await store_node_output_entities(session, "cycle-1", "reader", "analysis", {"summary": "done"}, "session-1")
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    monkeypatch.setattr("sys.argv", ["rig", "--config-dir", str(config_dir), "node", "output", "reader", "--cycle-id", "cycle-1"])

    main()

    assert '"summary": "done"' in capsys.readouterr().out


def test_rig_node_output_export_writes_payload(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config_dir = _minimal_config(tmp_path)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    import asyncio

    async def seed() -> None:
        await init_db(engine)
        try:
            factory = session_factory(engine)
            async with factory() as session:
                await store_node_output_entities(session, "cycle-1", "reader", "analysis", {"summary": "done"}, None)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    out = tmp_path / "payload.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--config-dir",
            str(config_dir),
            "node",
            "output",
            "export",
            "--cycle",
            "cycle-1",
            "--node",
            "reader",
            "--out",
            str(out),
        ],
    )

    main()

    assert out.read_text(encoding="utf-8") == '{"summary": "done"}'


def test_rig_query_projects_runtime_facts(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    config_dir = _minimal_config(tmp_path)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    import asyncio

    async def seed() -> None:
        await init_db(engine)
        try:
            factory = session_factory(engine)
            async with factory() as session:
                await upsert_edge_input(session, "cycle-1", "source", "sink", True, "failed", False, "node failed")
                await upsert_source_recovery(
                    session,
                    "cycle-1",
                    "fetcher",
                    "hn-rss",
                    {"recovery_status": "escalated", "latest_failure_reason": "timeout"},
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    monkeypatch.setattr(
        "sys.argv",
        ["rig", "--config-dir", str(config_dir), "entity", "query", "type=runtime.edge-input AND cycle_id=cycle-1"],
    )
    main()
    edge_output = capsys.readouterr().out
    monkeypatch.setattr(
        "sys.argv",
        ["rig", "--config-dir", str(config_dir), "entity", "query", "type=runtime.source-recovery AND source_name=hn-rss"],
    )
    main()
    recovery_output = capsys.readouterr().out

    assert '"type": "runtime.edge-input"' in edge_output
    assert '"from_node_id": "source"' in edge_output
    assert '"type": "runtime.source-recovery"' in recovery_output
    assert '"latest_failure_reason": "timeout"' in recovery_output


def test_rig_client_init_writes_config(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    async def fake_init(server: str, common_name: str) -> dict[str, str]:
        assert server == "localhost:9090"
        assert common_name == "human:default"
        return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr("edera_core.rig_cli._grpc_client_init", fake_init)
    monkeypatch.setattr("sys.argv", ["rig", "client", "init", "--server", "localhost:9090"])

    main()

    assert '"configured": true' in capsys.readouterr().out
    assert "localhost:9090" in (tmp_path / ".rig" / "config.json").read_text(encoding="utf-8")
    assert (tmp_path / ".rig" / "client.crt").read_text(encoding="utf-8") == "cert"
    assert (tmp_path / ".rig" / "client.key").read_text(encoding="utf-8") == "key"
    assert (tmp_path / ".rig" / "ca.crt").read_text(encoding="utf-8") == "ca"


def test_inject_human_cert_env_reads_missing_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig_dir = tmp_path / ".rig"
    rig_dir.mkdir()
    (rig_dir / "client.crt").write_text("CERT", encoding="utf-8")
    (rig_dir / "client.key").write_text("KEY", encoding="utf-8")
    (rig_dir / "ca.crt").write_text("CA", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("RIG_CLIENT_CERT", raising=False)
    monkeypatch.delenv("RIG_CLIENT_KEY", raising=False)
    monkeypatch.delenv("RIG_CA_CERT", raising=False)

    _inject_human_cert_env()

    assert os.environ["RIG_CLIENT_CERT"] == "CERT"
    assert os.environ["RIG_CLIENT_KEY"] == "KEY"
    assert os.environ["RIG_CA_CERT"] == "CA"


def test_inject_human_cert_env_preserves_existing_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rig_dir = tmp_path / ".rig"
    rig_dir.mkdir()
    (rig_dir / "client.crt").write_text("CERT", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("RIG_CLIENT_CERT", "ORIGINAL")

    _inject_human_cert_env()

    assert os.environ["RIG_CLIENT_CERT"] == "ORIGINAL"


def test_client_init_skips_human_cert_injection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_init(server: str, common_name: str) -> dict[str, str]:
        return {"client_cert_pem": "new-cert", "client_key_pem": "new-key", "ca_cert_pem": "new-ca"}

    rig_dir = tmp_path / ".rig"
    rig_dir.mkdir()
    (rig_dir / "client.crt").write_text("OLD", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("RIG_CLIENT_CERT", raising=False)
    monkeypatch.delenv("RIG_CLIENT_KEY", raising=False)
    monkeypatch.delenv("RIG_CA_CERT", raising=False)
    monkeypatch.setattr("edera_core.rig_cli._grpc_client_init", fake_init)
    monkeypatch.setattr("sys.argv", ["rig", "client", "init", "--server", "localhost:9090"])

    main()

    assert "RIG_CLIENT_CERT" not in os.environ


def test_daemon_skips_human_cert_injection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def fake_serve(address: str, data_dir: Path | None, config_dir: Path, bootstrap_address: str | None) -> None:
        return None

    import edera_core.daemon as daemon_module

    rig_dir = tmp_path / ".rig"
    rig_dir.mkdir()
    (rig_dir / "client.crt").write_text("OLD", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.delenv("RIG_CLIENT_CERT", raising=False)
    monkeypatch.setattr(daemon_module, "serve", fake_serve)
    monkeypatch.setattr("sys.argv", ["rig", "daemon"])

    main()

    assert "RIG_CLIENT_CERT" not in os.environ


def test_rig_client_init_uses_force_insecure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str | None, bool, bool]] = []

    class FakeClient:
        def __init__(
            self,
            address: str | None = None,
            data_dir: Path | None = None,
            allow_insecure: bool = False,
            force_insecure: bool = False,
        ) -> None:
            calls.append((address, allow_insecure, force_insecure))

        async def init_client(self, common_name: str) -> dict[str, str]:
            assert common_name == "human:test"
            return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

        async def close(self) -> None:
            return None

    monkeypatch.setattr("edera_core.rig_cli.RigGrpcClient", FakeClient)

    import asyncio

    assert asyncio.run(_grpc_client_init("localhost:9090", "human:test")) == {
        "client_cert_pem": "cert",
        "client_key_pem": "key",
        "ca_cert_pem": "ca",
    }
    assert calls == [("localhost:9091", False, True)]


def test_rig_cli_uses_grpc_when_daemon_addr_is_set(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None, data_dir=None, allow_insecure: bool = False) -> None:
            assert address == "127.0.0.1:19090"

        async def dag_trigger(self, name: str, payload: object | None = None) -> dict[str, object]:
            assert name == "default"
            assert payload == {"x": 1}
            return {"cycle_id": "grpc-cycle"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("RIG_DAEMON_ADDR", "127.0.0.1:19090")
    monkeypatch.setattr("edera_core.rig_cli.RigGrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["rig", "dag", "trigger", "default", "--payload", '{"x": 1}'])

    main()

    assert '"cycle_id": "grpc-cycle"' in capsys.readouterr().out


def test_rig_dag_edit_uses_grpc_when_daemon_addr_is_set(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None, data_dir=None, allow_insecure: bool = False) -> None:
            assert address == "127.0.0.1:19090"

        async def dag_edit(self, name: str, operation: str, payload: dict[str, object]) -> dict[str, object]:
            assert name == "default"
            assert operation == "add-edge"
            assert payload == {"from": "a", "to": "b", "optional": True}
            return {"updated": True}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("RIG_DAEMON_ADDR", "127.0.0.1:19090")
    monkeypatch.setattr("edera_core.rig_cli.RigGrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["rig", "dag", "edit", "default", "add-edge", "--from", "a", "--to", "b", "--optional"],
    )

    main()

    assert '"updated": true' in capsys.readouterr().out


def test_rig_daemon_passes_data_dir_to_daemon_serve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, Path | None, Path, str | None]] = []

    async def fake_serve(address: str, data_dir: Path | None, config_dir: Path, bootstrap_address: str | None) -> None:
        calls.append((address, data_dir, config_dir, bootstrap_address))

    import edera_core.daemon as daemon_module

    monkeypatch.setattr(daemon_module, "serve", fake_serve)
    monkeypatch.setattr(
        "sys.argv",
        [
            "rig",
            "--config-dir",
            str(tmp_path / "config"),
            "daemon",
            "--address",
            "127.0.0.1:19090",
            "--bootstrap-address",
            "127.0.0.1:19091",
            "--data-dir",
            str(tmp_path / "rig-data"),
        ],
    )

    main()

    assert calls == [("127.0.0.1:19090", tmp_path / "rig-data", tmp_path / "config", "127.0.0.1:19091")]


def _minimal_config(tmp_path) -> object:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    schema_dir = tmp_path / "schemas" / "entity-types"
    schema_dir.mkdir(parents=True)
    (schema_dir / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema:\n  type: object\n  required: [code, name]\n  properties:\n    code:\n      type: string\n    name:\n      type: string\n    secret:\n      type: string\nfield_permissions:\n  code: read-only\n  secret: none\n",
        encoding="utf-8",
    )
    (schema_dir / "relation.yaml").write_text(
        "display_name: Relation\nbusiness_id_field: relation_type\ndisplay_template: '{from} -> {to}'\nschema:\n  type: object\n  required: [from, to, relation_type]\n  properties:\n    from:\n      type: string\n    to:\n      type: string\n    relation_type:\n      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "node.yaml").write_text(
        "display_name: Node\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema:\n  type: object\n  required: [name, type, input_type, output_type]\n  properties:\n    name:\n      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "dag.yaml").write_text(
        "display_name: DAG\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema:\n  type: object\n  required: [name, nodes, edges]\n  properties:\n    name:\n      type: string\n",
        encoding="utf-8",
    )
    (config_dir / "entities.yaml").write_text(
        "entities:\n- id: stock-test\n  type: stock\n  attributes:\n    code: TEST\n    name: Test\n    secret: hidden\n",
        encoding="utf-8",
    )
    (config_dir / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (config_dir / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{tmp_path / "test.db"}"\nweb_host = "127.0.0.1"\n',
        encoding="utf-8",
    )
    (config_dir / "dags").mkdir()
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    (config_dir / "nodes").mkdir()
    (config_dir / "skills").mkdir()
    return config_dir
