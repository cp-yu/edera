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
        _validate_parameter_mapping(value)
        return value


class DagConfig(BaseModel):
    name: str
    nodes: list[DagNodeInstance]
    edges: list[DagEdge]
    ui: dict[str, Any] = Field(default_factory=dict)


class AppConfig(BaseModel):
    system: SystemConfig
    portfolio: PortfolioConfig
    runtime: RuntimeSettings
    nodes: dict[str, NodeConfig]
    skills: dict[str, SkillConfig]
    dags: dict[str, DagConfig]


JsonObject = dict[str, Any]
