from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from stockimformation_core.cert import CertificateAuthority
from stockimformation_core.config.schema import AgentNodeConfig, DagConfig, DagNodeConfig, FunctionNodeConfig, NodeConfig
from stockimformation_core.dag.loader import load_graph
from stockimformation_core.dag.runner import DagRunner
from stockimformation_core.daemon import RigDaemon, _DagService, _NodeService, _SystemService
from stockimformation_core.events import event_bus
from stockimformation_core.grpc_client import RigGrpcClient
from stockimformation_core.hot_reload import clear_handler_cache
from stockimformation_core.node.executor import NodeExecutor
from stockimformation_core.node.models import NodeInput


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
    result = await DagRunner(executor).run(graph, "cycle", {"ticker": "AAPL"})

    assert result.node_outputs["source"].payload == "AAPL"
    assert result.node_outputs["sink"].ok
    assert result.node_outputs["sink"].payload == ["AAPL", None]


@pytest.mark.asyncio
async def test_agent_subprocess_launches_with_env_and_streaming(tmp_path: Path) -> None:
    fake_pi = tmp_path / "pi"
    capture = tmp_path / "capture.txt"
    fake_pi.write_text(
        "#!/usr/bin/env python3\n"
        "import os, pathlib, sys\n"
        f"pathlib.Path({str(capture)!r}).write_text(os.getcwd() + '\\n' + os.environ['RIG_IDENTITY'] + '\\n' + ' '.join(sys.argv[1:]))\n"
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
        stdout_recorder=lambda _cycle, _node, line: _append(events, line),
    )

    output = await executor.execute("agent", NodeInput(cycle_id="cycle", payload={"prompt": "do it"}))

    assert output.ok
    assert events == ["hello"]
    captured = capture.read_text(encoding="utf-8").splitlines()
    assert captured[0] == str(workdir)
    assert captured[1] == "node:agent"
    assert "--session-dir" in captured[2]


def test_clear_handler_cache() -> None:
    executor = NodeExecutor({}, system=_system(), runtime=_runtime())
    executor._modules["handler"] = object()  # type: ignore[assignment]

    clear_handler_cache(executor)

    assert executor._modules == {}


def test_certificate_authority_issues_agent_cert(tmp_path: Path) -> None:
    issued = CertificateAuthority(tmp_path).issue_client("node:agent-1", 60)

    assert issued.cert_path.exists()
    assert issued.key_path.exists()
    assert issued.common_name == "node:agent-1"


@pytest.mark.asyncio
async def test_daemon_grpc_server_start(tmp_path: Path) -> None:
    daemon = RigDaemon(tmp_path, "127.0.0.1:0")
    await daemon.start()
    try:
        assert isinstance(daemon.bound_port, int)
    finally:
        await daemon.stop()


@pytest.mark.asyncio
async def test_rig_grpc_client_connects_to_daemon(tmp_path: Path) -> None:
    daemon = RigDaemon(tmp_path, "127.0.0.1:0")
    issued = daemon.ca.issue_client("human:test", 3600)
    (tmp_path / "client.crt").write_bytes(issued.cert_path.read_bytes())
    (tmp_path / "client.key").write_bytes(issued.key_path.read_bytes())
    (tmp_path / "ca.crt").write_bytes(daemon.ca.ca_cert_pem())
    await daemon.start()
    client = RigGrpcClient(f"127.0.0.1:{daemon.bound_port}", tmp_path)
    try:
        assert await client.health() == {"ok": True}
    finally:
        await client.close()
        await daemon.stop()


@pytest.mark.asyncio
async def test_daemon_bootstrap_issues_client_cert_for_mtls_port(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    daemon = RigDaemon(tmp_path / "rig", "127.0.0.1:0", config_dir, bootstrap_address="127.0.0.1:0")
    await daemon.start()
    bootstrap = RigGrpcClient(f"127.0.0.1:{daemon.bootstrap_bound_port}", tmp_path / "bootstrap", allow_insecure=True)
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    try:
        certs = await bootstrap.init_client("human:test")
        (client_dir / "client.crt").write_text(certs["client_cert_pem"], encoding="utf-8")
        (client_dir / "client.key").write_text(certs["client_key_pem"], encoding="utf-8")
        (client_dir / "ca.crt").write_text(certs["ca_cert_pem"], encoding="utf-8")
    finally:
        await bootstrap.close()
    client = RigGrpcClient(f"127.0.0.1:{daemon.bound_port}", client_dir)
    try:
        assert await client.health() == {"ok": True}
        assert (await client.dag_status("default"))["dag_name"] == "default"
    finally:
        await client.close()
        await daemon.stop()


@pytest.mark.asyncio
async def test_daemon_streams_events_over_grpc(tmp_path: Path) -> None:
    daemon = RigDaemon(tmp_path / "rig", "127.0.0.1:0", bootstrap_address="127.0.0.1:0")
    service = _SystemService(daemon, bootstrap=False)
    request = daemon._proto.pb2.EventSubscribeRequest(node_id="reader")
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
async def test_pipeline_publishes_dag_status_events(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "dags" / "default.yaml").write_text("name: default\nnodes: []\nedges: []\n", encoding="utf-8")
    from stockimformation_core.pipeline import PipelineController

    controller = PipelineController(config_dir)
    await controller.start(run_startup=False)
    events = event_bus.subscribe()
    pending = asyncio.create_task(events.__anext__())
    try:
        cycle_id = await controller.run_now("manual", "default")
        first = await asyncio.wait_for(pending, timeout=1)
        assert first.type == "dag.status"
        assert first.payload == {"cycle_id": cycle_id, "dag_name": "default", "status": "started"}
        second = await asyncio.wait_for(events.__anext__(), timeout=1)
        assert second.type == "dag.status"
        assert second.payload["cycle_id"] == cycle_id
        assert second.payload["dag_name"] == "default"
        assert second.payload["status"] == "failed"
    finally:
        pending.cancel()
        await events.aclose()
        await controller.shutdown()


@pytest.mark.asyncio
async def test_daemon_grpc_entity_update_enforces_node_permissions(tmp_path: Path) -> None:
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
    data_dir = tmp_path / "rig"
    daemon = RigDaemon(data_dir, "127.0.0.1:0", config_dir)
    issued = daemon.ca.issue_client("node:reader", 3600)
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "client.crt").write_bytes(issued.cert_path.read_bytes())
    (client_dir / "client.key").write_bytes(issued.key_path.read_bytes())
    (client_dir / "ca.crt").write_bytes(daemon.ca.ca_cert_pem())
    await daemon.start()
    client = RigGrpcClient(f"127.0.0.1:{daemon.bound_port}", client_dir)
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
    daemon = RigDaemon(tmp_path / "rig", "127.0.0.1:0", config_dir)
    service = _DagService(daemon)

    response = await service.Edit(
        daemon._proto.pb2.DagEditRequest(
            name="default",
            operation="add-node",
            json='{"id":"reader-1","type":"reader","config":{}}',
        ),
        _FakeGrpcContext(),
    )

    assert json.loads(response.json) == {"updated": True, "dag": "default"}
    assert "reader-1" in (config_dir / "dags" / "default.yaml").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_daemon_node_stop_and_resume_use_controller(tmp_path: Path) -> None:
    config_dir = _minimal_config(tmp_path)
    (config_dir / "dags" / "default.yaml").write_text(
        "name: default\nnodes:\n- id: reader-1\n  type: reader\nedges: []\n",
        encoding="utf-8",
    )

    class Controller:
        agent_certificate_issuer = None

        async def stop_current(self, dag_name: str, force: bool = False, node_id: str | None = None) -> str:
            assert dag_name == "default"
            assert node_id == "reader-1"
            return "cycle-1"

        async def resume_node(self, dag_name: str, cycle_id: str, node_id: str, payload: object) -> str:
            assert dag_name == "default"
            assert cycle_id == "cycle-1"
            assert node_id == "reader-1"
            assert payload == {"resume_session": "sandbox:reader-1:cycle-1", "prompt": "adjust"}
            return cycle_id

    daemon = RigDaemon(tmp_path / "rig", "127.0.0.1:0", config_dir, controller=Controller())  # type: ignore[arg-type]
    service = _NodeService(daemon)

    stopped = await service.Stop(daemon._proto.pb2.NodeRef(id="reader-1"), _FakeGrpcContext())
    resumed = await service.Resume(
        daemon._proto.pb2.NodeResumeRequest(id="reader-1", cycle_id="cycle-1", prompt="adjust"),
        _FakeGrpcContext(),
    )

    assert stopped.status == "stopped"
    assert resumed.cycle_id == "cycle-1"


async def _append(items: list[str], value: str) -> None:
    items.append(value)


def _system():
    from stockimformation_core.config.schema import SystemConfig

    return SystemConfig()


def _runtime():
    from stockimformation_core.config.schema import RuntimeSettings

    return RuntimeSettings()


class _FakeGrpcContext:
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
        f'database_url = "sqlite+aiosqlite:///{tmp_path / "test.db"}"\nweb_host = "127.0.0.1"\n',
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
