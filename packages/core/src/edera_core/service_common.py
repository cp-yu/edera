from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import yaml
from pydantic import ValidationError

from edera_core.config.editor import ConfigEditError, ConfigKind, RuntimeConfigEditor
from edera_core.config.entities import EntityStore, validate_permission_overrides
from edera_core.config.loader import (
    load_entity_type_configs,
    load_system_config,
)
from edera_core.config.schema import (
    AppConfig,
    DagConfig,
    EntitiesConfig,
    EntityConfig,
    EntityRelationConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    NodeConfig,
    SkillConfig,
    entity_ref,
)
from edera_core.errors import ConfigError

INSTANCE_CONFIG_FIELDS = {
    "model",
    "skills",
    "source_names",
    "entities",
    "entity_permissions",
    "timeout_seconds",
    "session_dir",
    "workdir",
    "tools",
}
SOURCE_ENTITY_TYPES = {"rss-source", "web-source", "api-source"}


def json_response(pb2, payload: object):
    return pb2.JsonResponse(json=json.dumps(payload, ensure_ascii=False, default=str))


def parse_json(value: str) -> dict[str, object]:
    payload = json.loads(value or "{}")
    if not isinstance(payload, dict):
        raise ConfigEditError("json payload must be an object")
    return payload


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def limit(value: int, default: int = 50) -> int:
    return min(max(value or default, 1), 100)


def editor(config_path: Path) -> RuntimeConfigEditor:
    return RuntimeConfigEditor(config_path, config_path.parent / "skills")


def kind(value: str) -> ConfigKind:
    if value not in {"system", "entities", "entity-relations", "node", "dag", "skill"}:
        raise ConfigEditError(f"unsupported config kind: {value}")
    return cast(ConfigKind, value)


def entity_store(root: Path) -> EntityStore:
    entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
    return EntityStore(EntitiesConfig(), entity_types, EntityRelationsConfig(), None)


def source_map(store: EntityStore) -> dict[str, EntityConfig]:
    return {
        str(entity.attributes.get("name") or entity.id): entity
        for entity in store.entities.entities
        if entity.type in SOURCE_ENTITY_TYPES
    }


async def source_map_from_store(session: Any, store: EntityStore) -> dict[str, EntityConfig]:
    sources = source_map(store)
    from edera_core.storage.repository import list_ordinary_entities

    for entity_type in sorted(SOURCE_ENTITY_TYPES):
        for entity in await list_ordinary_entities(session, store.entity_types, entity_type):
            sources[str(entity.attributes.get("name") or entity.id)] = entity
    return sources


def repair_task_payload(
    output_dir: Path,
    source_config: dict[str, object],
    health: dict[str, object],
    log: dict[str, object],
) -> dict[str, object]:
    now = datetime.now().astimezone().isoformat()
    task_id = f"{health['source_name']}-{uuid4().hex[:12]}"
    task_path = output_dir / f"{task_id}.json"
    return {
        "task_id": task_id,
        "task_path": str(task_path),
        "source_name": health["source_name"],
        "created_at": now,
        "source_config": source_config,
        "failure_context": {
            "run_id": health.get("run_id"),
            "latest_failure_reason": health.get("latest_failure_reason"),
            "node_error": log.get("error"),
            "dag_status": log.get("dag_status"),
        },
        "recovery_summary": {
            "recovery_status": health.get("recovery_status"),
            "attempt_count": health.get("attempt_count"),
            "recoverable_reason": health.get("recoverable_reason"),
            "escalation_reason": health.get("escalation_reason"),
        },
        "expected_fix": "Update only this source configuration or parser so the next DAG run succeeds.",
    }


def repair_task_dir(config_path: Path) -> Path:
    system_config = load_system_config(config_path / "system.toml")
    return system_config.source_repair_task_output_dir or system_config.workspace_root / "source-repair-tasks"


def write_repair_task(task: dict[str, object]) -> None:
    path = Path(str(task["task_path"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")


def metadata_bar(briefing: EntityConfig | None, failed_sources: dict[str, object]) -> dict[str, object]:
    if briefing is None:
        return {
            "run_id": "无",
            "created_at": "",
            "window": "无数据窗口",
            "failed_count": 0,
            "degraded": False,
            "disclaimer": "本系统产出仅供学习参考，不构成投资建议。",
        }
    data = model_payload(briefing)
    data_window = briefing_metadata(briefing).get("data_window", {})
    if not isinstance(data_window, dict):
        data_window = {}
    start = data_window.get("start", "")
    end = data_window.get("end", "")
    return {
        "run_id": data.get("run_id", ""),
        "created_at": str(data.get("created_at") or ""),
        "window": f"{start} 至 {end}" if start or end else "无数据窗口",
        "failed_count": len(failed_sources),
        "degraded": bool(failed_sources),
        "disclaimer": "本系统产出仅供学习参考，不构成投资建议。",
    }


def summary_item(advice: Any, degraded: bool) -> dict[str, object]:
    data = model_payload(advice)
    direction = str(data.get("direction") or "hold")
    if data.get("low_confidence"):
        state = "low-confidence"
        label = "低置信度"
    else:
        state = direction
        label = {"buy": "买入", "sell": "卖出", "hold": "持有"}.get(direction, direction)
    data.update(
        {
            "state": state,
            "state_class": f"state-{state}",
            "direction_label": label,
            "degraded": degraded,
            "comparison": empty_comparison(),
        }
    )
    return data


def advice_payload(advice: Any) -> dict[str, object]:
    data = model_payload(advice)
    data["id"] = str(data.get("id") or getattr(advice, "id", ""))
    data["comparison"] = empty_comparison()
    return data


def briefing_payload(briefing: EntityConfig) -> dict[str, object]:
    data = model_payload(briefing)
    return {
        "id": str(data.get("id") or briefing.id),
        "run_id": str(data.get("run_id") or ""),
        "content": str(data.get("content") or ""),
        "metadata": briefing_metadata(briefing),
        "created_at": str(data.get("created_at") or ""),
    }


def briefing_metadata(briefing: EntityConfig) -> dict[str, object]:
    metadata = model_payload(briefing).get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def event_payload(event: Any) -> dict[str, object]:
    if isinstance(event, EntityConfig):
        data = model_payload(event)
        return {
            "id": data.get("id"),
            "stock_code": data.get("stock_code", ""),
            "title": data.get("title", ""),
            "status": data.get("status", ""),
            "heat_score": data.get("heat_score", 0),
            "heat_score_components": data.get("heat_score_components", {}),
            "contradiction": data.get("contradiction", False),
            "source_names": data.get("source_names", []),
            "evidence_analysis_ids": data.get("evidence_analysis_ids", []),
            "evidence_raw_item_ids": data.get("evidence_raw_item_ids", []),
            "evidence_count": len(data.get("evidence_analysis_ids", [])),
            "source_count": len(data.get("source_names", [])),
            "first_seen_at": data.get("first_seen_at", ""),
            "last_seen_at": data.get("last_seen_at", ""),
        }
    return {
        "id": event.id,
        "stock_code": event.stock_code,
        "title": event.title,
        "status": event.status,
        "heat_score": event.heat_score,
        "heat_score_components": event.heat_score_components,
        "contradiction": event.contradiction,
        "source_names": event.source_names,
        "evidence_analysis_ids": event.evidence_analysis_ids,
        "evidence_raw_item_ids": event.evidence_raw_item_ids,
        "evidence_count": len(event.evidence_analysis_ids),
        "source_count": len(event.source_names),
        "first_seen_at": event.first_seen_at.isoformat() if event.first_seen_at else "",
        "last_seen_at": event.last_seen_at.isoformat() if event.last_seen_at else "",
    }


def model_payload(value: Any) -> dict[str, object]:
    if isinstance(value, EntityConfig):
        return dict(value.attributes)
    return cast(dict[str, object], value.model_dump(mode="json"))


def empty_comparison() -> dict[str, object]:
    return {"verdict": "unknown", "verdict_label": "未知"}


def entity_type_path(root: Path, name: str) -> Path:
    if "/" in name or "\\" in name or name in {"", ".", ".."}:
        raise ConfigEditError("invalid entity type name")
    return root.parent / "schemas" / "entity-types" / f"{name}.yaml"


def resolve_entity_type_path(root: Path, name: str) -> Path:
    path = entity_type_path(root, name)
    if path.exists():
        return path
    return root / "schemas" / f"{name}.yaml"


def entity_type_config(root: Path, name: str) -> EntityTypeConfig | None:
    return load_entity_type_configs(root.parent / "schemas" / "entity-types").get(name)


def validate_entity_type_content(content: str) -> None:
    data = yaml.safe_load(content) or {}
    if not isinstance(data, dict):
        raise ConfigEditError("YAML content must be a mapping")
    EntityTypeConfig.model_validate(data)


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def valid_dag_name(name: str) -> bool:
    return bool(name) and all(part and part.islower() and part.replace("-", "").isalnum() for part in name.split("-"))


def graph_dag_state_from_config(app: AppConfig, name: str) -> dict[str, object]:
    return _graph_dag_state(
        app.dags[name],
        app.nodes,
        app.skills,
        app.entity_types,
        app.entities,
        app.entity_relations,
    )


async def graph_dag_state_from_database(
    app: AppConfig,
    name: str,
    session: Any,
    dag: DagConfig | None = None,
    nodes: dict[str, NodeConfig] | None = None,
) -> dict[str, object]:
    from edera_core.storage.repository import list_ordinary_entities, list_relations

    entities = _merge_entities(
        app.entities.entities,
        await list_ordinary_entities(session, app.entity_types),
    )
    relation_configs = list(app.entity_relations.relations)
    seen = {relation.id for relation in relation_configs}
    for relation in await list_relations(session):
        if relation.id in seen:
            continue
        relation_configs.append(_relation_config(relation))
        seen.add(relation.id)
    return _graph_dag_state(
        dag or app.dags[name],
        nodes or app.nodes,
        app.skills,
        app.entity_types,
        EntitiesConfig(entities=entities),
        EntityRelationsConfig(relations=relation_configs),
    )


def _graph_dag_state(
    dag: DagConfig,
    nodes: dict[str, NodeConfig],
    skills: dict[str, SkillConfig],
    entity_types: dict[str, EntityTypeConfig],
    entities: EntitiesConfig,
    relations: EntityRelationsConfig,
) -> dict[str, object]:
    model_names = available_model_names()
    node_instances = []
    for instance in dag.nodes:
        node_config = nodes.get(instance.type)
        if node_config:
            item = node_payload(node_config, skills, entity_types, entities, model_names)
            item.update({
                "id": instance.id,
                "type_name": instance.type,
                "dag_ref": instance.dag_ref,
                "input_mapping": instance.input_mapping,
                "alias": instance.alias,
                "config": instance.config,
                "optional": instance.optional,
            })
            for key, value in instance.config.items():
                if key in INSTANCE_CONFIG_FIELDS | {"parameters"}:
                    item[key] = value
        else:
            item = {
                "id": instance.id,
                "name": instance.type,
                "type": "function",
                "type_name": instance.type,
                "dag_ref": instance.dag_ref,
                "input_mapping": instance.input_mapping,
                "alias": instance.alias,
                "config": instance.config,
                "input_type": "Any",
                "output_type": "Any",
                "optional": instance.optional,
            }
        if instance.loop:
            item["loop"] = instance.loop.model_dump(mode="json", exclude_none=True)
        if instance.resource:
            item["resource"] = instance.resource
        node_instances.append(item)
    return {
        "name": dag.name,
        "nodes": node_instances,
        "edges": [{"from": e.from_, "to": e.to, "fan_out": e.fan_out, "fan_in": e.fan_in, "optional": e.optional, "fan_in_mode": e.fan_in_mode} for e in dag.edges],
        "ui": dag.ui,
        "entity_types": entity_types_payload(entity_types),
        "entities": entity_list_payload(entity_types, entities),
        "entity_relations": [relation.model_dump(mode="json") for relation in relations.relations],
    }


def _merge_entities(*groups: list[EntityConfig]) -> list[EntityConfig]:
    seen: set[str] = set()
    entities: list[EntityConfig] = []
    for group in groups:
        for entity in group:
            if entity.id in seen:
                continue
            seen.add(entity.id)
            entities.append(entity)
    return entities


def _relation_config(relation: Any) -> EntityRelationConfig:
    return EntityRelationConfig(
        id=relation.id,
        entities=[relation.from_entity_id, relation.to_entity_id],
        type=relation.relation_type,
        metadata=relation.metadata_,
    )


def graph_dag_payload(name: str, body: dict[str, object]) -> dict[str, object]:
    nodes = body.get("nodes", [])
    edges = body.get("edges", [])
    ui = body.get("ui", {})
    if not isinstance(nodes, list):
        raise ConfigEditError("dag nodes must be a list")
    if not isinstance(edges, list):
        raise ConfigEditError("dag edges must be a list")
    payload: dict[str, object] = {
        "name": name,
        "nodes": [dag_node_payload(node) for node in nodes],
        "edges": [dag_edge_payload(edge) for edge in edges],
        "ui": ui if isinstance(ui, dict) else {},
    }
    try:
        return DagConfig.model_validate(payload).model_dump(by_alias=True, mode="json")
    except ValidationError as exc:
        raise ConfigEditError(str(exc)) from exc


def validate_graph_entity_permissions(config_root: Path, payload: dict[str, object]) -> None:
    entity_types = load_entity_type_configs(config_root.parent / "schemas" / "entity-types")
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


def graph_node_payload(name: str, body: dict[str, object]) -> dict[str, object]:
    skills = body.get("skills", [])
    if not isinstance(skills, list):
        skills = []
    inferred_type = body.get("type")
    if inferred_type != "function":
        inferred_type = "function"
    payload: dict[str, object] = {
        "name": name,
        "type": inferred_type,
        "role": body.get("role", "processor"),
        "skills": [str(s) for s in skills],
        "handler": body.get("handler", name if inferred_type == "function" else None),
        "system_prompt_file": body.get("system_prompt_file", None),
        "tools": body.get("tools", []),
        "input_type": body.get("input_type", "Any"),
        "output_type": body.get("output_type", "Any"),
        "timeout_seconds": body.get("timeout_seconds"),
        "source_names": body.get("source_names", []),
        "parameters": body.get("parameters", {}),
        "parameters_schema": body.get("parameters_schema", {}),
    }
    try:
        return NodeConfig.model_validate(payload).model_dump(mode="json")
    except ValidationError as exc:
        raise ConfigEditError(str(exc)) from exc


def dag_node_payload(node: object) -> dict[str, object]:
    if isinstance(node, str):
        return {"id": node, "type": node, "alias": node, "config": {}}
    if not isinstance(node, dict):
        raise ConfigEditError("dag node must be a mapping")
    node_type = node.get("type_name") or node.get("type") or node.get("name")
    node_id = node.get("id", node.get("name"))
    if not isinstance(node_id, str) or not isinstance(node_type, str):
        raise ConfigEditError("dag node requires id and type")
    payload: dict[str, object] = {"id": node_id, "type": node_type, "config": split_instance_config(node.get("config", {}))}
    alias = node.get("alias")
    if isinstance(alias, str) and alias:
        payload["alias"] = alias
    if bool(node.get("optional")):
        payload["optional"] = True
    dag_ref = node.get("dag_ref")
    if isinstance(dag_ref, str) and dag_ref:
        payload["dag_ref"] = dag_ref
    input_mapping = node.get("input_mapping")
    if isinstance(input_mapping, dict):
        payload["input_mapping"] = {str(key): str(value) for key, value in input_mapping.items()}
    loop = node.get("loop")
    if isinstance(loop, dict):
        payload["loop"] = loop
    resource = node.get("resource")
    if isinstance(resource, str):
        payload["resource"] = resource
    return payload


def dag_edge_payload(edge: object) -> dict[str, object]:
    if not isinstance(edge, dict):
        raise ConfigEditError("dag edge must be a mapping")
    from_node = edge.get("from")
    to_node = edge.get("to")
    if not isinstance(from_node, str) or not isinstance(to_node, str):
        raise ConfigEditError("dag edge requires from and to")
    payload: dict[str, object] = {"from": from_node, "to": to_node}
    for key in ("fan_out", "fan_in", "optional"):
        if bool(edge.get(key)):
            payload[key] = True
    mode = edge.get("fan_in_mode")
    if mode in {"barrier", "accumulate", "collect", "stream"}:
        payload["fan_in_mode"] = mode
    return payload


def node_payload(
    node: NodeConfig,
    skills: dict[str, SkillConfig] | None = None,
    entity_types: dict[str, EntityTypeConfig] | None = None,
    entities: EntitiesConfig | None = None,
    model_names: list[str] | None = None,
) -> dict[str, object]:
    payload = node.model_dump(mode="json")
    if skills is not None and entity_types is not None and entities is not None:
        payload["inspector_schema"] = build_inspector_schema(node, skills, entity_types, entities, model_names or [])
    return payload


def build_inspector_schema(
    node: NodeConfig,
    skills: dict[str, SkillConfig],
    entity_types: dict[str, EntityTypeConfig],
    entities: EntitiesConfig,
    model_names: list[str],
) -> dict[str, object]:
    properties: dict[str, object] = {}
    if node.type == "function" and node.role == "source":
        properties["entities"] = {
            "type": "array",
            "items": {"type": "string", "enum": sorted(entity_ref(entity, entity_types) for entity in entities.entities if entity.type in {"rss-source", "web-source", "api-source"})},
            "default": [source_ref_for_name(entities, entity_types, name) for name in node.source_names],
        }
    properties["entity_permissions"] = {
        "type": "object",
        "properties": {
            name: {"type": "object", "properties": {field: {"type": "string", "enum": ["none", "read-only", "write-only", "read-write"]} for field in entity_type.field_permissions}}
            for name, entity_type in entity_types.items()
        },
        "default": {},
    }
    properties["timeout_seconds"] = {"type": "number", "default": node.timeout_seconds}
    properties["model"] = {"type": "string", "default": None, "enum": model_names}
    properties["session_dir"] = {"type": "string", "default": None}
    properties["tools"] = {"type": "array", "items": {"type": "string", "enum": ["bash", "read", "edit", "write", "grep", "find"]}, "default": node.tools}
    for key, value in node.parameters_schema.get("properties", {}).items():
        if isinstance(value, dict):
            properties[f"param.{key}"] = value
    return {"type": "object", "properties": properties}


def entities_response(entity_types: dict[str, EntityTypeConfig], entities: EntitiesConfig) -> dict[str, object]:
    return {"entity_types": entity_types_payload(entity_types), "entities": entity_list_payload(entity_types, entities)}


def entity_payload(entity_types: dict[str, EntityTypeConfig], entity: EntityConfig) -> dict[str, object]:
    item = entity.model_dump(mode="json")
    item["ref"] = entity_ref(entity, entity_types)
    item["display"] = render_entity_display(entity, entity_types[entity.type])
    return item


def entity_types_payload(entity_types: dict[str, EntityTypeConfig]) -> dict[str, object]:
    return {name: entity_type.model_dump(mode="json", by_alias=True) for name, entity_type in entity_types.items()}


def entity_list_payload(entity_types: dict[str, EntityTypeConfig], entities: EntitiesConfig) -> list[dict[str, object]]:
    return [entity_payload(entity_types, entity) for entity in entities.entities]


def resolve_entity(entities: EntitiesConfig, entity_types: dict[str, EntityTypeConfig], ref: str) -> EntityConfig:
    for entity in entities.entities:
        if ref == entity.id or ref == entity_ref(entity, entity_types):
            return entity
    raise ConfigError(f"Entity not found: {ref}")


def entity_ref_from_any(entities: EntitiesConfig, entity_types: dict[str, EntityTypeConfig], ref: str) -> str:
    return entity_ref(resolve_entity(entities, entity_types, ref), entity_types)


def render_entity_display(entity: EntityConfig, entity_type: EntityTypeConfig) -> str:
    try:
        return entity_type.display_template.format(**entity.attributes)
    except KeyError:
        return str(entity.attributes.get(entity_type.business_id_field, entity.id))


def source_ref_for_name(entities: EntitiesConfig, entity_types: dict[str, EntityTypeConfig], name: str) -> str:
    for entity in entities.entities:
        if entity.type in {"rss-source", "web-source", "api-source"} and entity.attributes.get("name") == name:
            return entity_ref(entity, entity_types)
    return name


def available_model_names() -> list[str]:
    model_file = Path.home() / ".pi" / "agent" / "models.json"
    if not model_file.exists():
        return []
    try:
        data = json.loads(model_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return sorted(extract_model_names(data))


def extract_model_names(data: object) -> set[str]:
    if isinstance(data, list):
        return {str(item.get("id") or item.get("name")) for item in data if isinstance(item, dict) and (item.get("id") or item.get("name"))}
    if isinstance(data, dict):
        if isinstance(data.get("models"), list):
            return extract_model_names(data["models"])
        return {str(key) for key, value in data.items() if isinstance(key, str) and value is not None}
    return set()


def split_instance_config(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    payload: dict[str, object] = {}
    parameters = dict(raw.get("parameters", {})) if isinstance(raw.get("parameters"), dict) else {}
    for key, value in raw.items():
        if key == "parameters":
            continue
        if key.startswith("param."):
            if value is not None:
                parameters[key.removeprefix("param.")] = value
            continue
        payload[key] = value
    if parameters:
        payload["parameters"] = parameters
    return payload


def save_node_assets(root: Path, payload: dict[str, object], body: dict[str, object]) -> None:
    if payload.get("type") != "function":
        return
    handler = payload.get("handler")
    code = body.get("handler_code", body.get("code"))
    if isinstance(handler, str) and isinstance(code, str):
        path = root / "extensions" / handler / "handler.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code, encoding="utf-8")


def delete_node_assets(root: Path, node: NodeConfig) -> None:
    if node.type == "function" and node.handler:
        (root / "extensions" / node.handler / "handler.py").unlink(missing_ok=True)


def save_skill(root: Path, path: Path, body: dict[str, object]) -> dict[str, object]:
    raw_handler = body.get("handler", body.get("name"))
    code = body.get("handler_code", body.get("code"))
    handler = body.get("name") if isinstance(raw_handler, str) and "\n" in raw_handler else raw_handler
    if not isinstance(code, str) and isinstance(raw_handler, str) and "\n" in raw_handler:
        code = raw_handler
    payload = SkillConfig.model_validate({"name": body.get("name"), "description": body.get("description", ""), "handler": handler, "parameters_schema": body.get("parameters_schema", {})})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload.model_dump(mode="json"), allow_unicode=True, sort_keys=False), encoding="utf-8")
    if isinstance(code, str):
        handler_path = root / "extensions" / payload.handler / "handler.py"
        handler_path.parent.mkdir(parents=True, exist_ok=True)
        handler_path.write_text(code, encoding="utf-8")
    return {"skill": payload.model_dump(mode="json")}
