from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    ntfy_topic: str | None = None
    ntfy_url: str = "https://ntfy.sh"
    pi_bin: str = "pi"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="STOCKIMFORMATION_",
        extra="ignore",
    )


class SystemConfig(BaseModel):
    database_url: str = "sqlite+aiosqlite:///data/stockimformation.db"
    schedule_minutes: int = Field(default=30, ge=1)
    web_host: str = "127.0.0.1"
    web_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    workspace_root: Path = Path("/tmp/stockimformation/runs")
    retention_count: int = Field(default=20, ge=0)
    retention_hours: int = Field(default=24, ge=0)
    source_recovery_enabled: bool = True
    source_recovery_max_attempts: int = Field(default=2, ge=0)
    source_repair_task_output_dir: Path | None = None
    price_history_path: Path | None = None
    price_comparison_horizon_days: int = Field(default=7, ge=1)
    price_comparison_threshold_percent: float = Field(default=1.0, ge=0.0)

    @field_validator("web_host")
    @classmethod
    def _local_web_host(cls, value: str) -> str:
        if value != "127.0.0.1":
            raise ValueError("web_host must be 127.0.0.1")
        return value


class Holding(BaseModel):
    quantity: float = Field(default=0.0, ge=0.0)
    cost_price: float | None = Field(default=None, ge=0.0)


class SourceConfig(BaseModel):
    name: str
    type: Literal["rss", "web"]
    url: HttpUrl
    selector: str | None = None
    regex: str | None = None


class TargetConfig(BaseModel):
    code: str
    name: str
    holding: Holding | None = None
    sources: list[str] = Field(default_factory=list)


class PortfolioConfig(BaseModel):
    targets: list[TargetConfig]
    sources: list[SourceConfig]

    def source_map(self) -> dict[str, SourceConfig]:
        return {source.name: source for source in self.sources}


FieldPermission = Literal["none", "read-only", "write-only", "read-write"]


class EntityTypeConfig(BaseModel):
    display_name: str
    business_id_field: str
    display_template: str
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")
    field_permissions: dict[str, FieldPermission] = Field(default_factory=dict)
    validate_: bool = Field(default=True, alias="validate")


class EntityConfig(BaseModel):
    id: str
    type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntitiesConfig(BaseModel):
    entities: list[EntityConfig] = Field(default_factory=list)

    def by_id(self) -> dict[str, EntityConfig]:
        return {entity.id: entity for entity in self.entities}

    def to_portfolio(
        self,
        entity_types: dict[str, EntityTypeConfig],
        relations: EntityRelationsConfig | None = None,
    ) -> PortfolioConfig:
        source_entities = [entity for entity in self.entities if entity.type in {"rss-source", "web-source"}]
        stock_entities = [entity for entity in self.entities if entity.type == "stock"]
        sources = [
            SourceConfig.model_validate(
                {
                    "name": entity.attributes.get("name") or _business_id(entity, entity_types),
                    "type": "rss" if entity.type == "rss-source" else "web",
                    "url": entity.attributes.get("url"),
                    "selector": entity.attributes.get("selector"),
                    "regex": entity.attributes.get("regex"),
                }
            )
            for entity in source_entities
        ]
        source_names_by_stock = _source_names_by_stock(self, entity_types, relations)
        targets = [
            TargetConfig.model_validate(
                {
                    "code": entity.attributes.get("code"),
                    "name": entity.attributes.get("name"),
                    "holding": entity.attributes.get("holding"),
                    "sources": source_names_by_stock.get(entity_ref(entity, entity_types), []),
                }
            )
            for entity in stock_entities
        ]
        return PortfolioConfig(targets=targets, sources=sources)


class EntityRelationConfig(BaseModel):
    entities: list[str]
    type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntityRelationsConfig(BaseModel):
    relations: list[EntityRelationConfig] = Field(default_factory=list)


NodeRole = Literal["source", "processor", "sink"]


class SkillConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    handler: str
    parameters_schema: dict[str, Any] = Field(default_factory=dict)


class NodeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["function", "llm"]
    role: NodeRole = "processor"
    skills: list[str] = Field(default_factory=list)
    handler: str | None = None
    system_prompt_file: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    input_type: str
    output_type: str
    timeout_seconds: float | None = Field(default=None, gt=0)
    source_names: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("skills", mode="before")
    @classmethod
    def _skill_names(cls, value: object) -> object:
        if isinstance(value, list):
            return [item.get("name") if isinstance(item, dict) else item for item in value]
        return value

    @model_validator(mode="after")
    def _type_specific_fields(self) -> NodeConfig:
        if self.type == "function" and not self.handler and not self.skills:
            raise ValueError("function node requires handler")
        if self.type == "llm" and not self.system_prompt_file:
            raise ValueError("llm node requires system_prompt_file")
        if self.type == "function" and self.skills:
            raise ValueError("function node must not define skills")
        return self

    @field_validator("parameters")
    @classmethod
    def _json_like_parameters(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_parameter_mapping(value)
        return value

    @field_validator("parameters_schema")
    @classmethod
    def _json_like_parameters_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_json_schema_object(value)
        return value


def _validate_parameter_mapping(value: dict[str, Any]) -> None:
    for key, item in value.items():
        lowered = key.lower()
        if any(token in lowered for token in ("secret", "token", "password", "credential", "key")):
            raise ValueError("parameters must not contain credentials")
        _validate_parameter_value(item)


def _validate_parameter_value(value: Any) -> None:
    if value is None or isinstance(value, str | int | float | bool):
        return
    if isinstance(value, list):
        for item in value:
            _validate_parameter_value(item)
        return
    if isinstance(value, dict):
        _validate_parameter_mapping(value)
        return
    raise ValueError("parameters must be JSON-like")


def _validate_json_schema_object(value: dict[str, Any], path: str = "parameters_schema") -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON Schema object")
    schema_type = value.get("type")
    if schema_type is not None and schema_type != "object":
        raise ValueError(f"{path}.type must be 'object'")
    properties = value.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ValueError(f"{path}.properties must be a mapping")
        for key, item in properties.items():
            if not isinstance(key, str) or not isinstance(item, dict):
                raise ValueError(f"{path}.properties entries must be objects")
            _validate_json_schema_fragment(item, f"{path}.properties.{key}")
    required = value.get("required")
    if required is not None:
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise ValueError(f"{path}.required must be a list of strings")


def _validate_json_schema_fragment(value: dict[str, Any], path: str) -> None:
    schema_type = value.get("type")
    if schema_type is not None and not isinstance(schema_type, str):
        raise ValueError(f"{path}.type must be a string")
    enum = value.get("enum")
    if enum is not None and not isinstance(enum, list):
        raise ValueError(f"{path}.enum must be a list")
    items = value.get("items")
    if items is not None:
        if not isinstance(items, dict):
            raise ValueError(f"{path}.items must be an object")
        _validate_json_schema_fragment(items, f"{path}.items")
    properties = value.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ValueError(f"{path}.properties must be a mapping")
        for key, item in properties.items():
            if not isinstance(key, str) or not isinstance(item, dict):
                raise ValueError(f"{path}.properties entries must be objects")
            _validate_json_schema_fragment(item, f"{path}.properties.{key}")
    required = value.get("required")
    if required is not None:
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise ValueError(f"{path}.required must be a list of strings")
    if "default" in value:
        _validate_parameter_value(value["default"])


class DagEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    fan_out: bool = False
    fan_in: bool = False


class DagNodeInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    alias: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("config")
    @classmethod
    def _json_like_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        checked = {key: item for key, item in value.items() if key != "entity_permissions"}
        _validate_parameter_mapping(checked)
        return value


class DagConfig(BaseModel):
    name: str
    nodes: list[DagNodeInstance]
    edges: list[DagEdge]
    ui: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    system: SystemConfig
    entity_types: dict[str, EntityTypeConfig]
    entities: EntitiesConfig
    entity_relations: EntityRelationsConfig
    runtime: RuntimeSettings
    nodes: dict[str, NodeConfig]
    skills: dict[str, SkillConfig]
    dags: dict[str, DagConfig]

    @property
    def portfolio(self) -> PortfolioConfig:
        return self.entities.to_portfolio(self.entity_types, self.entity_relations)


JsonObject = dict[str, Any]


def entity_ref(entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> str:
    business_id = _business_id(entity, entity_types)
    return f"{entity.type}:{business_id}"


def _business_id(entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> str:
    entity_type = entity_types[entity.type]
    value = entity.attributes.get(entity_type.business_id_field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"entity {entity.id} missing business id field: {entity_type.business_id_field}")
    return value


def _source_names_by_stock(
    entities: EntitiesConfig,
    entity_types: dict[str, EntityTypeConfig],
    relations: EntityRelationsConfig | None,
) -> dict[str, list[str]]:
    if relations is None:
        return {}
    refs_by_id = {entity.id: entity_ref(entity, entity_types) for entity in entities.entities}
    source_names = {
        entity_ref(entity, entity_types): str(entity.attributes.get("name") or _business_id(entity, entity_types))
        for entity in entities.entities
        if entity.type in {"rss-source", "web-source"}
    }
    result: dict[str, list[str]] = {}
    for relation in relations.relations:
        refs = [refs_by_id.get(ref, ref) for ref in relation.entities]
        stocks = [ref for ref in refs if ref.startswith("stock:")]
        sources = [source_names[ref] for ref in refs if ref in source_names]
        for stock in stocks:
            result.setdefault(stock, [])
            for source in sources:
                if source not in result[stock]:
                    result[stock].append(source)
    return result
