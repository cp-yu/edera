from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator
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


class SkillRef(BaseModel):
    name: str


class NodeConfig(BaseModel):
    name: str
    type: Literal["function", "llm"]
    skills: list[SkillRef]
    model: str | None = None
    input_type: str
    output_type: str
    timeout_seconds: float | None = Field(default=None, gt=0)
    source_names: list[str] = Field(default_factory=list)

    @field_validator("skills")
    @classmethod
    def _has_skill(cls, value: list[SkillRef]) -> list[SkillRef]:
        if not value:
            raise ValueError("node requires at least one skill")
        return value


class DagEdge(BaseModel):
    from_: str = Field(alias="from")
    to: str
    fan_out: bool = False
    fan_in: bool = False


class DagConfig(BaseModel):
    name: str
    nodes: list[str]
    edges: list[DagEdge]


class AppConfig(BaseModel):
    system: SystemConfig
    portfolio: PortfolioConfig
    runtime: RuntimeSettings
    nodes: dict[str, NodeConfig]
    dags: dict[str, DagConfig]


JsonObject = dict[str, Any]
