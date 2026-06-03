from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID
from pydantic import ValidationError

from edera_core.cert import CertificateAuthority
from edera_core.config.schema import AgentNodeConfig, DagConfig, DagNodeConfig, FunctionNodeConfig, NodeConfig
from edera_core.dag.loader import load_graph
from edera_core.dag.runner import DagRunner
from edera_core.server import Server, _DagService, _NodeService, _SystemService, ensure_ca, ensure_server_cert, resolve_data_dir
from edera_core.events import event_bus
from edera_core.grpc_client import GrpcClient, _channel_credentials
from edera_core.hot_reload import clear_handler_cache
from edera_core.node.executor import NodeExecutor, _agent_cert_env, _agent_session_dir
from edera_core.node.models import NodeInput


def test_node_config_discriminated_union() -> None:
    function = NodeConfig.model_validate(
        {"name": "f", "type": "function", "handler": "run", "input_type": "Any", "output_type": "Any"}
    )
    agent = NodeConfig.model_validate(
        {"name": "a", "type": "agent", "model": "m", "workdir": "/tmp", "input_type": "Any", "output_type": "Any"}
    )
    dag = NodeConfig.model_validate(
        {"name": "d", "type": "dag", "dag_ref": "child", "input_type": "Any", "output_type": "Any"}
    )

    assert isinstance(function, FunctionNodeConfig)
    assert isinstance(agent, AgentNodeConfig)
    assert isinstance(dag, DagNodeConfig)
    assert "session_dir" not in AgentNodeConfig.model_fields
    with pytest.raises(ValidationError):
        NodeConfig.model_validate({"name": "bad", "type": "agent", "input_type": "Any", "output_type": "Any"})


def test_dag_config_inputs_and_optional_edges() -> None:
    dag = DagConfig.model_validate(
        {
            "name": "d",
            "inputs": [{"name": "ticker", "type": "string"}],
            "nodes": [{"id": "source", "type": "source"}, {"id": "sink", "type": "sink"}],
            "edges": [{"from": "source", "to": "sink", "optional": True}],
        }
    )
    nodes = {
        "source": NodeConfig(name="source", role="source", handler="source", input_type="Any", output_type="Any"),
        "sink": NodeConfig(name="sink", handler="sink", input_type="Any", output_type="Any"),
    }
    graph = load_graph(dag, nodes)

    assert dag.inputs[0].name == "ticker"
    assert ("source", "sink") in graph.optional_edges


@pytest.mark.asyncio
async def test_dag_input_binding_and_optional_barrier() -> None:
    nodes = {
        "source": NodeConfig(
            name="source",
            role="source",
            handler="source",
            input_type="Any",
            output_type="Any",
            input_binding="ticker",
        ),
        "optional": NodeConfig(name="optional", role="source", handler="optional", input_type="Any", output_type="Any"),
        "sink": NodeConfig(name="sink", handler="sink", input_type="Any", output_type="Any"),
    }
    dag = DagConfig.model_validate(
        {
            "name": "d",
            "nodes": [
                {"id": "source", "type": "source"},
                {"id": "optional", "type": "optional"},
                {"id": "sink", "type": "sink"},
            ],
            "edges": [{"from": "source", "to": "sink"}, {"from": "optional", "to": "sink", "optional": True}],
        }
    )
    graph = load_graph(dag, nodes)

    async def source(node_input: NodeInput) -> object:
        return node_input.payload

    async def optional(_node_input: NodeInput) -> object:
        raise RuntimeError("optional failed")

    async def sink(node_input: NodeInput) -> object:
        return node_input.payload

    executor = NodeExecutor(nodes, system=_system(), runtime=_runtime(), handlers={"source": source, "optional": optional, "sink": sink}, instances=graph.instances)
    result = await DagRunner(executor).run(graph, "run", {"ticker": "AAPL"})

    assert result.node_outputs["source"].payload == "AAPL"
    assert result.node_outputs["sink"].ok
    assert result.node_outputs["sink"].payload == "AAPL"


@pytest.mark.asyncio
async def test_agent_subprocess_launches_with_env_and_streaming(tmp_path: Path) -> None:
    fake_pi = tmp_path / "pi"
    capture = tmp_path / "capture.txt"
    fake_pi.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        f"pathlib.Path({str(capture)!r}).write_text(os.getcwd() + '\\n' + os.environ['EDERA_IDENTITY'] + '\\n' + json.dumps(sys.argv[1:]))\n"
        "print('hello')\n",
        encoding="utf-8",
    )
    fake_pi.chmod(0o755)
    workdir = tmp_path / "work"
    workdir.mkdir()
    events: list[str] = []
    nodes = {
        "agent": NodeConfig.model_validate(
            {
                "name": "agent",
                "type": "agent",
                "model": "m",
                "workdir": str(workdir),
                "input_type": "Any",
                "output_type": "Any",
            }
        )
    }
    executor = NodeExecutor(
        nodes,
        system=_system().model_copy(update={"workspace_root": tmp_path / "runs"}),
        runtime=_runtime().model_copy(update={"pi_bin": str(fake_pi)}),
        stdout_recorder=lambda _run, _node, line: _append(events, line),
        daemon_data_dir=tmp_path / "edera",
    )

    output = await executor.execute("agent", NodeInput(run_id="run", payload={"prompt": "do it"}))

    assert output.ok
    assert events == ["hello"]
    captured = capture.read_text(encoding="utf-8").splitlines()
    assert captured[0] == str(workdir)
    assert captured[1] == "node:agent"
    args = json.loads(captured[2])
    session_dir = Path(args[args.index("--session-dir") + 1])
    assert (session_dir / "runtime-context.json").exists()


def test_clear_handler_cache() -> None:
    executor = NodeExecutor({}, system=_system(), runtime=_runtime())
    executor._modules["handler"] = object()  # type: ignore[assignment]

    clear_handler_cache(executor)

    assert executor._modules == {}


def test_certificate_authority_issues_agent_cert(tmp_path: Path) -> None:
    issued = CertificateAuthority(tmp_path).issue_client("node:agent-1", 60)

    assert issued.cert_pem.startswith("-----BEGIN CERTIFICATE-----")
    assert issued.key_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert issued.ca_pem.startswith("-----BEGIN CERTIFICATE-----")
    assert issued.common_name == "node:agent-1"
    assert not (tmp_path / "certs").exists()


def test_grpc_client_loads_pem_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    pem = "-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----"
    monkeypatch.setenv("EDERA_CLIENT_CERT", pem)
    monkeypatch.setenv("EDERA_CLIENT_KEY", pem)
    monkeypatch.setenv("EDERA_CA_CERT", pem)

    assert _channel_credentials() is not None


def test_grpc_client_ignores_pem_file_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "client.crt").write_text("FAKEPEM", encoding="utf-8")
    monkeypatch.delenv("EDERA_CLIENT_CERT", raising=False)
    monkeypatch.delenv("EDERA_CLIENT_KEY", raising=False)
    monkeypatch.delenv("EDERA_CA_CERT", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

    assert _channel_credentials() is None


def test_daemon_data_dir_env_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDERA_DATA_DIR", "/tmp/test-edera-data")

    assert resolve_data_dir(None) == Path("/tmp/test-edera-data")


def test_daemon_ca_and_server_cert_generation(tmp_path: Path) -> None:
    ensure_ca(tmp_path)
    ensure_server_cert(tmp_path, "localhost")

    assert (tmp_path / "ca.crt").exists()
    assert (tmp_path / "ca.key").exists()
    assert (tmp_path / "server.crt").exists()
    assert (tmp_path / "server.key").exists()
    assert oct((tmp_path / "ca.key").stat().st_mode)[-3:] == "600"
    assert oct((tmp_path / "server.key").stat().st_mode)[-3:] == "600"


@pytest.mark.asyncio
async def test_bff_cert_uses_web_console_common_name_and_ttl(tmp_path: Path) -> None:
    daemon = Server(tmp_path / "edera", "127.0.0.1:0")
    service = _SystemService(daemon, bootstrap=True)

    response = await service.InitClient(daemon.pb2.ClientInitRequest(common_name="bff:web-console"), _FakeGrpcContext())
    cert = x509.load_pem_x509_certificate(response.client_cert_pem.encode())
    common_name = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc

    assert common_name == "bff:web-console"
    assert 6.9 <= (not_after - not_before).total_seconds() / 86400 <= 7.1
    assert response.client_key_pem.startswith("-----BEGIN PRIVATE KEY-----")
    assert response.ca_cert_pem.startswith("-----BEGIN CERTIFICATE-----")


def test_server_cert_san_reissues_when_public_host_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDERA_SERVER_PUBLIC_HOST", "old.edera.lan")
    ensure_server_cert(tmp_path, "0.0.0.0:9090")
    old_cert = x509.load_pem_x509_certificate((tmp_path / "server.crt").read_bytes())

    monkeypatch.setenv("EDERA_SERVER_PUBLIC_HOST", "new.edera.lan")
    ensure_server_cert(tmp_path, "0.0.0.0:9090")
    new_cert = x509.load_pem_x509_certificate((tmp_path / "server.crt").read_bytes())
    san = new_cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value

    assert new_cert.serial_number != old_cert.serial_number
    assert "new.edera.lan" in san.get_values_for_type(x509.DNSName)


def test_agent_cert_env_injects_pem_content() -> None:
    cert = SimpleNamespace(cert_pem="CERT_PEM", key_pem="KEY_PEM", ca_pem="CA_PEM")

    assert _agent_cert_env(cert) == {
        "EDERA_CLIENT_CERT": "CERT_PEM",
        "EDERA_CLIENT_KEY": "KEY_PEM",
        "EDERA_CA_CERT": "CA_PEM",
    }


def test_agent_session_dir_uses_daemon_data_dir(tmp_path: Path) -> None:
    assert _agent_session_dir(tmp_path, "dag", "agent", "run") == tmp_path / "sessions" / "dag" / "agent" / "run"


@pytest.mark.asyncio
async def test_daemon_grpc_server_start(tmp_path: Path) -> None:
    daemon = Server(tmp_path, "127.0.0.1:0")
    await daemon.start()
    try:
        assert isinstance(daemon.bound_port, int)
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_grpc_client_connects_to_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    daemon = Server(tmp_path, "127.0.0.1:0")
    issued = daemon.ca.issue_client("human:test", 3600)
    monkeypatch.setenv("EDERA_CLIENT_CERT", issued.cert_pem)
    monkeypatch.setenv("EDERA_CLIENT_KEY", issued.key_pem)
    monkeypatch.setenv("EDERA_CA_CERT", issued.ca_pem)
    await daemon.start()
    client = GrpcClient(f"127.0.0.1:{daemon.bound_port}")
    try:
        assert await client.health() == {"ok": True}
    finally:
        await client.close()
        await daemon.stop()


@pytest.mark.asyncio
async def test_daemon_bootstrap_issues_client_cert_for_mtls_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    daemon = Server(tmp_path / "edera", "127.0.0.1:0", config_dir)
    await daemon.start()
    bootstrap = GrpcClient(f"127.0.0.1:{daemon.bootstrap_bound_port}", force_insecure=True)
    try:
        certs = await bootstrap.init_client("human:test")
        monkeypatch.setenv("EDERA_CLIENT_CERT", certs["client_cert_pem"])
        monkeypatch.setenv("EDERA_CLIENT_KEY", certs["client_key_pem"])
        monkeypatch.setenv("EDERA_CA_CERT", certs["ca_cert_pem"])
    finally:
        await bootstrap.close()
    client = GrpcClient(f"127.0.0.1:{daemon.bound_port}")
    try:
        assert await client.health() == {"ok": True}
        assert (await client.dag_status("default"))["dag_name"] == "default"
    finally:
        await client.close()
        await daemon.stop()


@pytest.mark.asyncio
async def test_daemon_streams_events_over_grpc(tmp_path: Path) -> None:
    daemon = Server(tmp_path / "edera", "127.0.0.1:0")
    service = _SystemService(daemon, bootstrap=False)
    request = daemon.pb2.EventSubscribeRequest(node_id="reader")
    events = service.SubscribeEvents(request, _FakeGrpcContext())
    pending = asyncio.create_task(events.__anext__())
    await asyncio.sleep(0)
    await event_bus.publish("node.stdout", node_id="other", line="skip")
    await event_bus.publish("node.stdout", node_id="reader", line="hello")
    event = await asyncio.wait_for(pending, timeout=1)
    assert event.type == "node.stdout"
    assert event.json == '{"node_id": "reader", "line": "hello"}'
    await events.aclose()


@pytest.mark.asyncio
async def test_daemon_streams_node_waiting_over_grpc(tmp_path: Path) -> None:
    daemon = Server(tmp_path / "edera", "127.0.0.1:0")
    service = _SystemService(daemon, bootstrap=False)
    request = daemon.pb2.EventSubscribeRequest(node_id="gate")
    events = service.SubscribeEvents(request, _FakeGrpcContext())
    pending = asyncio.create_task(events.__anext__())
    await asyncio.sleep(0)
    await event_bus.publish("node.waiting", run_id="run", node="other", node_id="other", wait_for="event:other")
    await event_bus.publish("node.waiting", run_id="run", node="gate", node_id="gate", wait_for="event:approve:run")
    event = await asyncio.wait_for(pending, timeout=1)
    assert event.type == "node.waiting"
    assert json.loads(event.json) == {
        "run_id": "run",
        "node": "gate",
        "node_id": "gate",
        "wait_for": "event:approve:run",
    }
    await events.aclose()


@pytest.mark.asyncio
async def test_dag_controller_publishes_dag_status_events(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    from edera_core.dag_controller import DagController

    controller = DagController(config_dir)
    await controller.start(run_startup=False)
    events = event_bus.subscribe()
    pending = asyncio.create_task(events.__anext__())
    try:
        run_id = await controller.run_now("manual", "default")
        first = await asyncio.wait_for(pending, timeout=1)
        assert first.type == "dag.status"
        assert first.payload == {"run_id": run_id, "dag_name": "default", "status": "started"}
        second = await asyncio.wait_for(events.__anext__(), timeout=1)
        assert second.type == "dag.status"
        assert second.payload["run_id"] == run_id
        assert second.payload["dag_name"] == "default"
        assert second.payload["status"] == "failed"
    finally:
        pending.cancel()
        await events.aclose()
        await controller.shutdown()


@pytest.mark.asyncio
async def test_daemon_grpc_entity_update_enforces_node_permissions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = _minimal_config(tmp_path)
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
    data_dir = tmp_path / "edera"
    daemon = Server(data_dir, "127.0.0.1:0", config_dir)
    issued = daemon.ca.issue_client("node:reader", 3600)
    monkeypatch.setenv("EDERA_CLIENT_CERT", issued.cert_pem)
    monkeypatch.setenv("EDERA_CLIENT_KEY", issued.key_pem)
    monkeypatch.setenv("EDERA_CA_CERT", issued.ca_pem)
    await daemon.start()
    client = GrpcClient(f"127.0.0.1:{daemon.bound_port}", identity="node:reader")
    try:
        with pytest.raises(Exception):
            await client.entity_update("stock:TEST", "code", "NEW")
    finally:
        await client.close()
        await daemon.stop()


@pytest.mark.asyncio
async def test_daemon_dag_edit_persists_config(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    daemon = Server(tmp_path / "edera", "127.0.0.1:0", config_dir)
    service = _DagService(daemon)

    response = await service.Edit(
        daemon.pb2.DagEditRequest(
            name="default",
            operation="add-node",
            json='{"id":"reader-1","type":"reader","config":{}}',
        ),
        _FakeGrpcContext(),
    )

    assert json.loads(response.json) == {"updated": True, "dag": "default"}
    assert "reader-1" in (config_dir / "dags" / "default.yaml").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_daemon_dag_run_routes_through_emit(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    daemon = Server(tmp_path / "edera", "127.0.0.1:0", config_dir)

    class Controller:
        def __init__(self) -> None:
            self.calls = []

        async def emit(self, event, payload=None, *, source="rpc", depth=0):
            self.calls.append((event, payload, source, depth))
            return ["run-1"]

    controller = Controller()
    daemon.controller = controller
    service = _DagService(daemon)

    response = await service.Run(
        daemon.pb2.DagRunRequest(name="default", inputs_json='{"symbol":"TEST"}'),
        _FakeGrpcContext(),
    )

    assert response.run_id == "run-1"
    assert controller.calls == [("manual:dag:default", {"symbol": "TEST"}, "dag-service", 0)]


@pytest.mark.asyncio
async def test_daemon_node_stop_and_resume_use_controller(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "dags" / "default.yaml").write_text(
        "name: default\nnodes:\n- id: reader-1\n  type: reader\nedges: []\n",
        encoding="utf-8",
    )

    class Controller:
        agent_certificate_issuer = None
        daemon_data_dir = None

        async def stop_current(self, dag_name: str, force: bool = False, node_id: str | None = None) -> str:
            assert dag_name == "default"
            assert node_id == "reader-1"
            return "run-1"

        async def resume_node(self, dag_name: str, run_id: str, node_id: str, payload: object) -> str:
            assert dag_name == "default"
            assert run_id == "run-1"
            assert node_id == "reader-1"
            assert payload == {"resume_session": "sandbox:reader-1:run-1", "prompt": "adjust"}
            return run_id

    daemon = Server(tmp_path / "edera", "127.0.0.1:0", config_dir, controller=Controller())  # type: ignore[arg-type]
    service = _NodeService(daemon)

    stopped = await service.Stop(daemon.pb2.NodeRef(id="reader-1"), _FakeGrpcContext())
    resumed = await service.Resume(
        daemon.pb2.NodeResumeRequest(id="reader-1", run_id="run-1", prompt="adjust"),
        _FakeGrpcContext(),
    )

    assert stopped.status == "stopped"
    assert resumed.run_id == "run-1"
    assert daemon.controller.daemon_data_dir == tmp_path / "edera"


def test_daemon_resume_path_reissues_agent_cert(tmp_path: Path) -> None:
    issued: list[tuple[str, int]] = []

    def issuer(instance_id: str, ttl_seconds: int) -> object:
        issued.append((instance_id, ttl_seconds))
        return SimpleNamespace(cert_pem="CERT", key_pem="KEY", ca_pem="CA")

    executor = NodeExecutor(
        {
            "agent": NodeConfig.model_validate(
                {
                    "name": "agent",
                    "type": "agent",
                    "model": "m",
                    "input_type": "Any",
                    "output_type": "Any",
                }
            )
        },
        _system().model_copy(update={"llm_timeout_seconds": 12}),
        _runtime(),
        agent_certificate_issuer=issuer,
        daemon_data_dir=tmp_path / "edera",
    )
    cert = executor.agent_certificate_issuer("agent", 12)

    assert _agent_cert_env(cert)["EDERA_CLIENT_CERT"] == "CERT"
    assert issued == [("agent", 12)]


async def _append(items: list[str], value: str) -> None:
    items.append(value)


def _system():
    from edera_core.config.schema import SystemConfig

    return SystemConfig()


def _runtime():
    from edera_core.config.schema import RuntimeSettings

    return RuntimeSettings()


class _FakeGrpcContext:
    def invocation_metadata(self):
        return ()

    def auth_context(self):
        return {"x509_common_name": [b"human:test"]}

    async def abort(self, code, message):
        raise AssertionError(message)


def _minimal_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    schema_dir = tmp_path / "schemas" / "entity-types"
    schema_dir.mkdir(parents=True)
    (schema_dir / "stock.yaml").write_text(
        "display_name: Stock\nbusiness_id_field: code\ndisplay_template: '{code}'\nschema:\n  type: object\n  required: [code, name]\n  properties:\n    code:\n      type: string\n    name:\n      type: string\nfield_permissions:\n  code: read-only\n",
        encoding="utf-8",
    )
    (schema_dir / "node.yaml").write_text(
        "display_name: Node\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema:\n  type: object\n  required: [name]\n  properties:\n    name:\n      type: string\n",
        encoding="utf-8",
    )
    (schema_dir / "dag.yaml").write_text(
        "display_name: DAG\nbusiness_id_field: name\ndisplay_template: '{name}'\nschema:\n  type: object\n  required: [name]\n  properties:\n    name:\n      type: string\n",
        encoding="utf-8",
    )
    (config_dir / "entities.yaml").write_text(
        "entities:\n- id: stock-test\n  type: stock\n  attributes:\n    code: TEST\n    name: Test\n",
        encoding="utf-8",
    )
    (config_dir / "entity-relations.yaml").write_text("relations: []\n", encoding="utf-8")
    (config_dir / "system.toml").write_text(
        f'database_url = "sqlite+aiosqlite:///{tmp_path / "test.db"}"\n',
        encoding="utf-8",
    )
    (config_dir / "dags").mkdir()
    (config_dir / "nodes").mkdir()
    (config_dir / "nodes" / "reader.yaml").write_text(
        "name: reader\ntype: function\nhandler: reader\ninput_type: Any\noutput_type: Any\n",
        encoding="utf-8",
    )
    (config_dir / "skills").mkdir()
    return config_dir
