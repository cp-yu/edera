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
import yaml

from edera_core.bootstrap import BootstrapResult
from edera_core.cert import CertificateAuthority, IssuedCertificate
from edera_core.config_service import _ConfigService
from edera_core.config.entities import EntityStore, can_read, can_write, field_permission
from edera_core.config.loader import CORE_ENTITY_TYPES, _load_runtime_base_config, load_app_config
from edera_core.config.schema import AppConfig, DagConfig, EntitiesConfig, EntityConfig, MaterializedFieldConfig, entity_ref
from edera_core.events import event_bus
from edera_core.graph_service import _GraphService
from edera_core.grpc_extension_service import _ExtensionService
from edera_core.event_service import _EventService
from edera_core.hot_reload import HotReloader
from edera_core.dag.loader import validate_sub_dag_nesting
from edera_core.dag_controller import DagController, DagRunNotFoundError, RunAlreadyActiveError
from edera_core.errors import ConfigError, DagError
from edera_core.proto import edera_pb2 as pb2, edera_pb2_grpc as pb2_grpc
from edera_core.query_service import _QueryService
from edera_core.service_common import (
    briefing_metadata,
    json_response,
    repair_task_dir,
    repair_task_payload,
    render_entity_display,
    source_map_from_store,
    write_repair_task,
)
from edera_core.storage import create_engine, init_db, session_factory
from edera_core.storage.repository import (
    delete_core_entity,
    delete_ordinary_entity,
    edge_inputs_for_run,
    get_dag_config,
    get_dag_entity,
    get_node_config,
    latest_briefing,
    list_dag_configs,
    list_entity_type_configs,
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
            bootstrap_loader=self.controller.load_bootstrap,
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
        return _load_runtime_base_config(self.config_dir)

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
        self.pb2_grpc.add_ExtensionServiceServicer_to_server(_ExtensionService(self), self.server)
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
        if _controller_started(self.daemon):
            async with self.daemon.controller._factory()() as session:
                result = await store.query_one_async(request.ref, session=session)
            return _entity_message(self.pb2, store, result.entity)
        return _entity_message(self.pb2, store, store.resolve(request.ref))

    async def List(self, request, context):
        await _identity(context)
        runtime_store, app = _runtime_entity_store(self.daemon)
        if request.type == "entity_type":
            if _controller_started(self.daemon):
                async with self.daemon.controller._factory()() as session:
                    entity_types = await list_entity_type_configs(session)
                return self.pb2.EntityList(entities=[_entity_type_message(self.pb2, name, entity_type) for name, entity_type in entity_types.items()])
            return self.pb2.EntityList(entities=[_entity_type_message(self.pb2, name, entity_type) for name, entity_type in app.entity_types.items()])
        store = _active_run_entity_store(self.daemon, request.dag_run_id or None) or runtime_store
        filters = _filters_from_json(request.filters_json)
        if _controller_started(self.daemon):
            async with self.daemon.controller._factory()() as session:
                if request.type == "relation" and _has_relation_repository_filter(filters):
                    from edera_core.storage.repository import list_relations

                    relation_filters = _relation_repository_filters(filters)
                    relations = await list_relations(session, **relation_filters)
                    entities = _filter_entities([_relation_entity(relation) for relation in relations], filters)
                    return self.pb2.EntityList(entities=[_entity_message(self.pb2, store, entity) for entity in entities])
                results = await store.query_async(request.type or None, dag_run_id=request.dag_run_id or None, session=session)
        else:
            results = store.query_results(request.type or None, dag_run_id=request.dag_run_id or None)
        entities = _filter_entities([result.entity for result in results], filters)
        return self.pb2.EntityList(entities=[_entity_message(self.pb2, store, entity) for entity in entities])

    async def Query(self, request, context):
        identity = request.identity or await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        try:
            if _controller_started(self.daemon):
                async with self.daemon.controller._factory()() as session:
                    permissions = await _identity_permissions_from_db(session, identity)
                    entities = await _query(
                        app,
                        store,
                        identity,
                        permissions,
                        request.expression,
                        session,
                    )
            else:
                entities = await _query(app, store, identity, _default_identity_permissions(identity), request.expression)
        except ValueError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return self.pb2.EntityList(entities=[_entity_message(self.pb2, store, entity) for entity in entities])

    async def Create(self, request, context):
        await _identity(context)
        if request.type == "relation":
            store, app = _runtime_entity_store(self.daemon)
            attrs = json.loads(request.json or "{}")
            if not isinstance(attrs, dict):
                raise ValueError("entity json must be an object")
            async with self.daemon.controller._factory()() as session:
                from edera_core.storage.repository import create_relation

                relation = await create_relation(
                    session,
                    str(attrs["from_entity_id"]),
                    str(attrs["to_entity_id"]),
                    str(attrs["relation_type"]),
                    dict(attrs.get("metadata") or {}),
                    store.entity_types,
                )
                await session.commit()
            relation_entity = _relation_entity(relation)
            await self._emit_config_changed()
            return _entity_message(self.pb2, store, relation_entity)
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
            await self._after_database_entity_write(saved.type)
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
        async def _save_updated(entity: EntityConfig, session=None, permissions=None) -> EntityConfig:
            try:
                _check_write(identity, store, entity, data["field"], permissions)
            except PermissionError as exc:
                await context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
            if entity.type == "relation":
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "relation update is not supported")
            updated = entity.model_copy(update={"attributes": {**entity.attributes, data["field"]: data.get("value")}})
            if not _database_entity_available(self.daemon, entity.type):
                return store.save(updated, permissions)
            if session is None:
                raise ConfigError("database session is required")
            _validate_entity_for_store(store, updated, replace=True)
            return await _save_database_entity(session, updated, store.entity_types[entity.type])

        if _controller_started(self.daemon):
            async with self.daemon.controller._factory()() as session:
                permissions = await _identity_permissions_from_db(session, identity)
                entity = await _resolve_entity_for_mutation(store, request.id, session)
                saved = await _save_updated(entity, session, permissions)
                await session.commit()
            await self._after_database_entity_write(saved.type)
        else:
            saved = await _save_updated(store.resolve(request.id), permissions=_default_identity_permissions(identity))
        await self._emit_entity_changed(store, saved)
        return _entity_message(self.pb2, store, saved)

    async def Delete(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon) if _controller_started(self.daemon) else _entity_store(self.daemon.config_dir)
        if _controller_started(self.daemon):
            async with self.daemon.controller._factory()() as session:
                entity = await _resolve_entity_for_mutation(store, request.ref, session)
                if entity.type == "relation":
                    from edera_core.storage.repository import delete_relation

                    deleted = await delete_relation(session, entity.id)
                elif _database_entity_available(self.daemon, entity.type):
                    from edera_core.storage.repository import force_delete_entity_relations

                    refs = _entity_relation_refs(entity, store)
                    if request.force:
                        await force_delete_entity_relations(session, refs)
                    if entity.type in CORE_ENTITY_TYPES:
                        deleted = await delete_core_entity(session, entity.id, store.entity_types)
                    else:
                        deleted = await delete_ordinary_entity(session, entity.id, store.entity_types)
                else:
                    store.delete(entity.id)
                    deleted = True
                await session.commit()
            if not deleted:
                if getattr(deleted, "relations", None):
                    await context.abort(grpc.StatusCode.FAILED_PRECONDITION, _blocking_relations_message(deleted.relations))
                await context.abort(grpc.StatusCode.NOT_FOUND, f"Entity not found: {request.ref}")
            await self._after_database_entity_write(entity.type)
            await self._emit_entity_changed(store, entity)
            return self.pb2.DeleteResult(deleted=True)
        entity = store.resolve(request.ref)
        store.delete(entity.id)
        await self._emit_entity_changed(store, entity)
        return self.pb2.DeleteResult(deleted=True)

    async def Import(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        payload = json.loads(request.json or "{}")
        if not isinstance(payload, dict):
            raise ValueError("import request must be an object")
        path = Path(str(payload["file"]))
        async with self.daemon.controller._factory()() as session:
            from edera_core.storage.import_export import import_entities_from_yaml, import_relations_from_yaml

            if payload.get("type") == "relation" or path.name.startswith("relation"):
                result = await import_relations_from_yaml(session, path, store.entity_types)
            else:
                result = await import_entities_from_yaml(session, path, store.entity_types)
            await session.commit()
        await self._emit_config_changed()
        return json_response(self.pb2, result.__dict__)

    async def Export(self, request, context):
        await _identity(context)
        store, app = _runtime_entity_store(self.daemon)
        store = _active_run_entity_store(self.daemon, request.dag_run_id or None) or store
        if _controller_started(self.daemon):
            async with self.daemon.controller._factory()() as session:
                results = await store.query_async(request.type or None, dag_run_id=request.dag_run_id or None, session=session)
        else:
            results = store.query_results(request.type or None, dag_run_id=request.dag_run_id or None)
        entities = [result.entity for result in results]
        if request.type == "relation":
            content = yaml.safe_dump(
                {"relations": [_relation_export_record(entity) for entity in entities if entity.type == "relation"]},
                allow_unicode=True,
                sort_keys=False,
            )
            return json_response(self.pb2, {"content": content, "exported": len(entities)})
        content = yaml.safe_dump(
            {"entities": [entity.model_dump(mode="json") for entity in entities]},
            allow_unicode=True,
            sort_keys=False,
        )
        return json_response(self.pb2, {"content": content, "exported": len(entities)})

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
                await self.daemon.controller.emit("event:config-changed", source="entity-service")
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

    async def _emit_config_changed(self) -> None:
        await self.daemon.controller.emit("event:config-changed", source="entity-service")

    async def _after_database_entity_write(self, entity_type: str) -> None:
        if entity_type == "trigger":
            await self.daemon.controller._reload_triggers()
            await self._emit_config_changed()
            return
        await self._emit_config_changed()

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
            fired = await self.daemon.controller.emit(f"manual:dag:{request.name}", payload, source="dag-service")
        except RunAlreadyActiveError as exc:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, exc.run_id)
        run_id = fired[0] if fired else ""
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
        except (DagError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return self.pb2.DagStatus(name=request.name, json=json.dumps(result, ensure_ascii=False, default=str))

    async def Stop(self, request, context):
        await _identity(context)
        async with self.daemon.controller._factory()() as session:
            if await get_dag_config(session, request.dag_name) is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.dag_name}' not found")
        run_id = await self.daemon.controller.stop_current(request.dag_name, force=request.force)
        return json_response(self.pb2, {"stopped": run_id is not None, "run_id": run_id})

    async def Retry(self, request, context):
        await _identity(context)
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
        dag_name = await self.daemon.controller.active_dag_for_node(request.id)
        if dag_name is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node '{request.id}' not found")
        run_id = await self.daemon.controller.stop_current(dag_name, node_id=request.id)
        return self.pb2.NodeStatus(id=request.id, status="stopped" if run_id is not None else "idle")

    async def Resume(self, request, context):
        await _identity(context)
        if not request.run_id:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "run_id is required")
        try:
            dag_name = await self.daemon.controller.dag_for_run_node(request.run_id, request.id)
        except DagRunNotFoundError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        if dag_name is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node '{request.id}' not found")
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
        async with self.daemon.controller._factory()() as session:
            source = (await source_map_from_store(session, self.daemon.controller.entity_store())).get(request.name)
            if source is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, "source not found")
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
    store = EntityStore(app.entities, app.entity_types, app.entity_relations, None)
    return store, app


def _runtime_entity_store(daemon: Server) -> tuple[EntityStore, AppConfig]:
    return daemon.controller.entity_store(), daemon.controller.runtime_config()


def _active_run_entity_store(daemon: Server, dag_run_id: str | None) -> EntityStore | None:
    if not dag_run_id:
        return None
    for context in getattr(daemon.controller, "active_runs", {}).values():
        if getattr(context, "run_id", None) != dag_run_id:
            continue
        task = getattr(context, "task", None)
        done = getattr(task, "done", None)
        if callable(done) and done():
            continue
        store = getattr(getattr(context, "executor", None), "entity_store", None)
        if isinstance(store, EntityStore):
            return store
    return None


def _controller_started(daemon: Server) -> bool:
    return getattr(daemon.controller, "factory", None) is not None


def _database_entity_available(daemon: Server, entity_type: str) -> bool:
    if not _controller_started(daemon):
        return False
    _, app = _runtime_entity_store(daemon)
    config = app.entity_types.get(entity_type)
    return config is not None and config.storage_tier == "database"


async def _resolve_entity_for_mutation(store: EntityStore, ref: str, session) -> EntityConfig:
    try:
        return (await store.query_one_async(ref, session=session)).entity
    except ConfigError:
        return store.resolve(ref)


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


def _entity_relation_refs(entity: EntityConfig, store: EntityStore) -> set[str]:
    refs = {entity.id}
    try:
        refs.add(entity_ref(entity, store.entity_types))
    except (KeyError, ValueError):
        pass
    return refs


def _relation_export_record(entity: EntityConfig) -> dict[str, object]:
    attrs = entity.attributes
    refs = attrs.get("entities")
    if not isinstance(refs, list) or len(refs) != 2:
        refs = [attrs.get("from_entity_id") or attrs.get("from"), attrs.get("to_entity_id") or attrs.get("to")]
    return {
        "id": entity.id,
        "entities": refs,
        "type": attrs.get("relation_type"),
        "metadata": attrs.get("metadata") or {},
    }


def _blocking_relations_message(relations) -> str:
    relation_ids = ", ".join(relation.id for relation in relations)
    return f"Entity is referenced by relations: {relation_ids}" if relation_ids else "Entity is referenced by relations"


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


def _default_identity_permissions(identity: str) -> dict[str, object] | None:
    if identity == "human" or identity.startswith("human:") or identity.startswith("bff:"):
        return None
    return {}


async def _identity_permissions_from_db(session, identity: str) -> dict[str, object] | None:
    if identity == "human" or identity.startswith("human:") or identity.startswith("bff:"):
        return None
    if not identity.startswith("node:"):
        return {}
    node_id = identity.removeprefix("node:")
    for dag in (await list_dag_configs(session)).values():
        for instance in dag.nodes:
            if instance.id == node_id or instance.alias == node_id or instance.type == node_id:
                permissions = instance.config.get("entity_permissions")
                return permissions if isinstance(permissions, dict) else {}
    return {}


def _check_write(identity: str, store: EntityStore, entity: EntityConfig, field: str, permissions: dict[str, object] | None) -> None:
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
    session=None,
) -> list[EntityConfig]:
    parts = [part.strip() for part in expression.split("AND") if part.strip()]
    if not parts:
        raise ValueError(_supported_query_message())
    relation_filters = _relation_filters(parts)
    if relation_filters is not None:
        return _readable_entities(identity, store, permissions, await _query_relations(store, relation_filters, session))
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


async def _query_relations(
    store: EntityStore,
    filters: dict[str, str],
    session=None,
) -> list[EntityConfig]:
    if session is None:
        return _filter_entities(store.query("relation"), filters)
    from edera_core.storage.repository import list_relations

    relations = await list_relations(session, **_relation_repository_filters(filters))
    return _filter_entities([_relation_entity(relation) for relation in relations], filters)


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


def _filters_from_json(value: str) -> dict[str, str]:
    if not value:
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("filters_json must be an object")
    return {str(key): str(item) for key, item in data.items()}


def _filter_entities(entities: list[EntityConfig], filters: dict[str, str]) -> list[EntityConfig]:
    result = entities
    for key, value in filters.items():
        result = [entity for entity in result if str(entity.attributes.get(key)) == value]
    return result


def _has_relation_repository_filter(filters: dict[str, str]) -> bool:
    return any(key in filters for key in ("from_entity_id", "from", "to_entity_id", "to", "relation_type"))


def _relation_repository_filters(filters: dict[str, str]) -> dict[str, str | None]:
    return {
        "from_entity_id": filters.get("from_entity_id") or filters.get("from"),
        "to_entity_id": filters.get("to_entity_id") or filters.get("to"),
        "relation_type": filters.get("relation_type"),
    }


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
            filters["relation_type"] = value
        elif key == "from_entity_id":
            filters["from_entity_id"] = value
        elif key == "to_entity_id":
            filters["to_entity_id"] = value
        elif key in {"from", "to"}:
            filters[key] = value
    return filters if is_relation else None


def _relation_entity(relation) -> EntityConfig:
    return _relation_config_entity(
        relation.id,
        [relation.from_entity_id, relation.to_entity_id],
        relation.relation_type,
        relation.metadata_,
    )


def _relation_config_entity(relation_id: str, refs: list[str], relation_type: str, metadata: dict[str, object]) -> EntityConfig:
    from_entity_id = refs[0] if refs else ""
    to_entity_id = refs[1] if len(refs) > 1 else ""
    return EntityConfig(
        id=relation_id,
        type="relation",
        attributes={
            "from": from_entity_id,
            "to": to_entity_id,
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            "relation_type": relation_type,
            "entities": refs,
            "metadata": metadata,
        },
    )


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
    async with daemon.controller._factory()() as session:
        dag_entity = await get_dag_entity(session, dag_name)
    if dag_entity is None:
        raise KeyError(dag_name)
    dag = DagConfig.model_validate(dag_entity.attributes)
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
    app = daemon.controller.runtime_config()
    async with daemon.controller._factory()() as session:
        dags = await _candidate_dag_closure(session, dag_name, dag_config)
        validate_sub_dag_nesting(dags, app.system.max_dag_depth)
        await save_core_entity(session, EntityConfig(id=dag_entity.id, type="dag", attributes=dag_config.model_dump(mode="json", by_alias=True)))
        await session.commit()
    await daemon.controller.emit("event:config-changed", source="dag-service")
    return {"updated": True, "dag": dag_name}


async def _candidate_dag_closure(session, dag_name: str, root: DagConfig) -> dict[str, DagConfig]:
    dags: dict[str, DagConfig] = {dag_name: root}

    async def visit(dag: DagConfig) -> None:
        for instance in dag.nodes:
            sub_dag_name = instance.dag_ref if instance.type == "dag" and instance.dag_ref else None
            if sub_dag_name is None and await get_dag_config(session, instance.type) is not None:
                sub_dag_name = instance.type
            if sub_dag_name is not None:
                if sub_dag_name not in dags:
                    sub_dag = await get_dag_config(session, sub_dag_name)
                    if sub_dag is None:
                        raise DagError(f"missing DAG config: {sub_dag_name}")
                    dags[sub_dag_name] = sub_dag
                    await visit(sub_dag)
                continue
            if await get_node_config(session, instance.type) is None:
                raise DagError(f"missing node config: {instance.type}")

    await visit(root)
    return dags


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
