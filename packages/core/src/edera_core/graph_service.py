from __future__ import annotations

from uuid import uuid4

import grpc

from edera_core.config.entities import validate_permission_overrides
from edera_core.config.schema import DagConfig, EntityConfig
from edera_core.dag.loader import validate_sub_dag_nesting
from edera_core.errors import ConfigError, DagError
from edera_core.service_common import (
    available_model_names,
    delete_node_assets,
    graph_dag_payload,
    graph_dag_state_from_database,
    graph_node_payload,
    json_response,
    node_payload,
    parse_json,
    save_node_assets,
    valid_dag_name,
)
from edera_core.storage.repository import (
    delete_core_entity,
    delete_skill,
    get_dag_config,
    get_node_config,
    list_enabled_extensions,
    list_dag_configs,
    list_dag_names,
    list_node_configs,
    list_skills,
    node_runs_for_run,
    recent_dag_runs,
    save_core_entity,
    skill_to_config,
    upsert_skill,
)


class _GraphService:
    def __init__(self, daemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def ListDags(self, request, context):
        async with self.daemon.controller._factory()() as session:
            return json_response(self.pb2, {"dags": await list_dag_names(session)})

    async def GetDag(self, request, context):
        try:
            app = self.daemon.controller.runtime_config()
            async with self.daemon.controller._factory()() as session:
                dag = await get_dag_config(session, request.name)
                if dag is None:
                    await context.abort(grpc.StatusCode.NOT_FOUND, f"dag {request.name} not found")
                return json_response(self.pb2, await graph_dag_state_from_database(app, request.name, session, dag, await list_node_configs(session)))
        except KeyError:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag {request.name} not found")

    async def CreateDag(self, request, context):
        name = request.name.strip()
        if not valid_dag_name(name):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "dag name must be kebab-case")
        async with self.daemon.controller._factory()() as session:
            if await get_dag_config(session, name) is not None:
                await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"dag '{name}' already exists")
        payload = {"name": name, "nodes": [], "edges": [], "ui": {}}
        await _save_core_and_emit(self.daemon, EntityConfig(id=name, type="dag", attributes=payload))
        return json_response(self.pb2, {"dag": payload})

    async def SaveDag(self, request, context):
        try:
            payload = graph_dag_payload(request.name, parse_json(request.json))
            app = self.daemon.controller.runtime_config()
            async with self.daemon.controller._factory()() as session:
                dags, nodes = await _candidate_dag_closure(session, request.name, payload)
            _validate_graph_entity_permissions(app.entity_types, payload)
            dag_config = DagConfig.model_validate(payload)
            validate_sub_dag_nesting(dags, app.system.max_dag_depth)
            await _save_core_and_emit(self.daemon, EntityConfig(id=request.name, type="dag", attributes=dag_config.model_dump(by_alias=True, mode="json")))
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
        app = self.daemon.controller.runtime_config()
        async with self.daemon.controller._factory()() as session:
            dag = await get_dag_config(session, request.name)
            nodes = await list_node_configs(session)
        if dag is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"dag '{request.name}' not found")
        node_name = str(body.get("name", ""))
        if not node_name:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "node name is required")
        if node_name in nodes:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"node '{node_name}' already exists")
        try:
            node_data = graph_node_payload(node_name, body)
            dag_nodes = [node.model_dump(mode="json") for node in dag.nodes] + [{"id": uuid4().hex, "type": node_name, "alias": node_name, "config": {}}]
            dag_payload = {"name": dag.name, "nodes": dag_nodes, "edges": [{"from": e.from_, "to": e.to, "fan_out": e.fan_out, "fan_in": e.fan_in} for e in dag.edges], "ui": dag.ui}
            dag_config = DagConfig.model_validate(dag_payload)
            async with self.daemon.controller._factory()() as session:
                await save_core_entity(session, EntityConfig(id=node_name, type="node", attributes=node_data))
                await save_core_entity(session, EntityConfig(id=request.name, type="dag", attributes=dag_config.model_dump(by_alias=True, mode="json")))
                await session.commit()
            await _emit_config_changed(self.daemon)
            node_config = await _get_node_config_or_abort(self.daemon, node_name, context)
        except (ConfigError, KeyError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"node": node_payload(node_config, app.skills, app.entity_types, app.entities, available_model_names())})

    async def ListNodeTypes(self, request, context):
        app = self.daemon.controller.runtime_config()
        model_names = available_model_names()
        async with self.daemon.controller._factory()() as session:
            nodes = await list_node_configs(session)
        payload = [node_payload(node, app.skills, app.entity_types, app.entities, model_names) for node in nodes.values()]
        return json_response(self.pb2, {"types": payload, "prototypes": payload})

    async def GetNodeType(self, request, context):
        app = self.daemon.controller.runtime_config()
        node_config = await _get_node_config_or_abort(self.daemon, request.name, context)
        return json_response(self.pb2, {"node": node_payload(node_config, app.skills, app.entity_types, app.entities, available_model_names())})

    async def SaveNodeType(self, request, context):
        body = parse_json(request.json)
        try:
            payload = graph_node_payload(request.name, body)
            save_node_assets(self.daemon.config_dir.parent, payload, body)
            await _save_core_and_emit(self.daemon, EntityConfig(id=request.name, type="node", attributes=payload))
            app = self.daemon.controller.runtime_config()
            node_config = await _get_node_config_or_abort(self.daemon, request.name, context)
        except (ConfigError, KeyError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"node": node_payload(node_config, app.skills, app.entity_types, app.entities, available_model_names())})

    async def CreateNodeType(self, request, context):
        async with self.daemon.controller._factory()() as session:
            if await get_node_config(session, request.name) is not None:
                await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"node type '{request.name}' already exists")
        return await self.SaveNodeType(request, context)

    async def DeleteNodeType(self, request, context):
        app = self.daemon.controller.runtime_config()
        async with self.daemon.controller._factory()() as session:
            dags = await list_dag_configs(session)
            node = await get_node_config(session, request.name)
        for dag in dags.values():
            if any(node.type == request.name for node in dag.nodes):
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"node type '{request.name}' is referenced by DAG '{dag.name}'")
        if node is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"node type {request.name} not found")
        async with self.daemon.controller._factory()() as session:
            await delete_core_entity(session, request.name, app.entity_types)
            await session.commit()
        delete_node_assets(self.daemon.config_dir.parent, node)
        await _emit_config_changed(self.daemon)
        return json_response(self.pb2, {"deleted": True})

    async def ListSkills(self, request, context):
        async with self.daemon.controller._factory()() as session:
            skills = [skill_to_config(skill).model_dump(mode="json") for skill in await list_skills(session)]
        return json_response(self.pb2, {"skills": skills})

    async def CreateSkill(self, request, context):
        body = parse_json(request.json)
        name = str(body.get("name", ""))
        if not name:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "skill name is required")
        async with self.daemon.controller._factory()() as session:
            if any(skill.name == name for skill in await list_skills(session)):
                await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"skill '{name}' already exists")
            skill = await upsert_skill(session, name, _skill_files(body), _display_name(body), _description(body))
            await session.commit()
        await _emit_config_changed(self.daemon)
        return json_response(self.pb2, {"skill": skill_to_config(skill).model_dump(mode="json")})

    async def SaveSkill(self, request, context):
        body = {**parse_json(request.json), "name": request.name}
        async with self.daemon.controller._factory()() as session:
            skill = await upsert_skill(session, request.name, _skill_files(body), _display_name(body), _description(body))
            await session.commit()
        await _emit_config_changed(self.daemon)
        return json_response(self.pb2, {"skill": skill_to_config(skill).model_dump(mode="json")})

    async def DeleteSkill(self, request, context):
        async with self.daemon.controller._factory()() as session:
            deleted = await delete_skill(session, request.name)
            await session.commit()
        if not deleted:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"skill {request.name} not found")
        await _emit_config_changed(self.daemon)
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


async def _save_core_and_emit(daemon, entity: EntityConfig) -> None:
    async with daemon.controller._factory()() as session:
        await save_core_entity(session, entity)
        await session.commit()
    await _emit_config_changed(daemon)


async def _emit_config_changed(daemon) -> None:
    await daemon.controller.emit("event:config-changed", source="graph-service")


async def _get_node_config_or_abort(daemon, name: str, context):
    async with daemon.controller._factory()() as session:
        node_config = await get_node_config(session, name)
    if node_config is None:
        await context.abort(grpc.StatusCode.NOT_FOUND, f"node {name} not found")
    return node_config


def _skill_files(body: dict[str, object]) -> list[dict[str, str]]:
    files = body.get("files")
    if isinstance(files, list):
        return [
            {"path": str(item.get("path") or ""), "content": str(item.get("content") or "")}
            for item in files
            if isinstance(item, dict)
        ]
    name = str(body.get("name") or "skill").strip() or "skill"
    description = _description(body)
    content = str(body.get("content") or body.get("skill_md") or f"# {name}\n\n{description}".rstrip())
    return [{"path": "SKILL.md", "content": content}]


def _display_name(body: dict[str, object]) -> str | None:
    value = body.get("display_name")
    return str(value) if value is not None else None


def _description(body: dict[str, object]) -> str:
    return str(body.get("description") or "")


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


async def _candidate_dag_closure(session, dag_name: str, payload: dict[str, object]) -> tuple[dict[str, DagConfig], dict[str, object]]:
    root = DagConfig.model_validate(payload)
    dags: dict[str, DagConfig] = {dag_name: root}
    nodes: dict[str, object] = {}

    async def visit(dag: DagConfig) -> None:
        for instance in dag.nodes:
            sub_dag_name = instance.dag_ref if instance.type == "dag" and instance.dag_ref else None
            if sub_dag_name is None:
                existing_dag = await get_dag_config(session, instance.type)
                if existing_dag is not None:
                    sub_dag_name = instance.type
            if sub_dag_name is not None:
                if sub_dag_name not in dags:
                    sub_dag = await get_dag_config(session, sub_dag_name)
                    if sub_dag is None:
                        raise ConfigError(f"dag '{sub_dag_name}' not found")
                    dags[sub_dag_name] = sub_dag
                    await visit(sub_dag)
                continue
            if instance.type in nodes:
                continue
            node = await get_node_config(session, instance.type)
            if node is None:
                raise ConfigError(f"node type '{instance.type}' not found")
            nodes[instance.type] = node

    await visit(root)
    return dags, nodes


def _manifest_handlers(manifest: dict[str, object]) -> list[dict[str, object]]:
    handlers = manifest.get("handlers")
    return [item for item in handlers if isinstance(item, dict)] if isinstance(handlers, list) else []
