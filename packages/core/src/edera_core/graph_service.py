from __future__ import annotations

from uuid import uuid4

import grpc
import yaml

from edera_core.config.entities import validate_permission_overrides
from edera_core.config.loader import _load_runtime_base_config, load_skill_configs
from edera_core.config.schema import DagConfig, EntityConfig, SkillConfig
from edera_core.dag.loader import validate_sub_dag_nesting
from edera_core.errors import ConfigError, DagError
from edera_core.service_common import (
    available_model_names,
    delete_node_assets,
    graph_dag_payload,
    graph_dag_state_from_config,
    graph_node_payload,
    json_response,
    node_payload,
    parse_json,
    save_node_assets,
    save_skill,
    valid_dag_name,
)
from edera_core.storage.repository import delete_core_entity, list_enabled_extensions, node_runs_for_run, recent_dag_runs, save_core_entity


class _GraphService:
    def __init__(self, daemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def ListDags(self, request, context):
        return json_response(self.pb2, {"dags": sorted(self.daemon.controller.runtime_snapshot().config.dags)})

    async def GetDag(self, request, context):
        try:
            return json_response(self.pb2, graph_dag_state_from_config(self.daemon.controller.runtime_snapshot().config, request.name))
        except KeyError:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag {request.name} not found")

    async def CreateDag(self, request, context):
        name = request.name.strip()
        if not valid_dag_name(name):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "dag name must be kebab-case")
        if name in self.daemon.controller.runtime_snapshot().config.dags:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"dag '{name}' already exists")
        payload = {"name": name, "nodes": [], "edges": [], "ui": {}}
        await _save_core_and_refresh(self.daemon, EntityConfig(id=name, type="dag", attributes=payload))
        return json_response(self.pb2, {"dag": payload})

    async def SaveDag(self, request, context):
        try:
            payload = graph_dag_payload(request.name, parse_json(request.json))
            app = self.daemon.controller.runtime_snapshot().config
            _validate_graph_node_refs(app, payload)
            _validate_graph_entity_permissions(app.entity_types, payload)
            dag_config = DagConfig.model_validate(payload)
            validate_sub_dag_nesting({**app.dags, request.name: dag_config}, app.system.max_dag_depth)
            await _save_core_and_refresh(self.daemon, EntityConfig(id=request.name, type="dag", attributes=dag_config.model_dump(by_alias=True, mode="json")))
        except (ConfigError, DagError, KeyError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(
            self.pb2,
            {
                "dag": {
                    "name": dag_config.name,
                    "nodes": [node.model_dump(mode="json") for node in dag_config.nodes],
                    "edges": [edge.model_dump(mode="json", by_alias=True) for edge in dag_config.edges],
                    "ui": dag_config.ui,
                },
            },
        )

    async def CreateDagNode(self, request, context):
        body = parse_json(request.json)
        app = self.daemon.controller.runtime_snapshot().config
        dags = app.dags
        if request.name not in dags:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.name}' not found")
        node_name = str(body.get("name", ""))
        if not node_name:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "node name is required")
        if node_name in app.nodes:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"node '{node_name}' already exists")
        try:
            node_data = graph_node_payload(node_name, body)
            dag = dags[request.name]
            dag_nodes = [node.model_dump(mode="json") for node in dag.nodes] + [{"id": uuid4().hex, "type": node_name, "alias": node_name, "config": {}}]
            dag_payload = {"name": dag.name, "nodes": dag_nodes, "edges": [{"from": e.from_, "to": e.to, "fan_out": e.fan_out, "fan_in": e.fan_in} for e in dag.edges], "ui": dag.ui}
            dag_config = DagConfig.model_validate(dag_payload)
            async with self.daemon.controller._factory()() as session:
                await save_core_entity(session, EntityConfig(id=node_name, type="node", attributes=node_data))
                await save_core_entity(session, EntityConfig(id=request.name, type="dag", attributes=dag_config.model_dump(by_alias=True, mode="json")))
                await session.commit()
            await _refresh_runtime_snapshot(self.daemon)
            app = self.daemon.controller.runtime_snapshot().config
            node_config = app.nodes[node_name]
        except (ConfigError, KeyError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"node": node_payload(node_config, app.skills, app.entity_types, app.entities, available_model_names())})

    async def ListNodeTypes(self, request, context):
        app = self.daemon.controller.runtime_snapshot().config
        model_names = available_model_names()
        payload = [node_payload(node, app.skills, app.entity_types, app.entities, model_names) for node in app.nodes.values()]
        return json_response(self.pb2, {"types": payload, "prototypes": payload})

    async def GetNodeType(self, request, context):
        try:
            app = self.daemon.controller.runtime_snapshot().config
            return json_response(self.pb2, {"node": node_payload(app.nodes[request.name], app.skills, app.entity_types, app.entities, available_model_names())})
        except KeyError:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node {request.name} not found")

    async def SaveNodeType(self, request, context):
        body = parse_json(request.json)
        try:
            payload = graph_node_payload(request.name, body)
            save_node_assets(self.daemon.config_dir.parent, payload, body)
            await _save_core_and_refresh(self.daemon, EntityConfig(id=request.name, type="node", attributes=payload))
            app = self.daemon.controller.runtime_snapshot().config
            node_config = app.nodes[request.name]
        except (ConfigError, KeyError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"node": node_payload(node_config, app.skills, app.entity_types, app.entities, available_model_names())})

    async def CreateNodeType(self, request, context):
        if request.name in self.daemon.controller.runtime_snapshot().config.nodes:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"node type '{request.name}' already exists")
        return await self.SaveNodeType(request, context)

    async def DeleteNodeType(self, request, context):
        app = self.daemon.controller.runtime_snapshot().config
        for dag in app.dags.values():
            if any(node.type == request.name for node in dag.nodes):
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"node type '{request.name}' is referenced by DAG '{dag.name}'")
        if request.name not in app.nodes:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node type {request.name} not found")
        node = app.nodes[request.name]
        async with self.daemon.controller._factory()() as session:
            await delete_core_entity(session, request.name, app.entity_types)
            await session.commit()
        delete_node_assets(self.daemon.config_dir.parent, node)
        await _refresh_runtime_snapshot(self.daemon)
        return json_response(self.pb2, {"deleted": True})

    async def ListSkills(self, request, context):
        return json_response(self.pb2, {"skills": [skill.model_dump(mode="json") for skill in load_skill_configs(self.daemon.config_dir / "skills").values()]})

    async def CreateSkill(self, request, context):
        body = parse_json(request.json)
        name = str(body.get("name", ""))
        if not name:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "skill name is required")
        path = self.daemon.config_dir / "skills" / f"{name}.yaml"
        if path.exists():
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"skill '{name}' already exists")
        return json_response(self.pb2, save_skill(self.daemon.config_dir.parent, path, body))

    async def SaveSkill(self, request, context):
        body = {**parse_json(request.json), "name": request.name}
        return json_response(self.pb2, save_skill(self.daemon.config_dir.parent, self.daemon.config_dir / "skills" / f"{request.name}.yaml", body))

    async def DeleteSkill(self, request, context):
        path = self.daemon.config_dir / "skills" / f"{request.name}.yaml"
        if not path.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, f"skill {request.name} not found")
        skill = SkillConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        path.unlink()
        (self.daemon.config_dir.parent / "extensions" / skill.handler / "handler.py").unlink(missing_ok=True)
        return json_response(self.pb2, {"deleted": True})

    async def ListHandlers(self, request, context):
        handlers = []
        async with self.daemon.controller._factory()() as session:
            for record in await list_enabled_extensions(session):
                handlers.extend({"name": handler["name"]} for handler in _manifest_handlers(record.manifest_data) if isinstance(handler.get("name"), str))
        return json_response(self.pb2, {"handlers": handlers})

    async def GetHandler(self, request, context):
        entry = await self._handler_path(request.name)
        if entry is None or not entry.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, f"handler {request.name} not found")
        return json_response(self.pb2, {"name": request.name, "code": entry.read_text(encoding="utf-8")})

    async def SaveHandler(self, request, context):
        entry = await self._handler_path(request.name)
        if entry is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"handler {request.name} not found")
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text(request.content, encoding="utf-8")
        return json_response(self.pb2, {"name": request.name, "code": request.content})

    async def _handler_path(self, name: str):
        async with self.daemon.controller._factory()() as session:
            for record in await list_enabled_extensions(session):
                for handler in _manifest_handlers(record.manifest_data):
                    if handler.get("name") == name and isinstance(handler.get("entry"), str):
                        return self.daemon.config_dir.parent / "handlers" / record.name / str(handler["entry"])
        return None

    async def RuntimeStatus(self, request, context):
        factory = self.daemon.controller._factory()
        run_id = request.run_id or ""
        if not run_id:
            async with factory() as session:
                recent = await recent_dag_runs(session)
            run_id = recent[0].run_id if recent else ""
        node_statuses: dict[str, dict[str, object]] = {}
        if run_id:
            async with factory() as session:
                for node_run in await node_runs_for_run(session, run_id):
                    node_statuses[node_run.node_name] = {
                        "status": node_run.status,
                        "started_at": node_run.started_at.isoformat() if node_run.started_at else None,
                        "ended_at": node_run.ended_at.isoformat() if node_run.ended_at else None,
                        "error": node_run.error,
                        "run_id": node_run.run_id,
                        "metadata": node_run.metadata_,
                    }
        return json_response(self.pb2, {"node_statuses": node_statuses})


async def _save_core_and_refresh(daemon, entity: EntityConfig) -> None:
    async with daemon.controller._factory()() as session:
        await save_core_entity(session, entity)
        await session.commit()
    await _refresh_runtime_snapshot(daemon)


async def _refresh_runtime_snapshot(daemon) -> None:
    config = _load_runtime_base_config(daemon.config_dir)
    await daemon.controller.install_snapshot(config, daemon.controller.runtime_snapshot().bootstrap)


def _validate_graph_entity_permissions(entity_types: dict[str, object], payload: dict[str, object]) -> None:
    nodes = payload.get("nodes", [])
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        config = node.get("config")
        if not isinstance(config, dict):
            continue
        permissions = config.get("entity_permissions")
        if isinstance(permissions, dict):
            validate_permission_overrides(entity_types, permissions)


def _validate_graph_node_refs(app, payload: dict[str, object]) -> None:
    nodes = payload.get("nodes", [])
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or "")
        dag_ref = node.get("dag_ref")
        if node_type in app.nodes or node_type in app.dags:
            continue
        if node_type == "dag" and isinstance(dag_ref, str) and dag_ref in app.dags:
            continue
        raise ConfigError(f"node type '{node_type}' not found")


def _manifest_handlers(manifest: dict[str, object]) -> list[dict[str, object]]:
    handlers = manifest.get("handlers")
    return [item for item in handlers if isinstance(item, dict)] if isinstance(handlers, list) else []
