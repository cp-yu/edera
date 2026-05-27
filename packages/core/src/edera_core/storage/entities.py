from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import field_validator
from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NodeOutputEntity(SQLModel, table=True):
    __tablename__ = "node_outputs"
    __table_args__ = (UniqueConstraint("type", "url", name="uq_node_outputs_type_url"),)

    id: int | None = Field(default=None, primary_key=True)
    entity_id: str = Field(index=True, unique=True)
    type: str = Field(index=True)
    cycle_id: str = Field(index=True)
    node_id: str = Field(index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    session_id: str | None = Field(default=None, index=True)
    url: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)

    @field_validator("entity_id", "type", "cycle_id", "node_id")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class EdgeInput(SQLModel, table=True):
    __tablename__ = "edge_inputs"
    __table_args__ = (UniqueConstraint("cycle_id", "from_node_id", "to_node_id", name="uq_edge_inputs_cycle_edge"),)

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: str = Field(index=True)
    from_node_id: str = Field(index=True)
    to_node_id: str = Field(index=True)
    edge_optional: bool = False
    status: str = Field(index=True)
    has_payload: bool = False
    error_summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)

    @field_validator("cycle_id", "from_node_id", "to_node_id", "status")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in {"available", "empty", "failed", "unknown"}:
            raise ValueError("invalid edge input status")
        return value


class SourceRecovery(SQLModel, table=True):
    __tablename__ = "source_recoveries"
    __table_args__ = (UniqueConstraint("cycle_id", "node_id", "source_name", name="uq_source_recoveries_cycle_node_source"),)

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: str = Field(index=True)
    node_id: str = Field(index=True)
    source_name: str = Field(index=True)
    recovery_status: str = Field(index=True)
    attempt_count: int = 0
    recoverable_reason: str | None = None
    latest_failure_reason: str | None = None
    escalated: bool = False
    escalation_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now, index=True)

    @field_validator("cycle_id", "node_id", "source_name", "recovery_status")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class PipelineRun(SQLModel, table=True):
    __tablename__ = "pipeline_runs"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: str = Field(index=True, unique=True)
    dag_name: str = Field(default="default", index=True)
    trigger: str = Field(index=True)
    status: str = Field(index=True)
    started_at: datetime = Field(default_factory=utc_now, index=True)
    ended_at: datetime | None = None
    error: str | None = None
    retry_of: str | None = Field(default=None, index=True)

    @field_validator("cycle_id", "trigger", "status")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("trigger")
    @classmethod
    def _valid_trigger(cls, value: str) -> str:
        if value not in {"startup", "schedule", "manual", "retry"}:
            raise ValueError("trigger must be startup, schedule, manual, or retry")
        return value

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in {"running", "succeeded", "failed", "cancelled"}:
            raise ValueError("status must be running, succeeded, failed, or cancelled")
        return value


class NodeRun(SQLModel, table=True):
    __tablename__ = "node_runs"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: str = Field(foreign_key="pipeline_runs.cycle_id", index=True)
    node_name: str = Field(index=True)
    status: str = Field(index=True)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    error: str | None = None
    failure_kind: str | None = Field(default=None, index=True)

    @field_validator("cycle_id", "node_name", "status")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("status")
    @classmethod
    def _valid_status(cls, value: str) -> str:
        if value not in {"pending", "running", "succeeded", "failed", "skipped", "cancelled"}:
            raise ValueError("invalid node run status")
        return value

    @field_validator("failure_kind")
    @classmethod
    def _valid_failure_kind(cls, value: str | None) -> str | None:
        if value is not None and value not in {"execution_failed", "upstream_failed"}:
            raise ValueError("invalid node run failure kind")
        return value
