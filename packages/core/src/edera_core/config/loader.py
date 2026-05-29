from __future__ import annotations

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
    SkillConfig,
    SystemConfig,
)
from edera_core.errors import ConfigError


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


def load_entities_config(
    path: Path,
    entity_types: dict[str, EntityTypeConfig],
) -> EntitiesConfig:
    entities = EntitiesConfig.model_validate(_read_yaml(path))
    entity_dir = path.parent / "entities"
    for file in sorted(entity_dir.glob("*.yaml")):
        entities.entities.append(_entity_from_file(file, None))
    _validate_entities(entities, entity_types)
    return entities


def load_entity_relations_config(
    path: Path,
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
) -> EntityRelationsConfig:
    raw = _read_yaml(path)
    relations = EntityRelationsConfig.model_validate(raw)
    refs = _entity_refs(entities, entity_types)
    for relation in relations.relations:
        for ref in relation.entities:
            if ref not in refs:
                raise ConfigError(f"Entity not found: {ref}")
    if any(isinstance(item, dict) and "id" not in item for item in raw.get("relations", [])):
        path.write_text(
            yaml.safe_dump(relations.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return relations


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


def load_skill_configs(path: Path) -> dict[str, SkillConfig]:
    configs: dict[str, SkillConfig] = {}
    if not path.exists():
        return configs
    for file in sorted(path.glob("*.yaml")):
        skill = SkillConfig.model_validate(_read_yaml(file))
        configs[skill.name] = skill
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
    entities = load_entities_config(config_dir / "entities.yaml", entity_types)
    entity_relations = load_entity_relations_config(
        config_dir / "entity-relations.yaml",
        entities,
        entity_types,
    )
    dags = load_dag_configs(config_dir / "dags")
    system = load_system_config(config_dir / "system.toml")
    from edera_core.dag.loader import validate_sub_dag_nesting

    validate_sub_dag_nesting(dags, system.max_dag_depth)
    _validate_dag_entity_permissions(dags, entity_types)
    return AppConfig(
        system=system,
        entity_types=entity_types,
        entities=entities,
        entity_relations=entity_relations,
        runtime=RuntimeSettings(),
        nodes=load_node_configs(config_dir / "nodes"),
        skills=load_skill_configs(config_dir / "skills"),
        dags=dags,
    )


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

    entity_types = load_entity_types(config_dir)
    entities = load_entities_config(config_dir / "entities.yaml", entity_types)
    relations = load_entity_relations_config(config_dir / "entity-relations.yaml", entities, entity_types)
    return EntityStore(entities, entity_types, relations, config_dir / "entities.yaml")


def _entity_store_or_none(config_dir: Path):
    if not (config_dir.parent / "schemas" / "entity-types").exists() and not (config_dir / "schemas").exists():
        return None
    if not (config_dir / "entities.yaml").exists() or not (config_dir / "entity-relations.yaml").exists():
        return None
    schema_dir = config_dir / "schemas" if (config_dir / "schemas").exists() else config_dir.parent / "schemas" / "entity-types"
    if not (schema_dir / "node.yaml").exists() or not (schema_dir / "dag.yaml").exists():
        return None
    try:
        return _entity_store(config_dir)
    except ConfigError:
        raise


def _entity_refs(
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
) -> set[str]:
    refs = {entity.id for entity in entities.entities}
    for entity in entities.entities:
        entity_type = entity_types[entity.type]
        business_id = entity.id if entity_type.business_id_field == "id" else entity.attributes[entity_type.business_id_field]
        refs.add(f"{entity.type}:{business_id}")
    return refs
