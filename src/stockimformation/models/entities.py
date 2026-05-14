from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import field_validator, model_validator
from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.types import JSON
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawItem(SQLModel, table=True):
    __tablename__ = "raw_items"
    __table_args__ = (UniqueConstraint("url", name="uq_raw_items_url"),)

    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    title: str
    content: str
    source_name: str
    source_type: str
    stock_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    published_at: datetime
    fetched_at: datetime = Field(default_factory=utc_now)

    @field_validator("url", "title", "content", "source_name", "source_type")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class AnalysisResult(SQLModel, table=True):
    __tablename__ = "analysis_results"

    id: int | None = Field(default=None, primary_key=True)
    raw_item_id: int = Field(foreign_key="raw_items.id")
    summary: str
    keywords: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    sentiment: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_quote: str
    source_url: str
    rationale: str | None = None
    contradiction: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("summary", "sentiment", "source_quote", "source_url")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("sentiment")
    @classmethod
    def _valid_sentiment(cls, value: str) -> str:
        if value not in {"bullish", "bearish", "neutral"}:
            raise ValueError("sentiment must be bullish, bearish, or neutral")
        return value


class Advice(SQLModel, table=True):
    __tablename__ = "advices"

    id: int | None = Field(default=None, primary_key=True)
    stock_code: str
    stock_name: str
    direction: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: list[int] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    source_quotes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    source_urls: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    portfolio_snapshot: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    version: int = Field(default=1, ge=1)
    low_confidence: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    data_window_start: datetime
    data_window_end: datetime

    @field_validator("stock_code", "stock_name", "direction", "reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("direction")
    @classmethod
    def _valid_direction(cls, value: str) -> str:
        if value not in {"buy", "sell", "hold"}:
            raise ValueError("direction must be buy, sell, or hold")
        return value

    @model_validator(mode="after")
    def _audit_fields_present(self) -> "Advice":
        if not self.evidence or not self.source_quotes or not self.source_urls:
            raise ValueError("advice requires evidence, source_quotes, and source_urls")
        if not self.portfolio_snapshot:
            raise ValueError("advice requires portfolio_snapshot")
        if self.data_window_end < self.data_window_start:
            raise ValueError("data_window_end must be after data_window_start")
        return self


class Briefing(SQLModel, table=True):
    __tablename__ = "briefings"

    id: int | None = Field(default=None, primary_key=True)
    cycle_id: str = Field(index=True)
    content: str
    metadata_: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("cycle_id", "content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


__all__ = ["Advice", "AnalysisResult", "Briefing", "RawItem", "utc_now"]
