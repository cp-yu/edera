from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import grpc
import yaml

from stockimformation_core.cert import CertificateAuthority, IssuedCertificate
from stockimformation_core.config.entities import EntityStore, can_write, field_permission
from stockimformation_core.config.loader import load_app_config
from stockimformation_core.config.schema import EntityConfig
from stockimformation_core.events import event_bus
from stockimformation_core.grpc_runtime import load_rig_proto
from stockimformation_core.pipeline import PipelineController
from stockimformation_core.rig_cli import _entity_payload, _query


class RigDaemon:
    def __init__(
        self,
        data_dir: Path | None = None,
        address: str = "127.0.0.1:9090",
        config_dir: Path = Path("config"),
        controller: PipelineController | None = None,
        bootstrap_address: str | None = None,
    ) -> None:
        self.data_dir = resolve_data_dir(data_dir)
        self.address = address
        self.bootstrap_address = bootstrap_address or _bootstrap_address(address)
        self.config_dir = config_dir
        self.ca = CertificateAuthority(self.data_dir)
        self.controller = controller or PipelineController(
            config_dir,
            agent_certificate_issuer=self.issue_agent_certificate,
            daemon_data_dir=self.data_dir,
        )
        self._owns_controller = controller is None
        if controller is not None and controller.agent_certificate_issuer is None:
            controller.agent_certificate_issuer = self.issue_agent_certificate
        if controller is not None and controller.daemon_data_dir is None:
            controller.daemon_data_dir = self.data_dir
        self.server = grpc.aio.server()
        self.bootstrap_server = grpc.aio.server()
        self._proto = load_rig_proto()
        self.bound_port: int | None = None
        self.bootstrap_bound_port: int | None = None
        self._add_services()

    async def start(self) -> None:
        self.ca.ensure()
        (self.data_dir / "sessions").mkdir(parents=True, exist_ok=True)
        if self._owns_controller:
            await self.controller.start(run_startup=False)
        if os.environ.get("RIG_ENV") == "dev":
            self.bound_port = self.server.add_insecure_port(self.address)
        else:
            server_cert = self.ca.issue_server(self.address)
            credentials = grpc.ssl_server_credentials(
                [(server_cert.key_path.read_bytes(), server_cert.cert_path.read_bytes())],
                root_certificates=self.ca.ca_cert_pem(),
                require_client_auth=True,
            )
            self.bound_port = self.server.add_secure_port(self.address, credentials)
            self.bootstrap_bound_port = self.bootstrap_server.add_insecure_port(self.bootstrap_address)
        await self.server.start()
        if self.bootstrap_bound_port is not None:
            await self.bootstrap_server.start()

    async def wait_closed(self) -> None:
        await self.server.wait_for_termination()

    async def stop(self, grace: float = 0.0) -> None:
        await self.server.stop(grace)
        await self.bootstrap_server.stop(grace)
        if self._owns_controller:
            await self.controller.shutdown()

    def issue_agent_certificate(self, instance_id: str, ttl_seconds: int) -> IssuedCertificate:
        return self.ca.issue_client(f"node:{instance_id}", ttl_seconds)

    def _add_services(self) -> None:
        self._proto.pb2_grpc.add_EntityServiceServicer_to_server(_EntityService(self), self.server)
        self._proto.pb2_grpc.add_DagServiceServicer_to_server(_DagService(self), self.server)
        self._proto.pb2_grpc.add_NodeServiceServicer_to_server(_NodeService(self), self.server)
        self._proto.pb2_grpc.add_SystemServiceServicer_to_server(_SystemService(self, bootstrap=False), self.server)
        self._proto.pb2_grpc.add_SystemServiceServicer_to_server(_SystemService(self, bootstrap=True), self.bootstrap_server)


class _EntityService:
    def __init__(self, daemon: RigDaemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon._proto.pb2

    async def Get(self, request, context):
        await _identity(context)
        store, app = _entity_store(self.daemon.config_dir)
        return _entity_message(self.pb2, store, store.resolve(request.ref))

    async def List(self, request, context):
        await _identity(context)
        store, app = _entity_store(self.daemon.config_dir)
        if request.type.startswith("query:"):
            entities = _query(app, store, "human", None, request.type.removeprefix("query:"))
        else:
            entities = store.query(request.type or None)
        return self.pb2.EntityList(entities=[_entity_message(self.pb2, store, entity) for entity in entities])

    async def Create(self, request, context):
        await _identity(context)
        store, app = _entity_store(self.daemon.config_dir)
        attrs = json.loads(request.json or "{}")
        if not isinstance(attrs, dict):
            raise ValueError("entity json must be an object")
        return _entity_message(self.pb2, store, store.create(request.type, attrs))

    async def Update(self, request, context):
        identity = await _identity(context)
        store, app = _entity_store(self.daemon.config_dir)
        data = json.loads(request.json or "{}")
        if not isinstance(data, dict) or not isinstance(data.get("field"), str):
            raise ValueError("update json must contain field")
        entity = store.resolve(request.id)
        _check_write(identity, app, store, entity, data["field"])
        updated = entity.model_copy(update={"attributes": {**entity.attributes, data["field"]: data.get("value")}})
        return _entity_message(self.pb2, store, store.save(updated, _identity_permissions(identity, app.dags)))

    async def Delete(self, request, context):
        await _identity(context)
        store, app = _entity_store(self.daemon.config_dir)
        store.delete(store.resolve(request.ref).id)
        return self.pb2.DeleteResult(deleted=True)


class _DagService:
    def __init__(self, daemon: RigDaemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon._proto.pb2

    async def Trigger(self, request, context):
        await _identity(context)
        payload = json.loads(request.inputs_json) if request.inputs_json else None
        cycle_id = await self.daemon.controller.start_run("manual", request.name, payload)
        return self.pb2.DagRunRef(cycle_id=cycle_id)

    async def Status(self, request, context):
        await _identity(context)
        status = await self.daemon.controller.status(request.name)
        return self.pb2.DagStatus(name=request.name, json=json.dumps(status, ensure_ascii=False, default=str))

    async def Edit(self, request, context):
        await _identity(context)
        payload = json.loads(request.json or "{}")
        result = _edit_dag_config(self.daemon.config_dir, request.name, request.operation, payload)
        return self.pb2.DagStatus(name=request.name, json=json.dumps(result, ensure_ascii=False, default=str))


class _NodeService:
    def __init__(self, daemon: RigDaemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon._proto.pb2

    async def Status(self, request, context):
        await _identity(context)
        return self.pb2.NodeStatus(id=request.id, status=await self.daemon.controller.node_status(request.id))

    async def Stop(self, request, context):
        await _identity(context)
        dag_name = _dag_for_node(self.daemon.config_dir, request.id)
        if dag_name is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node '{request.id}' not found")
        cycle_id = await self.daemon.controller.stop_current(dag_name, node_id=request.id)
        return self.pb2.NodeStatus(id=request.id, status="stopped" if cycle_id is not None else "idle")

    async def Resume(self, request, context):
        await _identity(context)
        dag_name = _dag_for_node(self.daemon.config_dir, request.id)
        if dag_name is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node '{request.id}' not found")
        if not request.cycle_id:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "cycle_id is required")
        payload: dict[str, object] = {"resume_session": f"sandbox:{request.id}:{request.cycle_id}"}
        if request.prompt:
            payload["prompt"] = request.prompt
        cycle_id = await self.daemon.controller.resume_node(dag_name, request.cycle_id, request.id, payload)
        return self.pb2.DagRunRef(cycle_id=cycle_id)

    async def Output(self, request, context):
        await _identity(context)
        store, app = _entity_store(self.daemon.config_dir)
        expression = f"type=node-output AND node_id={request.id}"
        if request.cycle_id:
            expression = f"{expression} AND cycle_id={request.cycle_id}"
        payload = [_entity_payload(store, entity) for entity in _query(app, store, "human", None, expression)]
        return self.pb2.NodeOutputList(json=json.dumps(payload, ensure_ascii=False, default=str))


class _SystemService:
    def __init__(self, daemon: RigDaemon, bootstrap: bool) -> None:
        self.daemon = daemon
        self.bootstrap = bootstrap
        self.pb2 = daemon._proto.pb2

    async def Health(self, request, context):
        if not self.bootstrap:
            await _identity(context)
        return self.pb2.HealthResponse(ok=True)

    async def Reload(self, request, context):
        if self.bootstrap:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, "reload requires mTLS")
        await _identity(context)
        return self.pb2.ReloadResponse(reloaded=True)

    async def InitClient(self, request, context):
        common_name = request.common_name or "human:default"
        issued = self.daemon.ca.issue_client(common_name, 365 * 24 * 3600)
        return self.pb2.ClientInitResponse(
            client_cert_pem=issued.cert_pem,
            client_key_pem=issued.key_pem,
            ca_cert_pem=issued.ca_pem,
        )

    async def SubscribeEvents(self, request, context):
        if self.bootstrap:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, "event subscription requires mTLS")
        await _identity(context)
        async for event in event_bus.subscribe():
            if request.node_id and event.payload.get("node_id") != request.node_id:
                continue
            if request.dag_name and event.payload.get("dag_name") != request.dag_name:
                continue
            yield self.pb2.EventMessage(
                type=event.type,
                json=json.dumps(event.payload, ensure_ascii=False, default=str),
            )


def _entity_store(config_dir: Path) -> tuple[EntityStore, object]:
    app = load_app_config(config_dir)
    store = EntityStore(app.entities, app.entity_types, app.entity_relations, config_dir / "entities.yaml")
    return store, app


def _entity_message(pb2, store: EntityStore, entity: EntityConfig):
    return pb2.Entity(id=entity.id, type=entity.type, json=json.dumps(_entity_payload(store, entity), ensure_ascii=False, default=str))


async def _identity(context) -> str:
    if os.environ.get("RIG_ENV") == "dev":
        return "human:dev"
    for key, value in context.auth_context().items():
        if key == "x509_common_name" and value:
            return value[0].decode() if isinstance(value[0], bytes) else str(value[0])
    await context.abort(grpc.StatusCode.UNAUTHENTICATED, "client certificate required")


def _identity_permissions(identity: str, dags: dict[str, object]) -> dict[str, object] | None:
    if identity.startswith("human:") or identity.startswith("bff:"):
        return None
    if not identity.startswith("node:"):
        return {}
    node_id = identity.removeprefix("node:")
    for dag in dags.values():
        for instance in dag.nodes:
            if instance.id == node_id or instance.alias == node_id or instance.type == node_id:
                permissions = instance.config.get("entity_permissions")
                return permissions if isinstance(permissions, dict) else {}
    return {}


def _check_write(identity: str, app, store: EntityStore, entity: EntityConfig, field: str) -> None:
    permissions = _identity_permissions(identity, app.dags)
    if permissions is None:
        return
    overrides = permissions.get(entity.type) if isinstance(permissions, dict) else None
    allowed = can_write(field_permission(store.entity_types[entity.type], field, overrides if isinstance(overrides, dict) else None))
    if not allowed:
        raise PermissionError(f"{identity} cannot write {entity.type}.{field}")


def _edit_dag_config(config_dir: Path, dag_name: str, operation: str, payload: dict[str, object]) -> dict[str, object]:
    path = config_dir / "dags" / f"{dag_name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("dag config must be a mapping")
    attrs = data.get("attributes") if data.get("type") == "dag" and isinstance(data.get("attributes"), dict) else data
    nodes = attrs.setdefault("nodes", [])
    edges = attrs.setdefault("edges", [])
    if operation == "add-node":
        node_id = payload.get("id")
        node_type = payload.get("type")
        if not isinstance(node_id, str) or not node_id or not isinstance(node_type, str) or not node_type:
            raise ValueError("add-node requires id and type")
        config = payload.get("config")
        nodes.append({"id": node_id, "type": node_type, "config": config if isinstance(config, dict) else {}})
    elif operation == "add-edge":
        source = payload.get("from")
        target = payload.get("to")
        if not isinstance(source, str) or not source or not isinstance(target, str) or not target:
            raise ValueError("add-edge requires from and to")
        edge = {"from": source, "to": target}
        if payload.get("optional"):
            edge["optional"] = True
        edges.append(edge)
    elif operation == "remove-edge":
        source = payload.get("from")
        target = payload.get("to")
        attrs["edges"] = [edge for edge in edges if not (edge.get("from") == source and edge.get("to") == target)]
    else:
        raise ValueError(f"unknown dag edit operation: {operation}")
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"updated": True, "dag": dag_name}


def _dag_for_node(config_dir: Path, node_id: str) -> str | None:
    app = load_app_config(config_dir)
    for dag in app.dags.values():
        if any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes):
            return dag.name
    return None


def _bootstrap_address(address: str) -> str:
    host, sep, port = address.rpartition(":")
    if not sep:
        return address
    try:
        value = int(port)
        return f"{host}:{0 if value == 0 else value + 1}"
    except ValueError:
        return address


def resolve_data_dir(cli_arg: Path | str | None = None) -> Path:
    if cli_arg is not None:
        return Path(cli_arg)
    env_value = os.environ.get("RIG_DAEMON_DATA_DIR")
    if env_value:
        return Path(env_value)
    default = Path("/var/lib/rig")
    if _writable_dir(default):
        return default
    return Path.home() / ".local" / "share" / "rig"


def ensure_ca(data_dir: Path) -> CertificateAuthority:
    ca = CertificateAuthority(data_dir)
    ca.ensure()
    return ca


def ensure_server_cert(data_dir: Path, listen_address: str) -> None:
    CertificateAuthority(data_dir).issue_server(listen_address)


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            return True
    except OSError:
        return False


async def serve(
    address: str = "127.0.0.1:9090",
    data_dir: Path | None = None,
    config_dir: Path = Path("config"),
    bootstrap_address: str | None = None,
) -> None:
    daemon = RigDaemon(data_dir, address, config_dir, bootstrap_address=bootstrap_address)
    await daemon.start()
    try:
        await daemon.wait_closed()
    except asyncio.CancelledError:
        await daemon.stop()
        raise
