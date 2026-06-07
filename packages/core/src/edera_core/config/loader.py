from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any

import yaml

from edera_core.config.schema import (
    AppConfig,
    DagConfig,
    EntitiesConfig,
    EntityConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    NodeConfig,
    RuntimeSettings,
    SystemConfig,
)
from edera_core.errors import ConfigError


LOGGER = logging.getLogger(__name__)
CORE_ENTITY_TYPES = {"node", "dag", "trigger", "resource"}


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"config file must contain a mapping: {path}")
    return data


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    return tomllib.loads(path.read_text())


def load_system_config(path: Path) -> SystemConfig:
    return SystemConfig.model_validate(_read_toml(path))


def load_entity_type_configs(path: Path) -> dict[str, EntityTypeConfig]:
    configs: dict[str, EntityTypeConfig] = {}
    paths = [path]
    legacy_peer = path.parent.parent / "config" / "schemas"
    if path.parts[-2:] == ("schemas", "entity-types") and legacy_peer.exists():
        paths.append(legacy_peer)
    for schema_path in paths:
        for file in sorted(schema_path.glob("*.yaml")):
            configs[file.stem] = EntityTypeConfig.model_validate(_read_yaml(file))
    if not configs:
        raise ConfigError(f"missing entity type schemas: {path}")
    return configs


def load_entity_types(config_dir: Path) -> dict[str, EntityTypeConfig]:
    legacy = config_dir.parent / "schemas" / "entity-types"
    local = config_dir / "schemas"
    if (config_dir / "schemas").exists():
        return {**load_entity_type_configs(legacy), **load_entity_type_configs(local)}
    return load_entity_type_configs(legacy)


def load_node_configs(path: Path) -> dict[str, NodeConfig]:
    configs: dict[str, NodeConfig] = {}
    root = path.parent.parent
    store = _entity_store_or_none(path.parent)
    entities = store.query("node") if store is not None else [_entity_from_file(file, "node") for file in sorted(path.glob("*.yaml"))]
    for entity in entities:
        node = NodeConfig.model_validate(entity.attributes)
        system_prompt_file = getattr(node, "system_prompt_file", None)
        if system_prompt_file:
            prompt_path = root / system_prompt_file
            if prompt_path.exists():
                node.system_prompt = prompt_path.read_text(encoding="utf-8")
        configs[node.name] = node
    return configs


def load_dag_config(path: Path) -> DagConfig:
    raw = _read_yaml(path)
    if raw.get("type") == "dag" and isinstance(raw.get("attributes"), dict):
        attrs = dict(raw["attributes"])
        attrs.setdefault("name", raw.get("id", path.stem))
        return DagConfig.model_validate(attrs)
    return DagConfig.model_validate(raw)


def load_dag_configs(path: Path) -> dict[str, DagConfig]:
    configs: dict[str, DagConfig] = {}
    store = _entity_store_or_none(path.parent)
    if store is None:
        for file in sorted(path.glob("*.yaml")):
            dag = load_dag_config(file)
            configs[dag.name] = dag
        return configs
    for entity in store.query("dag"):
        attrs = dict(entity.attributes)
        attrs.setdefault("name", entity.id)
        dag = DagConfig.model_validate(attrs)
        configs[dag.name] = dag
    return configs


def load_app_config(config_dir: Path = Path("config")) -> AppConfig:
    entity_types = load_entity_types(config_dir)
    dags = load_dag_configs(config_dir / "dags")
    system = load_system_config(config_dir / "system.toml")
    from edera_core.dag.loader import validate_sub_dag_nesting

    validate_sub_dag_nesting(dags, system.max_dag_depth)
    _validate_dag_entity_permissions(dags, entity_types)
    return AppConfig(
        system=system,
        entity_types=entity_types,
        entities=EntitiesConfig(),
        entity_relations=EntityRelationsConfig(),
        runtime=RuntimeSettings(),
        nodes=load_node_configs(config_dir / "nodes"),
        skills={},
        dags=dags,
    )


async def load_runtime_app_config(config_dir: Path, engine, extensions_dirs: list[Path] | None = None) -> AppConfig:
    config = _load_runtime_base_config(config_dir)
    from edera_core.bootstrap import load_installed_extensions
    from edera_core.migration.migrate_extensions import migrate_existing_extensions
    from edera_core.storage import session_factory

    async with session_factory(engine)() as session:
        if extensions_dirs is not None:
            await migrate_existing_extensions(
                session,
                extensions_dirs,
                handlers_dir=config_dir.parent / "handlers",
                entity_types=config.entity_types,
            )
            await session.commit()
        await load_installed_extensions(session, config_dir.parent / "handlers")
    return await materialize_runtime_app_config(config_dir, config, engine)


def _load_runtime_base_config(config_dir: Path) -> AppConfig:
    entity_types = _runtime_entity_types(load_entity_types(config_dir))
    return AppConfig(
        system=load_system_config(config_dir / "system.toml"),
        entity_types=entity_types,
        entities=EntitiesConfig(),
        entity_relations=EntityRelationsConfig(),
        runtime=RuntimeSettings(),
        nodes={},
        skills={},
        dags={},
    )


def _default_extensions_dirs(config_dir: Path) -> list[Path]:
    local = config_dir / "extensions"
    sibling = config_dir.parent / "extensions"
    return [local, sibling] if local != sibling else [local]


async def materialize_runtime_app_config(
    config_dir: Path,
    config: AppConfig,
    engine,
    extension_imports: list[tuple[Path, object]] | None = None,
) -> AppConfig:
    config.entity_types = _runtime_entity_types(config.entity_types)
    from edera_core.storage import session_factory
    from edera_core.storage.repository import (
        list_core_entities,
        list_entity_type_configs,
        list_skill_configs,
        seed_entity_type_records,
    )

    factory = session_factory(engine)
    migrated_files: list[tuple[Path, Path]] = []
    async with factory() as session:
        config.entity_types = await seed_entity_type_records(session, config.entity_types)
        try:
            migrated_files = await _migrate_legacy_entity_yaml(session, config_dir, config.entity_types)
        except Exception:
            await session.rollback()
            LOGGER.exception("legacy entity YAML migration failed")
            migrated_files = []
            config.entity_types = await seed_entity_type_records(session, config.entity_types)
        from edera_core.storage.repository import save_core_entity

        existing_core = {entity.id for entity in await list_core_entities(session)}
        for entity in _top_level_core_entities(config_dir):
            if entity.id in existing_core:
                continue
            await save_core_entity(session, entity)
        if extension_imports:
            from edera_core.extension_imports import import_manifest_entities

            for extension_root, manifest in extension_imports:
                await import_manifest_entities(session, extension_root, manifest, config.entity_types)
        for entity in config.entities.entities:
            if entity.type in CORE_ENTITY_TYPES:
                continue
            entity_type = config.entity_types.get(entity.type)
            if entity_type is None or entity_type.storage_tier != "database":
                continue
            from edera_core.storage.repository import save_ordinary_entity

            await save_ordinary_entity(session, entity, entity_type)
        db_entity_types = await list_entity_type_configs(session)
        skills = await list_skill_configs(session)
        await session.commit()
    for source, target in migrated_files:
        source.rename(target)
    config.entity_types = {**config.entity_types, **db_entity_types}
    config.entities = EntitiesConfig()
    config.entity_relations = EntityRelationsConfig()
    config.skills = skills
    config.nodes = {}
    config.dags = {}
    return config


async def _migrate_legacy_entity_yaml(
    session,
    config_dir: Path,
    entity_types: dict[str, EntityTypeConfig],
) -> list[tuple[Path, Path]]:
    entities_path = config_dir / "entities.yaml"
    relations_path = config_dir / "entity-relations.yaml"
    migrated: list[tuple[Path, Path]] = []
    if entities_path.exists():
        from edera_core.storage.import_export import import_entities_from_yaml

        await import_entities_from_yaml(session, entities_path, entity_types)
        migrated.append((entities_path, config_dir / "entities.yaml.migrated"))
    if relations_path.exists():
        from edera_core.storage.import_export import import_relations_from_yaml

        await import_relations_from_yaml(session, relations_path, entity_types)
        migrated.append((relations_path, config_dir / "entity-relations.yaml.migrated"))
    await session.flush()
    return migrated


def _top_level_core_entities(config_dir: Path) -> list[EntityConfig]:
    entities: list[EntityConfig] = []
    for entity_type, directory_name in (
        ("node", "nodes"),
        ("dag", "dags"),
        ("trigger", "triggers"),
        ("resource", "resources"),
    ):
        directory = config_dir / directory_name
        if not directory.exists():
            continue
        entities.extend(_entity_from_file(file, entity_type) for file in sorted(directory.glob("*.yaml")))
    return entities


def load_config(config_dir: Path = Path("config")) -> AppConfig:
    return load_app_config(config_dir)


def _validate_dag_entity_permissions(
    dags: dict[str, DagConfig],
    entity_types: dict[str, EntityTypeConfig],
) -> None:
    from edera_core.config.entities import validate_permission_overrides

    for dag in dags.values():
        for instance in dag.nodes:
            permissions = instance.config.get("entity_permissions")
            if isinstance(permissions, dict):
                validate_permission_overrides(entity_types, permissions)


def _validate_entities(
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
) -> None:
    ids: set[str] = set()
    business_refs: set[str] = set()
    for entity in entities.entities:
        if entity.id in ids:
            raise ConfigError(f"duplicate entity id: {entity.id}")
        ids.add(entity.id)
        entity_type = entity_types.get(entity.type)
        if entity_type is None:
            raise ConfigError(f"unknown entity type: {entity.type}")
        business_id = entity.id if entity_type.business_id_field == "id" else entity.attributes.get(entity_type.business_id_field)
        if not isinstance(business_id, str) or not business_id:
            raise ConfigError(f"entity {entity.id} missing business id field: {entity_type.business_id_field}")
        ref = f"{entity.type}:{business_id}"
        if ref in business_refs:
            raise ConfigError(f"duplicate entity business ref: {ref}")
        business_refs.add(ref)
        if entity_type.validate_:
            _validate_entity_attributes(entity, entity_type)


def _validate_entity_attributes(entity: EntityConfig, entity_type: EntityTypeConfig) -> None:
    schema = entity_type.schema_
    required = schema.get("required")
    if isinstance(required, list):
        missing = [field for field in required if isinstance(field, str) and field not in entity.attributes]
        if missing:
            raise ConfigError(f"entity {entity.id} missing required attributes: {', '.join(missing)}")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return
    for key, field_schema in properties.items():
        if key not in entity.attributes or not isinstance(field_schema, dict):
            continue
        expected = field_schema.get("type")
        value = entity.attributes[key]
        if expected == "string" and not isinstance(value, str):
            raise ConfigError(f"entity {entity.id}.{key} must be string")
        if expected == "number" and not isinstance(value, int | float):
            raise ConfigError(f"entity {entity.id}.{key} must be number")
        if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
            raise ConfigError(f"entity {entity.id}.{key} must be integer")
        minimum = field_schema.get("minimum")
        if isinstance(minimum, int | float) and isinstance(value, int | float) and value < minimum:
            raise ConfigError(f"entity {entity.id}.{key} must be >= {minimum:g}")
        if expected == "boolean" and not isinstance(value, bool):
            raise ConfigError(f"entity {entity.id}.{key} must be boolean")
        if expected == "object" and not isinstance(value, dict):
            raise ConfigError(f"entity {entity.id}.{key} must be object")
        if expected == "array" and not isinstance(value, list):
            raise ConfigError(f"entity {entity.id}.{key} must be array")


def _entity_from_file(path: Path, forced_type: str | None) -> EntityConfig:
    raw = _read_yaml(path)
    if "type" in raw and "attributes" in raw:
        return EntityConfig.model_validate(raw)
    entity_type = forced_type or str(raw.get("type") or path.parent.name.rstrip("s"))
    attrs = dict(raw)
    attrs.setdefault("name", path.stem)
    return EntityConfig(id=str(raw.get("id") or path.stem), type=entity_type, attributes=attrs)


def _node_from_entity(raw: dict[str, Any], fallback_name: str) -> NodeConfig:
    if raw.get("type") == "node" and isinstance(raw.get("attributes"), dict):
        attrs = dict(raw["attributes"])
        attrs.setdefault("name", raw.get("id", fallback_name))
        return NodeConfig.model_validate(attrs)
    return NodeConfig.model_validate(raw)


def _entity_store(config_dir: Path):
    from edera_core.config.entities import EntityStore

    config = load_app_config(config_dir)
    return EntityStore(config.entities, config.entity_types, config.entity_relations, None)


def _entity_store_from_config(config: AppConfig, config_dir: Path):
    from edera_core.config.entities import EntityStore

    return EntityStore(config.entities, config.entity_types, config.entity_relations, None)


def _runtime_entity_types(entity_types: dict[str, EntityTypeConfig]) -> dict[str, EntityTypeConfig]:
    result = dict(entity_types)
    for name, entity_type in _default_core_entity_types().items():
        result.setdefault(name, entity_type)
    result.setdefault("relation", _default_relation_entity_type())
    for name in CORE_ENTITY_TYPES:
        entity_type = result.get(name)
        if entity_type is not None:
            result[name] = entity_type.model_copy(update={"storage_tier": "database"})
    relation = result.get("relation")
    if relation is not None:
        result["relation"] = relation.model_copy(update={"business_id_field": "id", "storage_tier": "database"})
    return result


def _default_relation_entity_type() -> EntityTypeConfig:
    return EntityTypeConfig.model_validate(
        {
            "display_name": "Relation",
            "business_id_field": "id",
            "display_template": "{from} -> {to}",
            "storage_tier": "database",
            "schema": {
                "required": ["from", "to", "relation_type"],
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "relation_type": {"type": "string"},
                    "metadata": {"type": "object"},
                },
            },
        }
    )


def _default_core_entity_types() -> dict[str, EntityTypeConfig]:
    return {
        "node": EntityTypeConfig.model_validate(
            {
                "display_name": "Node",
                "business_id_field": "name",
                "display_template": "{name}",
                "system_protected": True,
                "schema": {
                    "required": ["name", "type", "input_type", "output_type"],
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string"},
                        "role": {"type": "string"},
                        "handler": {"type": "string"},
                        "input_type": {"type": "string"},
                        "output_type": {"type": "string"},
                    },
                },
            }
        ),
        "dag": EntityTypeConfig.model_validate(
            {
                "display_name": "DAG",
                "business_id_field": "name",
                "display_template": "{name}",
                "system_protected": True,
                "schema": {
                    "required": ["name", "nodes", "edges"],
                    "properties": {
                        "name": {"type": "string"},
                        "nodes": {"type": "array"},
                        "edges": {"type": "array"},
                        "ui": {"type": "object"},
                    },
                },
            }
        ),
        "trigger": EntityTypeConfig.model_validate(
            {
                "display_name": "Trigger",
                "business_id_field": "name",
                "display_template": "{name}",
                "system_protected": True,
                "schema": {
                    "required": ["name", "wait_for", "target"],
                    "properties": {
                        "name": {"type": "string"},
                        "wait_for": {"type": "string"},
                        "target": {"type": "string"},
                        "enabled": {"type": "boolean"},
                    },
                },
            }
        ),
        "resource": EntityTypeConfig.model_validate(
            {
                "display_name": "Resource",
                "business_id_field": "id",
                "display_template": "{id}",
                "system_protected": True,
                "schema": {
                    "required": ["permits"],
                    "properties": {
                        "permits": {"type": "integer", "minimum": 1},
                    },
                },
            }
        ),
    }


def _nodes_from_core_entities(config_dir: Path, entities: list[EntityConfig]) -> dict[str, NodeConfig]:
    root = config_dir.parent
    nodes: dict[str, NodeConfig] = {}
    for entity in entities:
        if entity.type != "node":
            continue
        node = NodeConfig.model_validate(entity.attributes)
        system_prompt_file = getattr(node, "system_prompt_file", None)
        if system_prompt_file:
            prompt_path = root / system_prompt_file
            if prompt_path.exists():
                node.system_prompt = prompt_path.read_text(encoding="utf-8")
        nodes[node.name] = node
    return nodes


def _dags_from_core_entities(entities: list[EntityConfig]) -> dict[str, DagConfig]:
    dags: dict[str, DagConfig] = {}
    for entity in entities:
        if entity.type != "dag":
            continue
        attrs = dict(entity.attributes)
        attrs.setdefault("name", entity.id)
        dag = DagConfig.model_validate(attrs)
        dags[dag.name] = dag
    return dags


def _core_entities_from_config(config: AppConfig, entity_type: str) -> list[EntityConfig]:
    if entity_type == "node":
        return [
            EntityConfig(id=node.name, type="node", attributes=node.model_dump(mode="json"))
            for node in config.nodes.values()
        ]
    if entity_type == "dag":
        return [
            EntityConfig(id=dag.name, type="dag", attributes=dag.model_dump(mode="json", by_alias=True))
            for dag in config.dags.values()
        ]
    return []


def _entity_store_or_none(config_dir: Path):
    return None
