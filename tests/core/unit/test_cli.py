from __future__ import annotations

import os
from pathlib import Path

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
    assert "EDERA_SERVER_ADDR not set" in capsys.readouterr().err


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

    import asyncio

    assert asyncio.run(_grpc_client_init("127.0.0.1:9091", "human:test")) == {
        "client_cert_pem": "cert",
        "client_key_pem": "key",
        "ca_cert_pem": "ca",
    }
    assert calls == [("127.0.0.1:9091", True)]


def test_cli_entity_query_uses_running_server(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    monkeypatch.setattr("sys.argv", ["edera", "entity", "query", "type=stock"])

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
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
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
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
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
    calls: list[tuple[str, dict[str, object], str]] = []

    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def entity_create(self, type_name: str, attributes: dict[str, object], entity_id: str = "") -> dict[str, object]:
            calls.append((type_name, attributes, entity_id))
            return {"id": entity_id, "type": type_name, "attributes": attributes}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "entity", "import", "--file", str(path)])

    main()

    assert calls == [("node", {"name": "reader", "type": "function"}, "node-1")]
    assert '"id": "node-1"' in capsys.readouterr().out


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


def test_cli_dag_status_uses_grpc(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    running_server,
) -> None:
    _set_server_env(monkeypatch, running_server)
    monkeypatch.setattr("sys.argv", ["edera", "dag", "status", "default"])

    main()

    assert '"dag_name": "default"' in capsys.readouterr().out


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


def test_cli_dag_run_inputs(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class FakeClient:
        def __init__(self, address: str | None = None, *, identity: str | None = None) -> None:
            assert address == "127.0.0.1:9090"
            assert identity == "human"

        async def dag_run(self, dag_name: str, payload: object | None = None) -> dict[str, object]:
            assert dag_name == "default"
            assert payload == {"symbol": "AAPL"}
            return {"run_id": "run-1"}

        async def close(self) -> None:
            return None

    monkeypatch.setenv("EDERA_SERVER_ADDR", "127.0.0.1:9090")
    monkeypatch.setattr("edera_core.cli.GrpcClient", FakeClient)
    monkeypatch.setattr("sys.argv", ["edera", "dag", "run", "default", "--inputs", '{"symbol":"AAPL"}'])

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
        ) -> dict[str, object]:
            assert dag_name == "default"
            assert run_id == "run-1"
            assert node_ids == ["node-a", "node-b"]
            assert mode == "multi"
            assert payload == {"reason": "test"}
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
