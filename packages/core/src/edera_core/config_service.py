from __future__ import annotations

import grpc
import json
import logging
import yaml

from edera_core.config.editor import ConfigEditError
from edera_core.config.loader import CORE_ENTITY_TYPES, _load_runtime_base_config, load_entity_type_configs
from edera_core.config.schema import EntitiesConfig, EntityConfig, EntityRelationsConfig, EntityTypeConfig
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


LOGGER = logging.getLogger(__name__)


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
        snapshot = _runtime_snapshot_or_none(self.daemon)
        if snapshot is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "runtime snapshot not found")
        content = yaml.safe_dump(snapshot.config.entities.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        return json_response(self.pb2, {"content": content})

    async def SaveEntitiesConfig(self, request, context):
        try:
            body = json.loads(request.json or "{}")
            entities = EntitiesConfig.model_validate(body)
            snapshot = _runtime_snapshot_or_none(self.daemon)
            if snapshot is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, "runtime snapshot not found")
            async with self.daemon.controller._factory()() as session:
                for entity in entities.entities:
                    await _save_entity_to_db(session, entity, snapshot.config.entity_types)
                await session.commit()
            await _refresh_runtime_snapshot(self.daemon)
            snapshot = self.daemon.controller.runtime_snapshot()
            response = entities_response(snapshot.config.entity_types, snapshot.config.entities)
        except (ConfigEditError, ConfigError, ValueError, json.JSONDecodeError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, response)

    async def ListEntityTypes(self, request, context):
        try:
            return json_response(self.pb2, {"types": entity_types_payload(load_entity_type_configs(self.daemon.config_dir.parent / "schemas" / "entity-types"))})
        except (ConfigError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

    async def ReloadEntityTypes(self, request, context):
        identity = _metadata_identity(context)
        if not _is_admin(identity):
            await context.abort(grpc.StatusCode.PERMISSION_DENIED, "reload entity types requires admin")
        count = await self.daemon.controller.reload_entity_types()
        LOGGER.info("ReloadEntityTypes called by user=%s, loaded %s entity types", identity, count)
        return json_response(self.pb2, {"reloaded": True, "count": count})

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
            path.unlink()
        except (ConfigEditError, ConfigError, OSError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"deleted": True, "instances_removed": len(matching)})

    async def ReadEntityRelationsConfig(self, request, context):
        snapshot = _runtime_snapshot_or_none(self.daemon)
        if snapshot is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "runtime snapshot not found")
        content = yaml.safe_dump(snapshot.config.entity_relations.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        return json_response(self.pb2, {"content": content})

    async def SaveEntityRelationsConfig(self, request, context):
        try:
            body = json.loads(request.json or "{}")
            relations = EntityRelationsConfig.model_validate(body)
            snapshot = _runtime_snapshot_or_none(self.daemon)
            if snapshot is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, "runtime snapshot not found")
            async with self.daemon.controller._factory()() as session:
                from edera_core.storage.repository import create_relation

                for relation in relations.relations:
                    if len(relation.entities) != 2:
                        raise ConfigError("relation must reference exactly two entities")
                    await create_relation(session, relation.entities[0], relation.entities[1], relation.type, relation.metadata, snapshot.config.entity_types)
                await session.commit()
            await _refresh_runtime_snapshot(self.daemon)
            relations = self.daemon.controller.runtime_snapshot().config.entity_relations
        except (ConfigEditError, ConfigError, ValueError, json.JSONDecodeError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"relations": [relation.model_dump(mode="json") for relation in relations.relations]})

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
            if len(refs) != 2:
                raise ConfigError("relation must reference exactly two entities")
            snapshot = _runtime_snapshot_or_none(self.daemon)
            if snapshot is None:
                await context.abort(grpc.StatusCode.NOT_FOUND, "runtime snapshot not found")
            async with self.daemon.controller._factory()() as session:
                from edera_core.storage.repository import create_relation

                relation = await create_relation(session, refs[0], refs[1], relation_type, dict(metadata), snapshot.config.entity_types)
                await session.commit()
            await _refresh_runtime_snapshot(self.daemon)
        except ConfigError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(
            self.pb2,
            {
                "relation": {
                    "id": relation.id,
                    "entities": [relation.from_entity_id, relation.to_entity_id],
                    "type": relation.relation_type,
                    "metadata": relation.metadata_,
                }
            },
        )

    async def DeleteEntityRelation(self, request, context):
        try:
            async with self.daemon.controller._factory()() as session:
                from edera_core.storage.repository import delete_relation

                deleted = await delete_relation(session, request.name)
                await session.commit()
            if not deleted:
                await context.abort(grpc.StatusCode.NOT_FOUND, f"Entity relation not found: {request.name}")
            await _refresh_runtime_snapshot(self.daemon)
        except ConfigError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except ConfigEditError as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return json_response(self.pb2, {"deleted": True})


async def _save_entity_to_db(session, entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> None:
    if entity.type == "relation":
        from edera_core.storage.repository import create_relation

        from_entity_id = str(entity.attributes.get("from_entity_id") or entity.attributes.get("from") or "")
        to_entity_id = str(entity.attributes.get("to_entity_id") or entity.attributes.get("to") or "")
        relation_type = str(entity.attributes.get("relation_type") or "")
        if not from_entity_id or not to_entity_id or not relation_type:
            raise ConfigError("relation entity requires from_entity_id, to_entity_id and relation_type")
        await create_relation(session, from_entity_id, to_entity_id, relation_type, dict(entity.attributes.get("metadata") or {}), entity_types)
        return
    if entity.type in CORE_ENTITY_TYPES:
        from edera_core.storage.repository import save_core_entity

        await save_core_entity(session, entity)
        return
    entity_type = entity_types.get(entity.type)
    if entity_type is None:
        raise ConfigError(f"unknown entity type: {entity.type}")
    from edera_core.storage.repository import save_ordinary_entity

    await save_ordinary_entity(session, entity, entity_type)


async def _refresh_runtime_snapshot(daemon) -> None:
    refresh = getattr(daemon.controller, "refresh", None)
    if refresh is not None:
        await refresh()
        return
    if getattr(daemon.controller, "engine", None) is None:
        return
    config = _load_runtime_base_config(daemon.config_dir)
    await daemon.controller.install_snapshot(config, daemon.controller.runtime_snapshot().bootstrap)


def _metadata_identity(context) -> str | None:
    for key, value in context.invocation_metadata():
        if key == "x-edera-identity" and value:
            return str(value)
    return None


def _is_admin(identity: str | None) -> bool:
    return identity == "admin" or bool(identity and identity.startswith("admin:"))


def _runtime_snapshot_or_none(daemon):
    controller = getattr(daemon, "controller", None)
    if controller is None:
        return None
    try:
        return controller.runtime_snapshot()
    except Exception:
        return None
