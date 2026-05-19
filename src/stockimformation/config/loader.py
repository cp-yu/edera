from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import yaml

from stockimformation.config.schema import (
    AppConfig,
    DagConfig,
    EntitiesConfig,
    EntityConfig,
    EntityRelationsConfig,
    EntityTypeConfig,
    NodeConfig,
    PortfolioConfig,
    RuntimeSettings,
    SkillConfig,
    SystemConfig,
)
from stockimformation.errors import ConfigError


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


def load_portfolio_config(path: Path) -> PortfolioConfig:
    return PortfolioConfig.model_validate(_read_yaml(path))


def load_entity_type_configs(path: Path) -> dict[str, EntityTypeConfig]:
    configs: dict[str, EntityTypeConfig] = {}
    for file in sorted(path.glob("*.yaml")):
        configs[file.stem] = EntityTypeConfig.model_validate(_read_yaml(file))
    if not configs:
        raise ConfigError(f"missing entity type schemas: {path}")
    return configs


def load_entities_config(
    path: Path,
    entity_types: dict[str, EntityTypeConfig],
) -> EntitiesConfig:
    entities = EntitiesConfig.model_validate(_read_yaml(path))
    _validate_entities(entities, entity_types)
    return entities


def load_entity_relations_config(
    path: Path,
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
) -> EntityRelationsConfig:
    relations = EntityRelationsConfig.model_validate(_read_yaml(path))
    refs = _entity_refs(entities, entity_types)
    for relation in relations.relations:
        for ref in relation.entities:
            if ref not in refs:
                raise ConfigError(f"Entity not found: {ref}")
    return relations


def load_node_configs(path: Path) -> dict[str, NodeConfig]:
    configs: dict[str, NodeConfig] = {}
    root = path.parent.parent
    for file in sorted(path.glob("*.yaml")):
        node = NodeConfig.model_validate(_read_yaml(file))
        if node.type == "llm" and node.system_prompt_file:
            prompt_path = root / node.system_prompt_file
            if not prompt_path.exists():
                raise ConfigError(f"missing system prompt file: {prompt_path}")
            node.system_prompt = prompt_path.read_text(encoding="utf-8")
        configs[node.name] = node
    return configs


def load_skill_configs(path: Path) -> dict[str, SkillConfig]:
    configs: dict[str, SkillConfig] = {}
    if not path.exists():
        return configs
    root = path.parent.parent
    for file in sorted(path.glob("*.yaml")):
        skill = SkillConfig.model_validate(_read_yaml(file))
        handler_path = root / "skill_handlers" / f"{skill.handler}.py"
        if not handler_path.exists():
            raise ConfigError(f"missing skill handler file: {handler_path}")
        configs[skill.name] = skill
    return configs


def load_dag_config(path: Path) -> DagConfig:
    return DagConfig.model_validate(_read_yaml(path))


def load_dag_configs(path: Path) -> dict[str, DagConfig]:
    configs: dict[str, DagConfig] = {}
    for file in sorted(path.glob("*.yaml")):
        dag = load_dag_config(file)
        configs[dag.name] = dag
    return configs


def load_app_config(config_dir: Path = Path("config")) -> AppConfig:
    entity_types = load_entity_type_configs(config_dir.parent / "schemas" / "entity-types")
    entities = load_entities_config(config_dir / "entities.yaml", entity_types)
    entity_relations = load_entity_relations_config(
        config_dir / "entity-relations.yaml",
        entities,
        entity_types,
    )
    dags = load_dag_configs(config_dir / "dags")
    _validate_dag_entity_permissions(dags, entity_types)
    return AppConfig(
        system=load_system_config(config_dir / "system.toml"),
        entity_types=entity_types,
        entities=entities,
        entity_relations=entity_relations,
        runtime=RuntimeSettings(),
        nodes=load_node_configs(config_dir / "nodes"),
        skills=load_skill_configs(config_dir / "skills"),
        dags=dags,
    )


def _validate_dag_entity_permissions(
    dags: dict[str, DagConfig],
    entity_types: dict[str, EntityTypeConfig],
) -> None:
    from stockimformation.config.entities import validate_permission_overrides

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
        business_id = entity.attributes.get(entity_type.business_id_field)
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
        if expected == "integer" and not isinstance(value, int):
            raise ConfigError(f"entity {entity.id}.{key} must be integer")
        if expected == "boolean" and not isinstance(value, bool):
            raise ConfigError(f"entity {entity.id}.{key} must be boolean")
        if expected == "object" and not isinstance(value, dict):
            raise ConfigError(f"entity {entity.id}.{key} must be object")
        if expected == "array" and not isinstance(value, list):
            raise ConfigError(f"entity {entity.id}.{key} must be array")


def _entity_refs(
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
) -> set[str]:
    refs = {entity.id for entity in entities.entities}
    for entity in entities.entities:
        entity_type = entity_types[entity.type]
        refs.add(f"{entity.type}:{entity.attributes[entity_type.business_id_field]}")
    return refs
