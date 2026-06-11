from __future__ import annotations

import json
import os
from pathlib import Path

import asyncio
import grpc
import pytest
import yaml

from edera_core.cli import _grpc_client_init, _inject_human_cert_env, main
from edera_core.grpc_client import GrpcClient


@pytest.fixture(autouse=True)
def _isolated_cli_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in (
        "EDERA_SERVER_ADDR",
        "EDERA_CLIENT_CERT",
        "EDERA_CLIENT_KEY",
        "EDERA_CA_CERT",
        "EDERA_IDENTITY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "home")


def test_cli_requires_server_addr(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edera", "entity", "list"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    error = json.loads(capsys.readouterr().err)
    assert error["type"] == "ValueError"
    assert error["detail"] == "EDERA_SERVER_ADDR not set"


def test_cli_output_modes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def query_latest_briefing(self) -> dict[str, object]:
            return {"briefing": {"id": "briefing-1", "items": [1, 2]}}

        async def query_source_logs(self, source_name: str = "", limit: int = 50) -> dict[str, object]:
            assert source_name == ""
            assert limit == 2
            return {"logs": [{"source_name": "rss-main", "metadata": {"attempt": 1}}]}

        async def close(self) -> None:
            return None

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    monkeypatch.setattr("sys.argv", ["edera", "--server", "127.0.0.1:0", "query", "briefing", "latest"])
    main()
    assert json.loads(capsys.readouterr().out) == {"briefing": {"id": "briefing-1", "items": [1, 2]}}

    monkeypatch.setattr("sys.argv", ["edera", "--server", "127.0.0.1:0", "query", "briefing", "latest", "--output", "yaml"])
    main()
    assert "briefing:" in capsys.readouterr().out

    monkeypatch.setattr("sys.argv", ["edera", "--server", "127.0.0.1:0", "source", "logs", "--limit", "2", "--output", "table"])
    main()
    table = capsys.readouterr().out
    assert "source_name" in table
    assert '{"attempt": 1}' in table


def test_cli_invalid_output_mode(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edera", "entity", "list", "--output", "xml"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code != 0
    assert "--output" in capsys.readouterr().err


def test_inject_human_cert_env_reads_edera_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    edera_dir = tmp_path / ".edera"
    edera_dir.mkdir()
    (edera_dir / "client.crt").write_text("CERT", encoding="utf-8")
    (edera_dir / "client.key").write_text("KEY", encoding="utf-8")
    (edera_dir / "ca.crt").write_text("CA", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    _inject_human_cert_env()

    assert os.environ["EDERA_CLIENT_CERT"] == "CERT"
    assert os.environ["EDERA_CLIENT_KEY"] == "KEY"
    assert os.environ["EDERA_CA_CERT"] == "CA"


def test_inject_human_cert_env_preserves_existing_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    edera_dir = tmp_path / ".edera"
    edera_dir.mkdir()
    (edera_dir / "client.crt").write_text("CERT", encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("EDERA_CLIENT_CERT", "ORIGINAL")

    _inject_human_cert_env()

    assert os.environ["EDERA_CLIENT_CERT"] == "ORIGINAL"


def test_client_init_writes_edera_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    async def fake_init(server: str, common_name: str) -> dict[str, str]:
        assert server == "127.0.0.1:9091"
        assert common_name == "human:default"
        return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setattr("edera_core.cli._grpc_client_init", fake_init)
    monkeypatch.setattr("sys.argv", ["edera", "client", "init", "--server", "127.0.0.1:9091"])

    main()

    assert '"configured": true' in capsys.readouterr().out
    assert (tmp_path / ".edera" / "client.crt").read_text(encoding="utf-8") == "cert"
    assert (tmp_path / ".edera" / "client.key").read_text(encoding="utf-8") == "key"
    assert (tmp_path / ".edera" / "ca.crt").read_text(encoding="utf-8") == "ca"


def test_client_init_uses_force_insecure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str | None, bool]] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, force_insecure: bool = False, **_kwargs) -> None:
            calls.append((address, force_insecure))

        async def init_client(self, common_name: str) -> dict[str, str]:
            assert common_name == "human:test"
            return {"client_cert_pem": "cert", "client_key_pem": "key", "ca_cert_pem": "ca"}

        async def close(self) -> None:
            return None

    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    assert asyncio.run(_grpc_client_init("127.0.0.1:9091", "human:test")) == {
        "client_cert_pem": "cert",
        "client_key_pem": "key",
        "ca_cert_pem": "ca",
    }
    assert calls == [("127.0.0.1:9091", True)]


def test_cli_help_lists_control_plane_commands(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["edera", "--help"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 0
    output = capsys.readouterr().out
    for command in (
        "entity",
        "relation",
        "entity-type",
        "node",
        "node-type",
        "skill",
        "dag",
        "event",
        "system",
        "client",
        "config",
        "query",
        "source",
        "handler",
        "handler-validate",
        "extension",
    ):
        assert command in output


def test_cli_entity_query_uses_running_server(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    monkeypatch.setattr("sys.argv", ["edera", "entity", "query", "type=stock"])

    main()

    assert capsys.readouterr().out == "[]\n"


def test_cli_entity_list_returns_explicitly_imported_entity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    entity_file = tmp_path / "stock.yaml"
    entity_file.write_text(
        "type: stock\n"
        "id: stock-test\n"
        "attributes:\n"
        "  code: TEST\n"
        "  name: Test\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sys.argv", ["edera", "entity", "import", "--file", str(entity_file)])
    main()
    capsys.readouterr()

    monkeypatch.setattr("sys.argv", ["edera", "entity", "list", "--type", "stock"])
    main()

    assert "stock:TEST" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_grpc_entity_list_returns_entity_types(
    monkeypatch: pytest.MonkeyPatch,
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    client = GrpcClient(running_server["addr"])
    try:
        entity_types = await client.entity_list("entity_type")
    finally:
        await client.close()

    assert any(item["id"] == "stock" and item["attributes"]["display_name"] == "Stock" for item in entity_types)


def test_cli_entity_update_denies_node_without_permission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    _import_stock_test(running_server, tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "--identity",
            "node:reader",
            "entity",
            "update",
            "stock:TEST",
            "--field",
            "code",
            "--value",
            "001",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "cannot write stock.code" in capsys.readouterr().err


def test_cli_entity_update_human_writes_field(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    _import_stock_test(running_server, tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "entity", "update", "stock:TEST", "--field", "name", "--value", "Changed"],
    )

    main()

    assert '"name": "Changed"' in capsys.readouterr().out


def test_cli_entity_import_uses_full_yaml_document(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "node.yaml"
    path.write_text(
        "type: node\n"
        "id: node-1\n"
        "attributes:\n"
        "  name: reader\n"
        "  type: function\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, str | None]] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def entity_import(self, import_path: str, type_name: str | None = None) -> dict[str, object]:
            calls.append((import_path, type_name))
            return {"imported": 1, "file": import_path}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "entity", "import", "--file", str(path)])

    main()

    assert calls[0][1] is None
    assert yaml.safe_load(Path(calls[0][0]).read_text(encoding="utf-8")) == {
        "entities": [
            {
                "type": "node",
                "id": "node-1",
                "attributes": {"name": "reader", "type": "function"},
            }
        ]
    }
    assert '"imported": 1' in capsys.readouterr().out


def test_cli_entity_export_writes_full_yaml_document(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "exported.yaml"

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def entity_get(self, ref: str) -> dict[str, object]:
            assert ref == "node:reader"
            return {"id": "node-1", "type": "node", "attributes": {"name": "reader"}}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "entity", "export", "node:reader", "--file", str(path)])

    main()

    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {
        "type": "node",
        "id": "node-1",
        "attributes": {"name": "reader"},
    }
    assert '"exported": "node:reader"' in capsys.readouterr().out


def test_cli_entity_template_uses_entity_type_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "template.yaml"

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def entity_list(self, type_name: str | None = None) -> list[dict[str, object]]:
            assert type_name == "entity_type"
            return [
                {
                    "id": "node",
                    "type": "entity_type",
                    "attributes": {
                        "schema": {
                            "required": ["name", "enabled", "permits", "tags"],
                            "properties": {
                                "name": {"type": "string"},
                                "enabled": {"type": "boolean", "default": True},
                                "permits": {"type": "integer"},
                                "tags": {"type": "array"},
                            },
                        }
                    },
                }
            ]

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "entity", "template", "--type", "node", "--file", str(path)])

    main()

    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {
        "type": "node",
        "id": "",
        "attributes": {"name": "", "enabled": True, "permits": 0, "tags": []},
    }
    assert '"template": "node"' in capsys.readouterr().out


def test_cli_entity_type_materialize_plan_uses_grpc(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def entity_materialize(self, payload: dict[str, object]) -> dict[str, object]:
            assert payload == {
                "operation": "plan",
                "entity_type": "stock",
                "field": "code",
                "index": True,
            }
            return {"column": "code", "index_name": "idx_entity_stock_code", "backfill_count": 3}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "entity-type", "materialize", "plan", "stock", "--field", "code", "--index"])

    main()

    output = capsys.readouterr().out
    assert '"column": "code"' in output
    assert '"idx_entity_stock_code"' in output


def test_cli_entity_import_rejects_invalid_yaml_document(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("id: node-1\nattributes: []\n", encoding="utf-8")

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            raise AssertionError("invalid import must not open gRPC client")

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "entity", "import", "--file", str(path)])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "entity YAML requires non-empty type" in capsys.readouterr().err


def test_cli_relation_import_accepts_relation_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "relations.yaml"
    path.write_text(
        "relations:\n"
        "- entities: [stock:TEST, rss-source:demo]\n"
        "  type: watches\n",
        encoding="utf-8",
    )
    calls: list[tuple[str, str | None]] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def entity_import(self, import_path: str, type_name: str | None = None) -> dict[str, object]:
            calls.append((import_path, type_name))
            return {"imported": 1}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "relation", "import", "--file", str(path)])

    main()

    assert calls == [(str(path), "relation")]
    assert '"imported": 1' in capsys.readouterr().out


def test_cli_dag_status_uses_grpc(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    monkeypatch.setattr("sys.argv", ["edera", "dag", "status", "default"])

    main()

    assert '"dag_name": "default"' in capsys.readouterr().out


def test_cli_dag_definition_commands_use_graph_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dag_file = tmp_path / "dag.json"
    dag_file.write_text('{"nodes":[{"id":"reader"}]}', encoding="utf-8")
    exported = tmp_path / "exported.json"
    calls: list[object] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def graph_list_dags(self) -> dict[str, object]:
            calls.append("list")
            return {"dags": [{"name": "default"}]}

        async def graph_get_dag(self, name: str) -> dict[str, object]:
            calls.append(("show", name))
            return {"name": name, "nodes": []}

        async def graph_create_dag(self, name: str) -> dict[str, object]:
            calls.append(("create", name))
            return {"created": name}

        async def graph_save_dag(self, name: str, payload: dict[str, object]) -> dict[str, object]:
            calls.append(("save", name, payload))
            return {"saved": name}

        async def graph_runtime_status(self, run_id: str = "") -> dict[str, object]:
            calls.append(("runtime-status", run_id))
            return {"run_id": run_id, "nodes": []}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    for argv in (
        ["edera", "dag", "list"],
        ["edera", "dag", "show", "default"],
        ["edera", "dag", "create", "new-dag"],
        ["edera", "dag", "save", "default", "--file", str(dag_file)],
        ["edera", "dag", "export", "default", "--file", str(exported)],
        ["edera", "dag", "import", "default", "--file", str(dag_file)],
        ["edera", "dag", "runtime-status", "--run-id", "run-1"],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()
        capsys.readouterr()

    assert calls == [
        "list",
        ("show", "default"),
        ("create", "new-dag"),
        ("save", "default", {"nodes": [{"id": "reader"}]}),
        ("show", "default"),
        ("save", "default", {"nodes": [{"id": "reader"}]}),
        ("runtime-status", "run-1"),
    ]
    assert json.loads(exported.read_text(encoding="utf-8")) == {"name": "default", "nodes": []}


def test_cli_node_type_commands_use_graph_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    node_type_file = tmp_path / "node-type.json"
    node_type_file.write_text('{"name":"fetch-rss","handler":"rss.fetch"}', encoding="utf-8")
    calls: list[object] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def graph_list_node_types(self) -> dict[str, object]:
            calls.append("list")
            return {"node_types": [{"name": "fetch-rss"}]}

        async def graph_get_node_type(self, name: str) -> dict[str, object]:
            calls.append(("show", name))
            return {"name": name}

        async def graph_create_node_type(self, name: str, payload: dict[str, object]) -> dict[str, object]:
            calls.append(("create", name, payload))
            return {"created": name}

        async def graph_save_node_type(self, name: str, payload: dict[str, object]) -> dict[str, object]:
            calls.append(("save", name, payload))
            return {"saved": name}

        async def graph_delete_node_type(self, name: str) -> dict[str, object]:
            calls.append(("delete", name))
            return {"deleted": name}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    for argv in (
        ["edera", "node-type", "list"],
        ["edera", "node-type", "show", "fetch-rss"],
        ["edera", "node-type", "create", "fetch-rss", "--file", str(node_type_file)],
        ["edera", "node-type", "save", "fetch-rss", "--file", str(node_type_file)],
        ["edera", "node-type", "delete", "fetch-rss"],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()
        capsys.readouterr()

    assert calls == [
        "list",
        ("show", "fetch-rss"),
        ("create", "fetch-rss", {"name": "fetch-rss", "handler": "rss.fetch"}),
        ("save", "fetch-rss", {"name": "fetch-rss", "handler": "rss.fetch"}),
        ("delete", "fetch-rss"),
    ]


def test_cli_handler_commands_use_graph_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    handler_file = tmp_path / "handler.py"
    handler_file.write_text("def run(ctx):\n    return {}\n", encoding="utf-8")
    calls: list[object] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def graph_list_handlers(self) -> dict[str, object]:
            calls.append("list")
            return {"handlers": [{"name": "rss.fetch"}]}

        async def graph_get_handler(self, name: str) -> dict[str, object]:
            calls.append(("show", name))
            return {"name": name, "content": "def run(ctx):\n    return {}\n"}

        async def graph_save_handler(self, name: str, code: str) -> dict[str, object]:
            calls.append(("save", name, code))
            return {"saved": name}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    for argv in (
        ["edera", "handler", "list"],
        ["edera", "handler", "show", "rss.fetch"],
        ["edera", "handler", "save", "rss.fetch", "--file", str(handler_file)],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()
        capsys.readouterr()

    monkeypatch.setattr("edera_core.cli.validate_handler", lambda path: [])
    monkeypatch.setattr("sys.argv", ["edera", "handler-validate", str(handler_file)])
    main()

    assert calls == [
        "list",
        ("show", "rss.fetch"),
        ("save", "rss.fetch", "def run(ctx):\n    return {}\n"),
    ]
    assert '"ok": true' in capsys.readouterr().out


def test_cli_config_system_and_generic_commands_use_config_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    system_file = tmp_path / "system.toml"
    system_file.write_text("handlers_dir = 'handlers'\n", encoding="utf-8")
    dag_file = tmp_path / "default.yaml"
    dag_file.write_text("name: default\n", encoding="utf-8")
    calls: list[object] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def config_list(self) -> dict[str, object]:
            calls.append("list")
            return {"configs": [{"kind": "dag", "name": "default.yaml"}]}

        async def config_read_system(self) -> dict[str, object]:
            calls.append("system-show")
            return {"content": "handlers_dir = 'handlers'\n"}

        async def config_save_system(self, content: str) -> dict[str, object]:
            calls.append(("system-save", content))
            return {"saved": "system"}

        async def config_read(self, kind: str, name: str) -> dict[str, object]:
            calls.append(("read", kind, name))
            return {"kind": kind, "name": name, "content": "name: default\n"}

        async def config_save(self, kind: str, name: str, content: str) -> dict[str, object]:
            calls.append(("save", kind, name, content))
            return {"saved": name}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    for argv in (
        ["edera", "config", "list"],
        ["edera", "config", "system", "show"],
        ["edera", "config", "system", "save", "--file", str(system_file)],
        ["edera", "config", "read", "dag", "default.yaml"],
        ["edera", "config", "save", "dag", "default.yaml", "--file", str(dag_file)],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()
        capsys.readouterr()

    assert calls == [
        "list",
        "system-show",
        ("system-save", "handlers_dir = 'handlers'\n"),
        ("read", "dag", "default.yaml"),
        ("save", "dag", "default.yaml", "name: default\n"),
    ]


def test_cli_config_entity_type_commands_use_config_service(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    entity_type_file = tmp_path / "stock.yaml"
    entity_type_file.write_text("name: stock\n", encoding="utf-8")
    calls: list[object] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def config_list_entity_types(self) -> dict[str, object]:
            calls.append("list")
            return {"entity_types": [{"name": "stock"}]}

        async def config_get_entity_type(self, name: str) -> dict[str, object]:
            calls.append(("show", name))
            return {"name": name, "content": "name: stock\n"}

        async def config_create_entity_type(self, name: str, content: str) -> dict[str, object]:
            calls.append(("create", name, content))
            return {"created": name}

        async def config_save_entity_type(self, name: str, content: str) -> dict[str, object]:
            calls.append(("save", name, content))
            return {"saved": name}

        async def config_delete_entity_type(self, name: str, cascade: bool = False) -> dict[str, object]:
            calls.append(("delete", name, cascade))
            return {"deleted": name}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    for argv in (
        ["edera", "config", "entity-type", "list"],
        ["edera", "config", "entity-type", "show", "stock"],
        ["edera", "config", "entity-type", "create", "stock", "--file", str(entity_type_file)],
        ["edera", "config", "entity-type", "save", "stock", "--file", str(entity_type_file)],
        ["edera", "config", "entity-type", "delete", "stock", "--cascade"],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()
        capsys.readouterr()

    assert calls == [
        "list",
        ("show", "stock"),
        ("create", "stock", "name: stock\n"),
        ("save", "stock", "name: stock\n"),
        ("delete", "stock", True),
    ]


def test_cli_query_commands_use_query_service(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[object] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def query_latest_briefing(self) -> dict[str, object]:
            calls.append("briefing-latest")
            return {"briefing": "latest"}

        async def query_list_briefings(self, created_from: str = "", created_to: str = "", limit: int = 50) -> dict[str, object]:
            calls.append(("briefing-list", created_from, created_to, limit))
            return {"briefings": []}

        async def query_get_briefing(self, briefing_id: str) -> dict[str, object]:
            calls.append(("briefing-show", briefing_id))
            return {"id": briefing_id}

        async def query_list_advices(
            self,
            stock_code: str = "",
            direction: str = "",
            created_from: str = "",
            created_to: str = "",
            limit: int = 50,
        ) -> dict[str, object]:
            calls.append(("advice-list", stock_code, direction, created_from, created_to, limit))
            return {"advices": []}

        async def query_get_advice(self, advice_id: str) -> dict[str, object]:
            calls.append(("advice-show", advice_id))
            return {"id": advice_id}

        async def query_results_summary(
            self,
            stock_code: str = "",
            direction: str = "",
            created_from: str = "",
            created_to: str = "",
        ) -> dict[str, object]:
            calls.append(("results-summary", stock_code, direction, created_from, created_to))
            return {"summary": []}

        async def query_node_outputs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
            calls.append(("node-outputs", node_id, run_id, limit))
            return {"outputs": []}

        async def query_node_history(self, dag_name: str, node_id: str, limit: int = 50) -> dict[str, object]:
            calls.append(("node-history", dag_name, node_id, limit))
            return {"history": []}

        async def query_child_run_for_parent(self, parent_run_id: str, parent_node_id: str) -> dict[str, object]:
            calls.append(("child-run", parent_run_id, parent_node_id))
            return {"run_id": "child-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    for argv in (
        ["edera", "query", "briefing", "latest"],
        ["edera", "query", "briefing", "list", "--limit", "20"],
        ["edera", "query", "briefing", "show", "briefing-1"],
        ["edera", "query", "advice", "list", "--stock-code", "600000", "--direction", "buy", "--limit", "20"],
        ["edera", "query", "advice", "show", "advice-1"],
        ["edera", "query", "results", "summary", "--stock-code", "600000"],
        ["edera", "query", "node-outputs", "--node-id", "reader", "--run-id", "run-1", "--limit", "10"],
        ["edera", "query", "node-history", "default", "reader", "--limit", "10"],
        ["edera", "query", "child-run", "--parent-run-id", "parent-1", "--parent-node-id", "subdag-node"],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()
        capsys.readouterr()

    assert calls == [
        "briefing-latest",
        ("briefing-list", "", "", 20),
        ("briefing-show", "briefing-1"),
        ("advice-list", "600000", "buy", "", "", 20),
        ("advice-show", "advice-1"),
        ("results-summary", "600000", "", "", ""),
        ("node-outputs", "reader", "run-1", 10),
        ("node-history", "default", "reader", 10),
        ("child-run", "parent-1", "subdag-node"),
    ]


def test_cli_source_commands_use_query_and_system_services(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[object] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def query_source_health(self) -> dict[str, object]:
            calls.append("health")
            return {"sources": []}

        async def query_source_logs(self, source_name: str = "", limit: int = 50) -> dict[str, object]:
            calls.append(("logs", source_name, limit))
            return {"logs": []}

        async def system_create_repair_task(self, source_name: str) -> dict[str, object]:
            calls.append(("repair-task", source_name))
            return {"task_id": "task-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    for argv in (
        ["edera", "source", "health"],
        ["edera", "source", "logs", "--source-name", "rss-main", "--limit", "20"],
        ["edera", "source", "repair-task", "rss-main"],
    ):
        monkeypatch.setattr("sys.argv", argv)
        main()
        capsys.readouterr()

    assert calls == ["health", ("logs", "rss-main", 20), ("repair-task", "rss-main")]


def test_cli_node_logs_uses_grpc_query(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def query_node_logs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
            calls.append("logs")
            assert node_id == "reader"
            assert run_id == "run-1"
            assert limit == 100
            return {"logs": [{"kind": "summary", "path": "/tmp/summary.json"}]}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "node", "logs", "reader", "--run-id", "run-1"])

    main()

    assert calls == ["logs"]
    assert "/tmp/summary.json" in capsys.readouterr().out


def test_cli_watch_modes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, str]] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def dag_status(self, dag_name: str) -> dict[str, object]:
            calls.append(("dag-status", dag_name))
            return {"dag": dag_name, "count": len(calls)}

        async def graph_runtime_status(self, run_id: str = "") -> dict[str, object]:
            calls.append(("runtime-status", run_id))
            return {"run_id": run_id, "count": len(calls)}

        async def system_scheduler_status(self) -> dict[str, object]:
            calls.append(("scheduler-status", ""))
            return {"scheduler": "running", "count": len(calls)}

        async def query_source_health(self) -> dict[str, object]:
            calls.append(("source-health", ""))
            return {"sources": [{"name": "rss-main"}], "count": len(calls)}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    monkeypatch.setattr("sys.argv", ["edera", "dag", "status", "default", "--watch", "--interval", "0", "--watch-count", "2"])
    main()
    assert calls == [("dag-status", "default"), ("dag-status", "default")]
    assert len(capsys.readouterr().out.strip().splitlines()) == 2
    calls.clear()

    monkeypatch.setattr("sys.argv", ["edera", "dag", "runtime-status", "--run-id", "run-1", "--watch", "--interval", "0", "--watch-count", "2"])
    main()
    assert calls == [("runtime-status", "run-1"), ("runtime-status", "run-1")]
    assert len(capsys.readouterr().out.strip().splitlines()) == 2
    calls.clear()

    monkeypatch.setattr("sys.argv", ["edera", "system", "scheduler-status", "--watch", "--interval", "0", "--watch-count", "2"])
    main()
    assert calls == [("scheduler-status", ""), ("scheduler-status", "")]
    assert len(capsys.readouterr().out.strip().splitlines()) == 2
    calls.clear()

    monkeypatch.setattr("sys.argv", ["edera", "source", "health", "--watch", "--interval", "0", "--watch-count", "2"])
    main()
    assert calls == [("source-health", ""), ("source-health", "")]
    assert len(capsys.readouterr().out.strip().splitlines()) == 2


def test_cli_tail_modes_deduplicate_logs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    node_calls = 0
    source_calls = 0

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def query_node_logs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
            nonlocal node_calls
            node_calls += 1
            assert node_id == "reader"
            assert run_id == "run-1"
            return {"logs": [{"id": "n1"}]} if node_calls == 1 else {"logs": [{"id": "n1"}, {"id": "n2"}]}

        async def query_source_logs(self, source_name: str = "", limit: int = 50) -> dict[str, object]:
            nonlocal source_calls
            source_calls += 1
            assert source_name == "rss-main"
            assert limit == 10
            return {"logs": [{"id": "s1"}]} if source_calls == 1 else {"logs": [{"id": "s1"}, {"id": "s2"}]}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    monkeypatch.setattr("sys.argv", ["edera", "node", "logs", "reader", "--run-id", "run-1", "--tail", "--interval", "0", "--watch-count", "2"])
    main()
    node_lines = capsys.readouterr().out.strip().splitlines()
    assert len(node_lines) == 2
    assert '"n1"' in node_lines[0]
    assert '"n2"' in node_lines[1]
    assert '"n1"' not in node_lines[1]

    monkeypatch.setattr("sys.argv", ["edera", "source", "logs", "--source-name", "rss-main", "--limit", "10", "--tail", "--interval", "0", "--watch-count", "2"])
    main()
    source_lines = capsys.readouterr().out.strip().splitlines()
    assert len(source_lines) == 2
    assert '"s1"' in source_lines[0]
    assert '"s2"' in source_lines[1]
    assert '"s1"' not in source_lines[1]


def test_cli_control_plane_pagination_display(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[object] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def query_list_briefings(self, created_from: str = "", created_to: str = "", limit: int = 50) -> dict[str, object]:
            calls.append(("briefings", created_from, created_to, limit))
            return {"briefings": [{"id": "b1"}, {"id": "b2"}, {"id": "b3"}]}

        async def query_list_advices(
            self,
            stock_code: str = "",
            direction: str = "",
            created_from: str = "",
            created_to: str = "",
            limit: int = 50,
        ) -> dict[str, object]:
            calls.append(("advices", stock_code, direction, created_from, created_to, limit))
            return {"advices": [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]}

        async def query_node_outputs(self, node_id: str = "", run_id: str = "", limit: int = 100) -> dict[str, object]:
            calls.append(("node-outputs", node_id, run_id, limit))
            return {"outputs": [{"id": "o1"}, {"id": "o2"}, {"id": "o3"}]}

        async def query_source_logs(self, source_name: str = "", limit: int = 50) -> dict[str, object]:
            calls.append(("source-logs", source_name, limit))
            return {"logs": [{"id": "l1"}, {"id": "l2"}, {"id": "l3"}]}

        async def graph_list_dags(self) -> dict[str, object]:
            calls.append("dags")
            return {"dags": [{"name": "d1"}, {"name": "d2"}, {"name": "d3"}]}

        async def graph_list_handlers(self) -> dict[str, object]:
            calls.append("handlers")
            return {"handlers": [{"name": "h1"}, {"name": "h2"}, {"name": "h3"}]}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)

    monkeypatch.setattr("sys.argv", ["edera", "query", "briefing", "list", "--limit", "2", "--offset", "1"])
    main()
    assert [item["id"] for item in json.loads(capsys.readouterr().out)["briefings"]] == ["b2", "b3"]

    monkeypatch.setattr("sys.argv", ["edera", "query", "advice", "list", "--limit", "2", "--offset", "1"])
    main()
    assert [item["id"] for item in json.loads(capsys.readouterr().out)["advices"]] == ["a2", "a3"]

    monkeypatch.setattr("sys.argv", ["edera", "query", "node-outputs", "--limit", "2", "--offset", "1"])
    main()
    assert [item["id"] for item in json.loads(capsys.readouterr().out)["outputs"]] == ["o2", "o3"]

    monkeypatch.setattr("sys.argv", ["edera", "source", "logs", "--source-name", "rss-main", "--limit", "2", "--offset", "1"])
    main()
    assert [item["id"] for item in json.loads(capsys.readouterr().out)["logs"]] == ["l2", "l3"]

    monkeypatch.setattr("sys.argv", ["edera", "dag", "list", "--limit", "1", "--offset", "1"])
    main()
    assert [item["name"] for item in json.loads(capsys.readouterr().out)["dags"]] == ["d2"]

    monkeypatch.setattr("sys.argv", ["edera", "handler", "list", "--limit", "1", "--offset", "1"])
    main()
    assert [item["name"] for item in json.loads(capsys.readouterr().out)["handlers"]] == ["h2"]

    assert calls == [
        ("briefings", "", "", 2),
        ("advices", "", "", "", "", 2),
        ("node-outputs", "", "", 2),
        ("source-logs", "rss-main", 2),
        "dags",
        "handlers",
    ]


def test_cli_node_output_remains_business_only(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def node_output(self, node_id: str, run_id: str | None = None) -> list[dict[str, object]]:
            calls.append("output")
            assert node_id == "reader"
            assert run_id == "run-1"
            return [{"payload": {"value": 1}}]

        async def query_node_logs(self, *_args, **_kwargs) -> dict[str, object]:
            raise AssertionError("node output must not query logs")

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "node", "output", "reader", "--run-id", "run-1"])

    main()

    assert calls == ["output"]
    assert '"payload": {"value": 1}' in capsys.readouterr().out


def test_cli_node_output_export_writes_payload_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "payload.json"

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def node_output(self, node_id: str, run_id: str | None = None) -> list[dict[str, object]]:
            assert node_id == "reader"
            assert run_id == "run-1"
            return [{"payload": {"value": 1}}]

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "node", "output", "export", "--run-id", "run-1", "--node", "reader", "--out", str(target)],
    )

    main()

    assert json.loads(target.read_text(encoding="utf-8")) == [{"value": 1}]
    assert '"entries": 1' in capsys.readouterr().out


def test_cli_node_output_export_does_not_query_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = tmp_path / "payload.json"

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            pass

        async def node_output(self, node_id: str, run_id: str | None = None) -> list[dict[str, object]]:
            return [{"payload": {"business": True}}]

        async def query_node_logs(self, *_args, **_kwargs) -> dict[str, object]:
            raise AssertionError("export must not query logs")

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "node", "output", "export", "--run-id", "run-1", "--node", "reader", "--out", str(target)],
    )

    main()

    assert "execution log" not in target.read_text(encoding="utf-8")
    capsys.readouterr()


def test_cli_node_output_export_requires_out(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            raise AssertionError("invalid export must not open gRPC client")

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "node", "output", "export", "--run-id", "run-1", "--node", "reader"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code != 0
    assert "--out" in capsys.readouterr().err


def test_cli_dag_run_inputs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def dag_run(
            self,
            dag_name: str,
            payload: object | None = None,
            *,
            source_shared_inputs: object | None = None,
            node_inputs: dict[str, object] | None = None,
            append_nodes: list[str] | None = None,
        ) -> dict[str, object]:
            assert dag_name == "default"
            assert payload == {"symbol": "AAPL"}
            assert source_shared_inputs is None
            assert node_inputs is None
            assert append_nodes is None
            return {"run_id": "run-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "dag", "run", "default", "--inputs", '{"symbol":"AAPL"}'])

    main()

    assert '"run_id": "run-1"' in capsys.readouterr().out


def test_cli_dag_run_temporary_inputs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def dag_run(
            self,
            dag_name: str,
            payload: object | None = None,
            *,
            source_shared_inputs: object | None = None,
            node_inputs: dict[str, object] | None = None,
            append_nodes: list[str] | None = None,
        ) -> dict[str, object]:
            assert dag_name == "default"
            assert payload == {"symbol": "AAPL"}
            assert source_shared_inputs == {"shared": True}
            assert node_inputs == {"worker": "entity://custom"}
            assert append_nodes == ["worker"]
            return {"run_id": "run-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "dag",
            "run",
            "default",
            "--inputs",
            '{"symbol":"AAPL"}',
            "--source-shared-inputs",
            '{"shared":true}',
            "--node-inputs",
            '{"worker":"entity://custom"}',
            "--append-nodes",
            "worker",
        ],
    )

    main()

    assert '"run_id": "run-1"' in capsys.readouterr().out


def test_cli_dag_stop(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def dag_stop(self, dag_name: str, force: bool = False) -> dict[str, object]:
            assert dag_name == "default"
            assert force is True
            return {"dag_name": dag_name, "stopped": True}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "dag", "stop", "default", "--force"])

    main()

    assert '"stopped": true' in capsys.readouterr().out


def test_cli_dag_retry(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def dag_retry(
            self,
            dag_name: str,
            run_id: str = "",
            node_ids: list[str] | None = None,
            mode: str = "single",
            payload: object | None = None,
            *,
            source_shared_inputs: object | None = None,
            node_inputs: dict[str, object] | None = None,
            append_nodes: list[str] | None = None,
        ) -> dict[str, object]:
            assert dag_name == "default"
            assert run_id == "run-1"
            assert node_ids == ["node-a", "node-b"]
            assert mode == "multi"
            assert payload == {"reason": "test"}
            assert source_shared_inputs is None
            assert node_inputs is None
            assert append_nodes is None
            return {"run_id": "retry-run-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "dag", "retry", "default", "--run-id", "run-1", "--nodes", "node-a,node-b", "--mode", "multi", "--payload", '{"reason":"test"}'],
    )

    main()

    assert '"run_id": "retry-run-1"' in capsys.readouterr().out


def test_cli_dag_retry_source_shared_inputs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            pass

        async def dag_retry(
            self,
            dag_name: str,
            run_id: str = "",
            node_ids: list[str] | None = None,
            mode: str = "single",
            payload: object | None = None,
            *,
            source_shared_inputs: object | None = None,
            node_inputs: dict[str, object] | None = None,
            append_nodes: list[str] | None = None,
        ) -> dict[str, object]:
            assert source_shared_inputs == {"entity": "entity://fix"}
            return {"run_id": "retry-run-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "dag", "retry", "default", "--nodes", "reader", "--source-shared-inputs", '{"entity":"entity://fix"}'],
    )

    main()

    assert '"run_id": "retry-run-1"' in capsys.readouterr().out


def test_cli_dag_retry_node_inputs_and_append_nodes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            pass

        async def dag_retry(
            self,
            dag_name: str,
            run_id: str = "",
            node_ids: list[str] | None = None,
            mode: str = "single",
            payload: object | None = None,
            *,
            source_shared_inputs: object | None = None,
            node_inputs: dict[str, object] | None = None,
            append_nodes: list[str] | None = None,
        ) -> dict[str, object]:
            assert node_inputs == {"analyzer": {"test_mode": True}}
            assert append_nodes == ["analyzer"]
            return {"run_id": "retry-run-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "edera",
            "dag",
            "retry",
            "default",
            "--nodes",
            "analyzer",
            "--node-inputs",
            '{"analyzer":{"test_mode":true}}',
            "--append-nodes",
            "analyzer",
        ],
    )

    main()

    assert '"run_id": "retry-run-1"' in capsys.readouterr().out


def test_cli_dag_retry_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            pass

        async def dag_retry(self, *_args, **_kwargs) -> dict[str, object]:
            raise AssertionError("invalid JSON must not call retry")

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "dag", "retry", "default", "--node-inputs", "{bad-json}"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert "Expecting property name" in capsys.readouterr().err


def test_cli_system_repair_source(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            pass

        async def system_create_repair_task(self, source_name: str) -> dict[str, object]:
            assert source_name == "rss-main"
            return {
                "task_id": "task-1",
                "task_path": "/tmp/task.json",
                "source_name": source_name,
                "created_at": "2026-06-10T00:00:00Z",
            }

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "system", "repair-source", "rss-main"])

    main()

    assert '"task_id": "task-1"' in capsys.readouterr().out


@pytest.mark.parametrize("detail", ["FAILED_PRECONDITION: source is not escalated", "NOT_FOUND: source not found"])
def test_cli_system_repair_source_reports_server_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    detail: str,
) -> None:
    class FakeRpcError(grpc.RpcError):
        def details(self) -> str:
            return detail

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            pass

        async def system_create_repair_task(self, source_name: str) -> dict[str, object]:
            raise FakeRpcError()

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "system", "repair-source", "rss-main"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 1
    assert detail in capsys.readouterr().err


def test_event_emit(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def event_emit(self, event: str, payload: object | None, *, source: str, depth: int) -> dict[str, object]:
            assert event == "event:price-drop"
            assert payload == {"symbol": "TEST"}
            assert source == "cli"
            assert depth == 0
            return {"event": event, "fired": ["dag:default"]}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        ["edera", "event", "emit", "event:price-drop", "--payload-json", '{"symbol":"TEST"}'],
    )

    main()

    assert '"fired": ["dag:default"]' in capsys.readouterr().out


def _set_server_env(monkeypatch: pytest.MonkeyPatch, running_server) -> None:
    monkeypatch.setenv("EDERA_SERVER_ADDR", running_server["addr"])
    monkeypatch.setenv("EDERA_CLIENT_CERT", running_server["certs"]["client_cert_pem"])
    monkeypatch.setenv("EDERA_CLIENT_KEY", running_server["certs"]["client_key_pem"])
    monkeypatch.setenv("EDERA_CA_CERT", running_server["certs"]["ca_cert_pem"])


def _import_stock_test(running_server, tmp_path: Path) -> None:
    path = tmp_path / "stock-test.yaml"
    path.write_text(
        "type: stock\n"
        "id: stock-test\n"
        "attributes:\n"
        "  code: TEST\n"
        "  name: Test\n",
        encoding="utf-8",
    )

    async def run() -> None:
        client = GrpcClient(running_server["addr"])
        try:
            await client.entity_import(str(path))
        finally:
            await client.close()

    asyncio.run(run())
