from __future__ import annotations

import grpc
import json
import yaml

from edera_core.config.editor import ConfigEditError
from edera_core.config.loader import load_entities_config, load_entity_relations_config, load_entity_type_configs
from edera_core.config.schema import EntitiesConfig, EntityRelationsConfig, EntityTypeConfig, entity_ref
from edera_core.errors import ConfigError
from edera_core.service_common import (
    atomic_write,
    editor,
    entities_response,
    entity_store,
    entity_type_config,
    entity_type_path,
    entity_types_payload,
    json_response,
    kind,
    resolve_entity_type_path,
    validate_entity_type_content,
)


class _ConfigService:
    def __init__(self, daemon) -> None:
        self.daemon = daemon
        self.pb2 = daemon.pb2

    async def ListConfigs(self, request, context):
        return json_response(self.pb2, {"files": [file.__dict__ for file in editor(self.daemon.config_dir).list_files()]})

    async def ReadSystemConfig(self, request, context):
        path = self.daemon.config_dir / "system.toml"
        if not path.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, "system.toml not found")
        return json_response(self.pb2, {"content": path.read_text(encoding="utf-8")})

    async def SaveSystemConfig(self, request, context):
        try:
            saved = editor(self.daemon.config_dir).save("system", "system", request.content)
        except ConfigEditError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"file": saved.__dict__, "content": saved.content})

    async def ReadConfig(self, request, context):
        try:
            return json_response(self.pb2, {"file": editor(self.daemon.config_dir).read(kind(request.kind), request.name).__dict__})
        except ConfigEditError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    async def SaveConfig(self, request, context):
        try:
            return json_response(
                self.pb2,
                {"file": editor(self.daemon.config_dir).save(kind(request.kind), request.name, request.content).__dict__},
            )
        except ConfigEditError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    async def ReadEntitiesConfig(self, request, context):
        path = self.daemon.config_dir / "entities.yaml"
        if not path.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, "entities.yaml not found")
        return json_response(self.pb2, {"content": path.read_text(encoding="utf-8")})

    async def SaveEntitiesConfig(self, request, context):
        try:
            body = json.loads(request.json or "{}")
            content = yaml.safe_dump(EntitiesConfig.model_validate(body).model_dump(mode="json"), allow_unicode=True, sort_keys=False)
            saved = editor(self.daemon.config_dir).save("entities", "entities", content)
            root = self.daemon.config_dir
            entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
            entities = load_entities_config(root / "entities.yaml", entity_types)
            response = entities_response(entity_types, entities)
            response["file"] = saved.__dict__
        except (ConfigEditError, ConfigError, json.JSONDecodeError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, response)

    async def ListEntityTypes(self, request, context):
        try:
            return json_response(self.pb2, {"types": entity_types_payload(load_entity_type_configs(self.daemon.config_dir.parent / "schemas" / "entity-types"))})
        except ConfigError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    async def CreateEntityType(self, request, context):
        name = request.name.strip()
        if not name:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "entity type name is required")
        path = entity_type_path(self.daemon.config_dir, name)
        if path.exists():
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, f"entity type '{name}' already exists")
        try:
            validate_entity_type_content(request.content)
            atomic_write(path, request.content)
        except (ConfigEditError, yaml.YAMLError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"created": True, "name": name})

    async def GetEntityType(self, request, context):
        path = resolve_entity_type_path(self.daemon.config_dir, request.name)
        if not path.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, f"entity type {request.name} not found")
        return json_response(self.pb2, {"name": request.name, "content": path.read_text(encoding="utf-8")})

    async def SaveEntityType(self, request, context):
        path = entity_type_path(self.daemon.config_dir, request.name)
        try:
            current = entity_type_config(self.daemon.config_dir, request.name)
        except ConfigError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        if current is not None and current.system_protected:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, f"entity type '{request.name}' is system protected")
        if not path.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, f"entity type {request.name} not found")
        try:
            validate_entity_type_content(request.content)
            atomic_write(path, request.content)
        except (ConfigEditError, yaml.YAMLError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"updated": True, "name": request.name})

    async def DeleteEntityType(self, request, context):
        root = self.daemon.config_dir
        path = entity_type_path(root, request.name)
        try:
            current = entity_type_config(root, request.name)
        except ConfigError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        if current is not None and current.system_protected:
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, f"entity type '{request.name}' is system protected")
        if not path.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, f"entity type {request.name} not found")
        store = entity_store(root)
        matching = [entity for entity in store.entities.entities if entity.type == request.name]
        if matching and not request.cascade:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"entity type '{request.name}' has {len(matching)} instances")
        try:
            removed_refs = {ref for entity in matching for ref in (entity.id, entity_ref(entity, store.entity_types))}
            store.entities.entities = [entity for entity in store.entities.entities if entity.type != request.name]
            store.relations.relations = [relation for relation in store.relations.relations if not any(ref in removed_refs for ref in relation.entities)]
            editor(root).save("entities", "entities", yaml.safe_dump(store.entities.model_dump(mode="json"), allow_unicode=True, sort_keys=False))
            editor(root).save("entity-relations", "entity-relations", yaml.safe_dump(store.relations.model_dump(mode="json"), allow_unicode=True, sort_keys=False))
            path.unlink()
        except (ConfigEditError, ConfigError, OSError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"deleted": True, "instances_removed": len(matching)})

    async def ReadEntityRelationsConfig(self, request, context):
        path = self.daemon.config_dir / "entity-relations.yaml"
        if not path.exists():
            await context.abort(grpc.StatusCode.NOT_FOUND, "entity-relations.yaml not found")
        return json_response(self.pb2, {"content": path.read_text(encoding="utf-8")})

    async def SaveEntityRelationsConfig(self, request, context):
        try:
            body = json.loads(request.json or "{}")
            content = yaml.safe_dump(EntityRelationsConfig.model_validate(body).model_dump(mode="json"), allow_unicode=True, sort_keys=False)
            saved = editor(self.daemon.config_dir).save("entity-relations", "entity-relations", content)
            root = self.daemon.config_dir
            entity_types = load_entity_type_configs(root.parent / "schemas" / "entity-types")
            entities = load_entities_config(root / "entities.yaml", entity_types)
            relations = load_entity_relations_config(root / "entity-relations.yaml", entities, entity_types)
        except (ConfigEditError, ConfigError, json.JSONDecodeError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"file": saved.__dict__, "relations": [relation.model_dump(mode="json") for relation in relations.relations]})

    async def CreateEntityRelation(self, request, context):
        try:
            body = json.loads(request.json or "{}")
        except json.JSONDecodeError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        refs = body.get("entities", [])
        relation_type = str(body.get("type", ""))
        metadata = body.get("metadata", {})
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "entities must be a list of strings")
        if not relation_type:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "relation type is required")
        if not isinstance(metadata, dict):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "metadata must be a mapping")
        try:
            relation = entity_store(self.daemon.config_dir).create_relation(refs, relation_type, dict(metadata))
        except ConfigEditError as exc:
            await context.abort(grpc.StatusCode.ALREADY_EXISTS, str(exc))
        except ConfigError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"relation": relation.model_dump(mode="json")})

    async def DeleteEntityRelation(self, request, context):
        try:
            entity_store(self.daemon.config_dir).delete_relation(request.name)
        except ConfigError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ConfigEditError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"deleted": True})
