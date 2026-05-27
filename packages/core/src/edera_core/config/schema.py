from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PI_TOOLS = {"bash", "read", "edit", "write", "grep", "find"}


class RuntimeSettings(BaseSettings):
    ntfy_topic: str | None = None
    ntfy_url: str = "https://ntfy.sh"
    pi_bin: str = "pi"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EDERA_",
        extra="ignore",
    )


class SystemConfig(BaseModel):
    database_url: str = "sqlite+aiosqlite:///data/edera.db"
    schedule_minutes: int = Field(default=30, ge=1)
    web_host: str = "127.0.0.1"
    web_port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    llm_timeout_seconds: float = Field(default=60.0, ge=0)
    workspace_root: Path = Path("/tmp/edera/runs")
    retention_count: int = Field(default=20, ge=0)
    retention_hours: int = Field(default=24, ge=0)
    sandbox_max_bytes: int = Field(default=0, ge=0)
    max_dag_depth: int = Field(default=3, ge=1)
    config_git_commit: bool = True
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


FieldPermission = Literal["none", "read-only", "write-only", "read-write"]
StorageTier = Literal["filesystem", "database", "memory"]


class EntityTypeConfig(BaseModel):
    display_name: str
    business_id_field: str
    display_template: str
    storage_tier: StorageTier = "filesystem"
    system_protected: bool = False
    schema_: dict[str, Any] = Field(default_factory=dict, alias="schema")
    field_permissions: dict[str, FieldPermission] = Field(default_factory=dict)
    validate_: bool = Field(default=True, alias="validate")

    def has_field(self, name: str) -> bool:
        properties = self.schema_.get("properties")
        return isinstance(properties, dict) and name in properties

    @property
    def is_executable(self) -> bool:
        return self.has_field("handler") or self.has_field("system_prompt_file")

    @property
    def is_dag(self) -> bool:
        return self.has_field("nodes") and self.has_field("edges")

    @property
    def is_trigger(self) -> bool:
        return self.has_field("wait_for") and self.has_field("target")

    @property
    def is_relation(self) -> bool:
        return self.has_field("from") and self.has_field("to") and self.has_field("relation_type")


class EntityConfig(BaseModel):
    id: str
    type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class EntitiesConfig(BaseModel):
    entities: list[EntityConfig] = Field(default_factory=list)

    def by_id(self) -> dict[str, EntityConfig]:
        return {entity.id: entity for entity in self.entities}


class EntityRelationConfig(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
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


class NodeConfigBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: NodeRole = "processor"
    input_type: str
    output_type: str
    optional: bool = False
    timeout_seconds: float | None = Field(default=None, gt=0)


class FunctionNodeConfig(NodeConfigBase):
    type: Literal["function"] = "function"
    handler: str
    skills: list[str] = Field(default_factory=list)
    system_prompt_file: str | None = None
    system_prompt: str | None = None
    tools: list[str] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    input_binding: str | None = None

    @field_validator("skills", mode="before")
    @classmethod
    def _skill_names(cls, value: object) -> object:
        if isinstance(value, list):
            return [item.get("name") if isinstance(item, dict) else item for item in value]
        return value

    @field_validator("tools")
    @classmethod
    def _pi_tools(cls, value: list[str]) -> list[str]:
        return _validate_tools(value)

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


class AgentNodeConfig(NodeConfigBase):
    type: Literal["agent"]
    model: str
    workdir: Path | None = None
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    system_prompt_file: str | None = None
    system_prompt: str | None = None
    parameters_schema: dict[str, Any] = Field(default_factory=dict)

    @field_validator("skills", mode="before")
    @classmethod
    def _skill_names(cls, value: object) -> object:
        if isinstance(value, list):
            return [item.get("name") if isinstance(item, dict) else item for item in value]
        return value

    @field_validator("tools")
    @classmethod
    def _pi_tools(cls, value: list[str]) -> list[str]:
        return _validate_tools(value)

    @field_validator("parameters_schema")
    @classmethod
    def _json_like_parameters_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_json_schema_object(value)
        return value


class DagNodeConfig(NodeConfigBase):
    type: Literal["dag"]
    dag_ref: str
    input_mapping: dict[str, str] = Field(default_factory=dict)

    @field_validator("input_mapping")
    @classmethod
    def _json_like_input_mapping(cls, value: dict[str, str]) -> dict[str, str]:
        return {str(key): str(item) for key, item in value.items()}


class NodeConfig(FunctionNodeConfig):
    _variants: ClassVar[dict[str, type[NodeConfigBase]]] = {
        "function": FunctionNodeConfig,
        "agent": AgentNodeConfig,
        "dag": DagNodeConfig,
    }

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> NodeConfigBase:
        if isinstance(obj, NodeConfigBase):
            return obj
        if isinstance(obj, dict):
            node_type = obj.get("type", "function")
            variant = cls._variants.get(str(node_type))
            if variant is not None and variant is not cls:
                return variant.model_validate(obj, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)

    @classmethod
    def model_construct(cls, _fields_set: set[str] | None = None, **values: Any) -> NodeConfigBase:
        node_type = values.get("type", "function")
        variant = cls._variants.get(str(node_type))
        if variant is not None and variant is not cls:
            return variant.model_construct(_fields_set=_fields_set, **values)
        return super().model_construct(_fields_set=_fields_set, **values)


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
    minimum = value.get("minimum")
    if minimum is not None and not isinstance(minimum, int | float):
        raise ValueError(f"{path}.minimum must be a number")
    if "default" in value:
        _validate_parameter_value(value["default"])


class DagEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    fan_out: bool = False
    fan_in: bool = False
    optional: bool = False
    condition: str | None = None
    fan_in_mode: Literal["barrier", "accumulate", "collect", "stream"] = "barrier"


class DagLoopConfig(BaseModel):
    mode: Literal["parallel", "serial"]
    count: int | None = Field(default=None, ge=1)
    until: str | None = None


class DagNodeInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    alias: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    optional: bool = False
    fan_in_mode: Literal["barrier", "accumulate"] = "barrier"
    loop: DagLoopConfig | None = None
    fallback: Literal["switch_model", "skip"] | None = None
    fallback_model: str | None = None
    resource: str | None = None

    @field_validator("config")
    @classmethod
    def _json_like_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        checked = {key: item for key, item in value.items() if key != "entity_permissions"}
        _validate_parameter_mapping(checked)
        if "session_dir" in value and not _valid_session_dir(value["session_dir"]):
            raise ValueError("config.session_dir must be an absolute path or sandbox:<node_id>:<cycle|latest>")
        if "tools" in value:
            tools = value["tools"]
            if not isinstance(tools, list):
                raise ValueError("config.tools must be a list")
            value["tools"] = _validate_tools([str(item) for item in tools])
        return value


class DagInputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str = "Any"
    required: bool = False
    default: Any = None


class DagConfig(BaseModel):
    name: str
    inputs: list[DagInputConfig] = Field(default_factory=list)
    nodes: list[DagNodeInstance]
    edges: list[DagEdge]
    ui: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    system: SystemConfig
    entity_types: dict[str, EntityTypeConfig]
    entities: EntitiesConfig
    entity_relations: EntityRelationsConfig
    runtime: RuntimeSettings
    nodes: dict[str, NodeConfigBase]
    skills: dict[str, SkillConfig]
    dags: dict[str, DagConfig]


JsonObject = dict[str, Any]


def entity_ref(entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> str:
    business_id = _business_id(entity, entity_types)
    return f"{entity.type}:{business_id}"


def _business_id(entity: EntityConfig, entity_types: dict[str, EntityTypeConfig]) -> str:
    entity_type = entity_types[entity.type]
    if entity_type.business_id_field == "id":
        value = entity.attributes.get("id")
        return value if isinstance(value, str) and value else entity.id
    value = entity.attributes.get(entity_type.business_id_field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"entity {entity.id} missing business id field: {entity_type.business_id_field}")
    return value


def _validate_tools(value: list[str]) -> list[str]:
    invalid = [item for item in value if item not in PI_TOOLS]
    if invalid:
        raise ValueError(f"unknown pi tool: {invalid[0]}")
    return value


def _valid_session_dir(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value.startswith("/"):
        return "\x00" not in value
    if not value.startswith("sandbox:"):
        return False
    parts = value.split(":")
    if len(parts) != 3:
        return False
    node_id, cycle = parts[1], parts[2]
    return _safe_token(node_id) and (cycle == "latest" or _safe_token(cycle))


def _safe_token(value: str) -> bool:
    return bool(value) and all(item.isalnum() or item in {"-", "_", "."} for item in value)
