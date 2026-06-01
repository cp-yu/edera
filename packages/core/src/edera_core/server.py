from __future__ import annotations

import asyncio
import argparse
import json
import os
import socket
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import grpc

from edera_core.bootstrap import BootstrapResult
from edera_core.cert import CertificateAuthority, IssuedCertificate
from edera_core.config_service import _ConfigService
from edera_core.config.entities import EntityStore, can_read, can_write, field_permission
from edera_core.config.loader import CORE_ENTITY_TYPES, load_app_config, load_runtime_app_config
from edera_core.config.schema import AppConfig, DagConfig, EntitiesConfig, EntityConfig, MaterializedFieldConfig, entity_ref
from edera_core.events import event_bus
from edera_core.graph_service import _GraphService
from edera_core.event_service import _EventService
from edera_core.hot_reload import HotReloader
from edera_core.dag_controller import DagController, DagRunNotFoundError, RunAlreadyActiveError
from edera_core.proto import edera_pb2 as pb2, edera_pb2_grpc as pb2_grpc
from edera_core.query_service import _QueryService
from edera_core.service_common import (
    briefing_metadata,
    json_response,
    repair_task_dir,
    repair_task_payload,
    render_entity_display,
    source_map,
    write_repair_task,
)
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import (
    delete_core_entity,
    delete_ordinary_entity,
    edge_inputs_for_run,
    latest_briefing,
    save_core_entity,
    save_ordinary_entity,
    query_node_output_entities,
    save_node_output_entity,
    source_execution_logs,
    source_health_summary,
    source_recoveries,
    upsert_entity_type_record,
)
from edera_core.storage.materialization import (
    apply_materialization,
    deprecated_cleanup_ready,
    materialization_plan,
)


BOOTSTRAP_HOST = "127.0.0.1"
BOOTSTRAP_PORT_START = 9091
BOOTSTRAP_PORT_END = 9190


class Server:
    def __init__(
        self,
        data_dir: Path | None = None,
        address: str = "127.0.0.1:9090",
        config_dir: Path = Path("config"),
        controller: DagController | None = None,
    ) -> None:
        self.data_dir = resolve_data_dir(data_dir)
        self.address = address
        self.bootstrap_address = f"{BOOTSTRAP_HOST}:{BOOTSTRAP_PORT_START}"
        self.config_dir = config_dir
        self.ca = CertificateAuthority(self.data_dir)
        self.controller = controller or DagController(
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
        self.pb2 = pb2
        self.pb2_grpc = pb2_grpc
        self.bound_port: int | None = None
        self.bootstrap_bound_port: int | None = None
        self._hot_reload_task: asyncio.Task[None] | None = None
        self._add_services()

    async def start(self) -> None:
        self.ca.ensure()
        (self.data_dir / "sessions").mkdir(parents=True, exist_ok=True)
        if self._owns_controller:
            await self.controller.start(run_startup=False)
        if os.environ.get("EDERA_DEV") == "1":
            self.bound_port = self.server.add_insecure_port(self.address)
        else:
            ensure_server_cert(self.data_dir, self.address)
            server_cert = self.ca.issue_server(_server_cert_address(self.address))
            credentials = grpc.ssl_server_credentials(
                [(server_cert.key_path.read_bytes(), server_cert.cert_path.read_bytes())],
                root_certificates=self.ca.ca_cert_pem(),
                require_client_auth=True,
            )
            self.bound_port = self.server.add_secure_port(self.address, credentials)
            self.bootstrap_bound_port = self._add_bootstrap_port()
            self.bootstrap_address = f"{BOOTSTRAP_HOST}:{self.bootstrap_bound_port}"
            write_bootstrap_status(self.data_dir, BOOTSTRAP_HOST, self.bootstrap_bound_port)
        await self.server.start()
        if self.bootstrap_bound_port is not None:
            await self.bootstrap_server.start()
        self._start_hot_reload()

    async def wait_closed(self) -> None:
        await self.server.wait_for_termination()

    async def stop(self, grace: float = 0.0) -> None:
        await self._stop_hot_reload()
        await self.server.stop(grace)
        await self.bootstrap_server.stop(grace)
        if self._owns_controller:
            await self.controller.shutdown()

    def issue_agent_certificate(self, instance_id: str, ttl_seconds: int) -> IssuedCertificate:
        return self.ca.issue_client(f"node:{instance_id}", ttl_seconds)

    def _start_hot_reload(self) -> None:
        extensions_dirs = getattr(self.controller, "extensions_dirs", [Path("extensions")])
        reloader = HotReloader(
            self.config_dir,
            list(extensions_dirs),
            self._reload_config,
            emit=self._emit_config_changed,
            config_loader=self._load_runtime_config,
        )
        self._hot_reload_task = asyncio.create_task(reloader.watch())

    async def _stop_hot_reload(self) -> None:
        if self._hot_reload_task is None:
            return
        self._hot_reload_task.cancel()
        try:
            await self._hot_reload_task
        except asyncio.CancelledError:
            pass
        self._hot_reload_task = None

    async def _reload_config(self, config: AppConfig, bootstrap: BootstrapResult) -> None:
        await self.controller.install_snapshot(config, bootstrap)

    async def _load_runtime_config(self) -> AppConfig:
        if self.controller.engine is None:
            raise RuntimeError("DAG controller has not been started")
        return await load_runtime_app_config(self.config_dir, self.controller.engine)

    async def _emit_config_changed(self, event: str) -> object:
        return await self.controller.emit(event, source="hot-reload")

    def _add_services(self) -> None:
        self.pb2_grpc.add_EntityServiceServicer_to_server(_EntityService(self), self.server)
        self.pb2_grpc.add_DagServiceServicer_to_server(_DagService(self), self.server)
        self.pb2_grpc.add_NodeServiceServicer_to_server(_NodeService(self), self.server)
        self.pb2_grpc.add_SystemServiceServicer_to_server(_SystemService(self, bootstrap=False), self.server)
        self.pb2_grpc.add_GraphServiceServicer_to_server(_GraphService(self), self.server)
        self.pb2_grpc.add_ConfigServiceServicer_to_server(_ConfigService(self), self.server)
        self.pb2_grpc.add_QueryServiceServicer_to_server(_QueryService(self), self.server)
        self.pb2_grpc.add_EventServiceServicer_to_server(_EventService(self), self.server)
        self.pb2_grpc.add_SystemServiceServicer_to_server(_SystemService(self, bootstrap=True), self.bootstrap_server)

    def _add_bootstrap_port(self) -> int:
        for port in range(BOOTSTRAP_PORT_START, BOOTSTRAP_PORT_END + 1):
            if not _tcp_port_available(BOOTSTRAP_HOST, port):
                continue
            bound = self.bootstrap_server.add_insecure_port(f"{BOOTSTRAP_HOST}:{port}")
            if bound == port:
                return port
        raise RuntimeError(f"no available bootstrap port in {BOOTSTRAP_HOST}:{BOOTSTRAP_PORT_START}-{BOOTSTRAP_PORT_END}")


class _EntityService:
    def __init__(self, daemon: Server) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def Get(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        return _entity_message(self.pb2, store, store.resolve(request.ref))

    async def List(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        if request.type == "entity_type":
            return self.pb2.EntityList(entities=[_entity_type_message(self.pb2, name, entity_type) for name, entity_type in app.entity_types.items()])
        entities = store.query(request.type or None)
        return self.pb2.EntityList(entities=[_entity_message(self.pb2, store, entity) for entity in entities])

    async def Query(self, request, context):
        identity = request.identity or await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        try:
            entities = await _query(app, store, identity, _identity_permissions(identity, app.dags), request.expression)
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return self.pb2.EntityList(entities=[_entity_message(self.pb2, store, entity) for entity in entities])

    async def Create(self, request, context):
        await _identity(context)
        if _database_entity_available(self.daemon, request.type):
            store, app = _runtime_entity_store(self.daemon)
            attrs = json.loads(request.json or "{}")
            if not isinstance(attrs, dict):
                raise ValueError("entity json must be an object")
            created = EntityConfig(id=request.id or uuid4().hex, type=request.type, attributes=attrs)
            _validate_entity_for_store(store, created, replace=False)
            async with self.daemon.controller._factory()() as session:
                saved = await _save_database_entity(session, created, store.entity_types[request.type])
                await session.commit()
            await self._refresh_runtime_snapshot()
            store, app = _runtime_entity_store(self.daemon)
            await self._emit_entity_changed(store, saved)
            return _entity_message(self.pb2, store, saved)
        store, app = _entity_store(self.daemon.config_dir)
        attrs = json.loads(request.json or "{}")
        if not isinstance(attrs, dict):
            raise ValueError("entity json must be an object")
        created = store.create(request.type, attrs, request.id or None)
        await self._emit_entity_changed(store, created)
        return _entity_message(self.pb2, store, created)

    async def Update(self, request, context):
        identity = await _identity(context)
        store, app = _runtime_entity_store(self.daemon) if _controller_started(self.daemon) else _entity_store(self.daemon.config_dir)
        data = json.loads(request.json or "{}")
        if not isinstance(data, dict) or not isinstance(data.get("field"), str):
            raise ValueError("update json must contain field")
        entity = store.resolve(request.id)
        try:
            _check_write(identity, app, store, entity, data["field"])
        except PermissionError as exc:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
        updated = entity.model_copy(update={"attributes": {**entity.attributes, data["field"]: data.get("value")}})
        if _database_entity_available(self.daemon, entity.type):
            _validate_entity_for_store(store, updated, replace=True)
            async with self.daemon.controller._factory()() as session:
                saved = await _save_database_entity(session, updated, store.entity_types[entity.type])
                await session.commit()
            await self._refresh_runtime_snapshot()
            store, app = _runtime_entity_store(self.daemon)
        else:
            saved = store.save(updated, _identity_permissions(identity, app.dags))
        await self._emit_entity_changed(store, saved)
        return _entity_message(self.pb2, store, saved)

    async def Delete(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon) if _controller_started(self.daemon) else _entity_store(self.daemon.config_dir)
        entity = store.resolve(request.ref)
        if _database_entity_available(self.daemon, entity.type):
            async with self.daemon.controller._factory()() as session:
                if entity.type in CORE_ENTITY_TYPES:
                    deleted = await delete_core_entity(session, entity.id, store.entity_types)
                else:
                    deleted = await delete_ordinary_entity(session, entity.id, store.entity_types)
                await session.commit()
            if not deleted:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"Entity not found: {request.ref}")
            await self._refresh_runtime_snapshot()
            store, app = _runtime_entity_store(self.daemon)
        else:
            store.delete(entity.id)
        await self._emit_entity_changed(store, entity)
        return self.pb2.DeleteResult(deleted=True)

    async def Materialize(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        payload = json.loads(request.json or "{}")
        if not isinstance(payload, dict):
            raise ValueError("materialize request must be an object")
        operation = str(payload.get("operation") or "")
        type_name = str(payload.get("entity_type") or "")
        if not type_name or type_name not in store.entity_types:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"unknown entity type: {type_name}")
        entity_type = store.entity_types[type_name]
        if type_name in CORE_ENTITY_TYPES or entity_type.storage_tier != "database":
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"entity type is not ordinary database-backed: {type_name}")
        field = str(payload.get("field") or "")
        field_type = str(payload["type"]) if payload.get("type") is not None else None
        index = bool(payload["index"]) if "index" in payload else None
        async with self.daemon.controller._factory()() as session:
            if operation == "inspect":
                result = {
                    "entity_type": type_name,
                    "table_name": entity_type.table_name,
                    "materialized_fields": {
                        name: config.model_dump(mode="json")
                        for name, config in entity_type.materialized_fields.items()
                    },
                    "deprecated_fields": list(entity_type.deprecated_fields),
                }
            elif operation == "plan":
                if not field:
                    raise ValueError("field is required")
                result = (await materialization_plan(session, type_name, entity_type, field, field_type, index)).to_dict()
            elif operation == "apply":
                if not field:
                    raise ValueError("field is required")
                plan = await apply_materialization(session, type_name, entity_type, field, field_type, index)
                materialized_fields = dict(entity_type.materialized_fields)
                materialized_fields[field] = MaterializedFieldConfig(type=plan.column_type, index=plan.index)
                updated = entity_type.model_copy(update={"materialized_fields": materialized_fields})
                await upsert_entity_type_record(session, type_name, updated)
                await session.commit()
                await self._refresh_runtime_snapshot()
                result = {**plan.to_dict(), "applied": True}
            elif operation == "cleanup-ready":
                if not field:
                    raise ValueError("field is required")
                result = {
                    "entity_type": type_name,
                    "field": field,
                    "cleanup_ready": await deprecated_cleanup_ready(session, type_name, entity_type, field),
                }
            else:
                raise ValueError(f"unknown materialize operation: {operation}")
        return json_response(self.pb2, result)

    async def _refresh_runtime_snapshot(self) -> None:
        if not _controller_started(self.daemon) or self.daemon.controller.engine is None:
            return
        config = await load_runtime_app_config(self.daemon.config_dir, self.daemon.controller.engine)
        await self.daemon.controller.install_snapshot(config, self.daemon.controller.runtime_snapshot().bootstrap)

    async def _emit_entity_changed(self, store: EntityStore, entity: EntityConfig) -> None:
        await self.daemon.controller.emit(
            f"event:entity-changed:{entity_ref(entity, store.entity_types)}",
            source="entity-service",
        )


class _DagService:
    def __init__(self, daemon: Server) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def Run(self, request, context):
        await _identity(context)
        payload = json.loads(request.inputs_json) if request.inputs_json else None
        try:
            run_id = await self.daemon.controller.start_run("manual", request.name, payload)
        except RunAlreadyActiveError as exc:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, exc.run_id)
        return self.pb2.DagRunRef(run_id=run_id)

    async def Status(self, request, context):
        await _identity(context)
        status = await self.daemon.controller.status(request.name)
        return self.pb2.DagStatus(name=request.name, json=json.dumps(status, ensure_ascii=False, default=str))

    async def Edit(self, request, context):
        await _identity(context)
        payload = json.loads(request.json or "{}")
        try:
            result = await _edit_runtime_dag(self.daemon, request.name, request.operation, payload)
        except KeyError:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.name}' not found")
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return self.pb2.DagStatus(name=request.name, json=json.dumps(result, ensure_ascii=False, default=str))

    async def Stop(self, request, context):
        await _identity(context)
        if request.dag_name not in self.daemon.controller.runtime_snapshot().config.dags:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.dag_name}' not found")
        run_id = await self.daemon.controller.stop_current(request.dag_name, force=request.force)
        return json_response(self.pb2, {"stopped": run_id is not None, "run_id": run_id})

    async def Retry(self, request, context):
        await _identity(context)
        if request.dag_name not in self.daemon.controller.runtime_snapshot().config.dags:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.dag_name}' not found")
        if not request.node_ids:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "node_ids is required")
        payload = json.loads(request.payload_json) if request.payload_json else None
        try:
            result = await self.daemon.controller.retry_node(
                request.dag_name,
                request.run_id or None,
                list(request.node_ids),
                request.mode or "single",
                payload,
            )
        except RunAlreadyActiveError as exc:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, exc.run_id)
        except DagRunNotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(
            self.pb2,
            {
                "run_id": result.run_id,
                "retry_of": result.retry_of,
                "node_ids": result.node_ids,
                "mode": result.mode,
                "retry_nodes": result.retry_nodes,
            },
        )


class _NodeService:
    def __init__(self, daemon: Server) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def Status(self, request, context):
        await _identity(context)
        return self.pb2.NodeStatus(id=request.id, status=await self.daemon.controller.node_status(request.id))

    async def Stop(self, request, context):
        await _identity(context)
        dag_name = _dag_for_node(self.daemon.controller.runtime_snapshot().config, request.id)
        if dag_name is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node '{request.id}' not found")
        run_id = await self.daemon.controller.stop_current(dag_name, node_id=request.id)
        return self.pb2.NodeStatus(id=request.id, status="stopped" if run_id is not None else "idle")

    async def Resume(self, request, context):
        await _identity(context)
        dag_name = _dag_for_node(self.daemon.controller.runtime_snapshot().config, request.id)
        if dag_name is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node '{request.id}' not found")
        if not request.run_id:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "run_id is required")
        payload: dict[str, object] = {"resume_session": f"sandbox:{request.id}:{request.run_id}"}
        if request.prompt:
            payload["prompt"] = request.prompt
        run_id = await self.daemon.controller.resume_node(dag_name, request.run_id, request.id, payload)
        return self.pb2.DagRunRef(run_id=run_id)

    async def Output(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        expression = f"type=node-output AND node_id={request.id}"
        if request.run_id:
            expression = f"{expression} AND run_id={request.run_id}"
        payload = [_entity_payload(store, entity) for entity in await _query(app, store, "human", None, expression)]
        return self.pb2.NodeOutputList(json=json.dumps(payload, ensure_ascii=False, default=str))


class _SystemService:
    def __init__(self, daemon: Server, bootstrap: bool) -> None:
        self.daemon = daemon
        self.bootstrap = bootstrap
        self.pb2 = daemon.pb2

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
        ttl_seconds = 7 * 24 * 3600 if common_name == "bff:web-console" else 365 * 24 * 3600
        issued = self.daemon.ca.issue_client(common_name, ttl_seconds)
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

    async def PauseScheduler(self, request, context):
        await _identity(context)
        self.daemon.controller.pause_scheduler()
        return json_response(self.pb2, await self.daemon.controller.status())

    async def ResumeScheduler(self, request, context):
        await _identity(context)
        self.daemon.controller.resume_scheduler()
        return json_response(self.pb2, await self.daemon.controller.status())

    async def SchedulerStatus(self, request, context):
        await _identity(context)
        return json_response(self.pb2, await self.daemon.controller.status())

    async def CreateRepairTask(self, request, context):
        await _identity(context)
        source = source_map(self.daemon.controller.runtime_snapshot().entity_store).get(request.name)
        if source is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "source not found")
        async with self.daemon.controller._factory()() as session:
            health = await source_health_summary(session, [request.name])
            logs = await source_execution_logs(session, request.name, 1)
            briefing = await latest_briefing(session)
            if not health or not health[0].get("escalated") or briefing is None:
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "source is not escalated")
            task = repair_task_payload(
                repair_task_dir(self.daemon.config_dir),
                source.model_dump(mode="json"),
                health[0],
                logs[0] if logs else {},
            )
            write_repair_task(task)
            metadata = dict(briefing_metadata(briefing))
            repair_tasks = dict(metadata.get("repair_tasks", {}))
            repair_tasks[request.name] = {"task_id": task["task_id"], "task_path": task["task_path"], "created_at": task["created_at"]}
            metadata["repair_tasks"] = repair_tasks
            payload = briefing.attributes.get("payload")
            attributes = dict(payload) if isinstance(payload, dict) else dict(briefing.attributes)
            attributes["metadata"] = metadata
            await save_node_output_entity(session, briefing.model_copy(update={"attributes": attributes}))
            await session.commit()
        return json_response(
            self.pb2,
            {
                "task_id": task["task_id"],
                "task_path": task["task_path"],
                "source_name": request.name,
                "created_at": task["created_at"],
            },
        )


def _entity_store(config_dir: Path) -> tuple[EntityStore, object]:
    app = load_app_config(config_dir)
    store = EntityStore(app.entities, app.entity_types, app.entity_relations, config_dir / "entities.yaml")
    return store, app


def _runtime_entity_store(daemon: Server) -> tuple[EntityStore, AppConfig]:
    snapshot = daemon.controller.runtime_snapshot()
    return snapshot.entity_store, snapshot.config


def _controller_started(daemon: Server) -> bool:
    return getattr(daemon.controller, "factory", None) is not None


def _database_entity_available(daemon: Server, entity_type: str) -> bool:
    if not _controller_started(daemon):
        return False
    _, app = _runtime_entity_store(daemon)
    config = app.entity_types.get(entity_type)
    return config is not None and config.storage_tier == "database"


async def _save_database_entity(session, entity: EntityConfig, entity_type) -> EntityConfig:
    if entity.type in CORE_ENTITY_TYPES:
        return await save_core_entity(session, entity)
    return await save_ordinary_entity(session, entity, entity_type)


def _validate_entity_for_store(store: EntityStore, entity: EntityConfig, *, replace: bool) -> None:
    entities = [
        current
        for current in store.entities.entities
        if not replace or current.id != entity.id
    ]
    checker = EntityStore(
        EntitiesConfig(entities=[*entities, entity]),
        store.entity_types,
        store.relations,
        None,
    )
    checker._validate()


def _entity_message(pb2, store: EntityStore, entity: EntityConfig):
    return pb2.Entity(id=entity.id, type=entity.type, json=json.dumps(_entity_payload(store, entity), ensure_ascii=False, default=str))


def _entity_type_message(pb2, name: str, entity_type):
    payload = entity_type.model_dump(mode="json", by_alias=True)
    payload["name"] = name
    return pb2.Entity(
        id=name,
        type="entity_type",
        json=json.dumps({"ref": f"entity_type:{name}", "id": name, "type": "entity_type", "attributes": payload}, ensure_ascii=False, default=str),
    )


async def _identity(context) -> str:
    if os.environ.get("EDERA_DEV") == "1":
        return _metadata_identity(context) or "human:dev"
    metadata_identity = _metadata_identity(context)
    if metadata_identity:
        return metadata_identity
    for key, value in context.auth_context().items():
        if key == "x509_common_name" and value:
            return value[0].decode() if isinstance(value[0], bytes) else str(value[0])
    await context.abort(grpc.StatusCode.UNAUTHENTICATED, "client certificate required")


def _metadata_identity(context) -> str | None:
    for key, value in context.invocation_metadata():
        if key == "x-edera-identity" and value:
            return str(value)
    return None


def _identity_permissions(identity: str, dags: dict[str, object]) -> dict[str, object] | None:
    if identity == "human" or identity.startswith("human:") or identity.startswith("bff:"):
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


async def _query(
    app: AppConfig,
    store: EntityStore,
    identity: str,
    permissions: dict[str, Any] | None,
    expression: str,
) -> list[EntityConfig]:
    parts = [part.strip() for part in expression.split("AND") if part.strip()]
    if not parts:
        raise ValueError(_supported_query_message())
    relation_filters = _relation_filters(parts)
    if relation_filters is not None:
        return _readable_entities(identity, store, permissions, _query_relations(store, relation_filters))
    runtime_filters = _runtime_filters(parts)
    if runtime_filters is not None:
        return _readable_entities(identity, store, permissions, await _query_runtime_facts(app, runtime_filters))
    node_output_filters = _node_output_filters(parts)
    if node_output_filters is not None:
        return _readable_entities(identity, store, permissions, await _query_node_outputs(app, node_output_filters))
    result = store.query()
    for part in parts:
        if part.startswith("type="):
            wanted = part.removeprefix("type=").strip()
            result = [entity for entity in result if entity.type == wanted]
        elif ">" in part:
            field, raw = [item.strip() for item in part.split(">", 1)]
            result = [entity for entity in result if float(entity.attributes.get(field, 0)) > float(raw)]
        elif "=" in part:
            field, raw = [item.strip() for item in part.split("=", 1)]
            result = [entity for entity in result if str(entity.attributes.get(field)) == raw]
        else:
            raise ValueError(_supported_query_message())
    return _readable_entities(identity, store, permissions, result)


def _readable_entities(
    identity: str,
    store: EntityStore,
    permissions: dict[str, Any] | None,
    entities: list[EntityConfig],
) -> list[EntityConfig]:
    return [_readable_entity(identity, store, permissions, entity) for entity in entities]


def _readable_entity(
    identity: str,
    store: EntityStore,
    permissions: dict[str, Any] | None,
    entity: EntityConfig,
) -> EntityConfig:
    if permissions is None:
        return entity
    overrides = permissions.get(entity.type) if isinstance(permissions, dict) else None
    entity_type = store.entity_types.get(entity.type)
    if entity_type is None:
        return entity
    filtered = {
        field: value
        for field, value in entity.attributes.items()
        if can_read(field_permission(entity_type, field, overrides if isinstance(overrides, dict) else None))
    }
    return entity.model_copy(update={"attributes": filtered})


def _relation_filters(parts: list[str]) -> dict[str, str] | None:
    is_relation = False
    filters: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = [item.strip() for item in part.split("=", 1)]
        if key == "type" and value == "relation":
            is_relation = True
        elif key == "relation_type":
            filters["type"] = value
        elif key in {"from", "to"}:
            filters[key] = value
    return filters if is_relation else None


def _query_relations(store: EntityStore, filters: dict[str, str]) -> list[EntityConfig]:
    entities: list[EntityConfig] = []
    for relation in store.relations.relations:
        if filters.get("type") and relation.type != filters["type"]:
            continue
        refs = relation.entities
        if filters.get("from") and filters["from"] not in refs:
            continue
        if filters.get("to") and filters["to"] not in refs:
            continue
        entities.append(
            EntityConfig(
                id=relation.id,
                type="relation",
                attributes={
                    "from": refs[0] if refs else "",
                    "to": refs[1] if len(refs) > 1 else "",
                    "relation_type": relation.type,
                    "entities": refs,
                    "metadata": relation.metadata,
                },
            )
        )
    return entities


def _node_output_filters(parts: list[str]) -> dict[str, str] | None:
    filters: dict[str, str] = {}
    for part in parts:
        if part.startswith("node_output:"):
            filters["node_id"] = part.removeprefix("node_output:").strip()
            continue
        if "=" not in part:
            continue
        key, value = [item.strip() for item in part.split("=", 1)]
        if key == "type":
            filters["type"] = value
        elif key in {"run_id", "node_id"}:
            filters[key] = value
    return filters if filters.get("type") == "node-output" or "node_id" in filters or "run_id" in filters else None


def _runtime_filters(parts: list[str]) -> dict[str, str] | None:
    filters: dict[str, str] = {}
    for part in parts:
        if part.startswith("runtime:"):
            filters["type"] = part.removeprefix("runtime:").strip()
            continue
        if "=" not in part:
            continue
        key, value = [item.strip() for item in part.split("=", 1)]
        if key in {"type", "run_id", "source_name"}:
            filters[key] = value
    return filters if filters.get("type") in {"runtime.edge-input", "runtime.source-recovery"} else None


async def _query_node_outputs(app: AppConfig, filters: dict[str, str]) -> list[EntityConfig]:
    engine = create_engine(app.system.database_url)
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            return await query_node_output_entities(
                session,
                None if filters.get("type") == "node-output" else filters.get("type"),
                filters.get("run_id"),
                filters.get("node_id"),
                None,
                100,
            )
    finally:
        await engine.dispose()


async def _query_runtime_facts(app: AppConfig, filters: dict[str, str]) -> list[EntityConfig]:
    engine = create_engine(app.system.database_url)
    try:
        await init_db(engine)
        factory = session_factory(engine)
        async with factory() as session:
            if filters["type"] == "runtime.edge-input":
                run_id = filters.get("run_id")
                if run_id is None:
                    return []
                return [_edge_input_entity(item) for item in await edge_inputs_for_run(session, run_id)]
            return [
                _source_recovery_entity(item)
                for item in await source_recoveries(session, filters.get("source_name"), 100)
            ]
    finally:
        await engine.dispose()


def _edge_input_entity(item) -> EntityConfig:
    return EntityConfig(
        id=f"{item.run_id}:{item.from_node_id}->{item.to_node_id}",
        type="runtime.edge-input",
        attributes={
            "run_id": item.run_id,
            "from_node_id": item.from_node_id,
            "to_node_id": item.to_node_id,
            "edge_optional": item.edge_optional,
            "status": item.status,
            "has_payload": item.has_payload,
            "error_summary": item.error_summary,
            "created_at": item.created_at,
        },
    )


def _source_recovery_entity(item) -> EntityConfig:
    return EntityConfig(
        id=f"{item.run_id}:{item.node_id}:{item.source_name}",
        type="runtime.source-recovery",
        attributes={
            "run_id": item.run_id,
            "node_id": item.node_id,
            "source_name": item.source_name,
            "recovery_status": item.recovery_status,
            "attempt_count": item.attempt_count,
            "recoverable_reason": item.recoverable_reason,
            "latest_failure_reason": item.latest_failure_reason,
            "escalated": item.escalated,
            "escalation_reason": item.escalation_reason,
            "created_at": item.created_at,
        },
    )


def _entity_payload(store: EntityStore, entity: EntityConfig) -> dict[str, object]:
    try:
        ref = entity_ref(entity, store.entity_types)
    except (KeyError, ValueError):
        ref = entity.id
    entity_type = store.entity_types.get(entity.type)
    display = render_entity_display(entity, entity_type) if entity_type else ref
    return {"ref": ref, "display": display, **entity.model_dump(mode="json")}


def _supported_query_message() -> str:
    return (
        "unsupported query expression; supported fields: type, relation_type, from, to, "
        "node_id, run_id, runtime.edge-input, runtime.source-recovery"
    )


async def _edit_runtime_dag(daemon: Server, dag_name: str, operation: str, payload: dict[str, object]) -> dict[str, object]:
    dag = daemon.controller.runtime_snapshot().config.dags[dag_name]
    attrs = dag.model_dump(mode="json", by_alias=True)
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
    dag_config = DagConfig.model_validate(attrs)
    async with daemon.controller._factory()() as session:
        await save_core_entity(session, EntityConfig(id=dag_name, type="dag", attributes=dag_config.model_dump(mode="json", by_alias=True)))
        await session.commit()
    if daemon.controller.engine is None:
        raise RuntimeError("DAG controller has not been started")
    config = await load_runtime_app_config(daemon.config_dir, daemon.controller.engine)
    await daemon.controller.install_snapshot(config, daemon.controller.runtime_snapshot().bootstrap)
    return {"updated": True, "dag": dag_name}


def _dag_for_node(app: AppConfig, node_id: str) -> str | None:
    for dag in app.dags.values():
        if any(instance.id == node_id or instance.alias == node_id for instance in dag.nodes):
            return dag.name
    return None


def resolve_data_dir(cli_arg: Path | str | None = None) -> Path:
    if cli_arg is not None:
        return Path(cli_arg)
    env_value = os.environ.get("EDERA_DATA_DIR")
    if env_value:
        return Path(env_value)
    return Path.home() / ".local" / "share" / "edera-server"


def ensure_ca(data_dir: Path) -> CertificateAuthority:
    ca = CertificateAuthority(data_dir)
    ca.ensure()
    return ca


def ensure_server_cert(data_dir: Path, listen_address: str) -> None:
    CertificateAuthority(data_dir).issue_server(_server_cert_address(listen_address))


def write_bootstrap_status(data_dir: Path, host: str, port: int) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "bootstrap.json").write_text(
        json.dumps({"host": host, "port": port}, ensure_ascii=False),
        encoding="utf-8",
    )


def _tcp_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _server_cert_address(listen_address: str) -> str:
    public_host = os.environ.get("EDERA_SERVER_PUBLIC_HOST")
    if not public_host:
        return listen_address
    _, sep, port = listen_address.rpartition(":")
    return f"{public_host}:{port}" if sep else public_host


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            return True
    except OSError:
        return False


async def serve(
    address: str = "0.0.0.0:9090",
    data_dir: Path | None = None,
    config_dir: Path = Path("config"),
) -> None:
    daemon = Server(data_dir, address, config_dir)
    await daemon.start()
    try:
        await daemon.wait_closed()
    except asyncio.CancelledError:
        await daemon.stop()
        raise


def main() -> None:
    parser = argparse.ArgumentParser(prog="edera-server")
    parser.add_argument("--bind", default=os.environ.get("EDERA_SERVER_BIND", "0.0.0.0:9090"))
    parser.add_argument("--data-dir", default=os.environ.get("EDERA_DATA_DIR"))
    parser.add_argument("--config-dir", default=os.environ.get("EDERA_CONFIG_DIR"))
    args = parser.parse_args()
    if not args.config_dir:
        parser.error("--config-dir or EDERA_CONFIG_DIR is required")
    asyncio.run(
        serve(
            args.bind,
            Path(args.data_dir) if args.data_dir else None,
            Path(args.config_dir),
        )
    )


if __name__ == "__main__":
    main()
