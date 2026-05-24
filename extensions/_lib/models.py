from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawItem(BaseModel):
    id: int | None = None
    url: str
    title: str
    content: str
    source_name: str
    source_type: str
    tags: list[str] = Field(default_factory=list)
    published_at: datetime
    fetched_at: datetime = Field(default_factory=utc_now)

    @field_validator("url", "title", "content", "source_name", "source_type")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value


class AnalysisResult(BaseModel):
    id: int | None = None
    raw_item_id: int = 0
    summary: str
    keywords: list[str] = Field(default_factory=list)
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


class Advice(BaseModel):
    id: int | None = None
    stock_code: str
    stock_name: str
    direction: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence: list[int] = Field(default_factory=list)
    source_quotes: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    portfolio_snapshot: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    low_confidence: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    data_window_start: datetime
    data_window_end: datetime

    @model_validator(mode="after")
    def _audit_fields_present(self) -> Advice:
        if not self.evidence or not self.source_quotes or not self.source_urls:
            raise ValueError("advice requires evidence, source_quotes, and source_urls")
        if not self.portfolio_snapshot:
            raise ValueError("advice requires portfolio_snapshot")
        return self


class Briefing(BaseModel):
    cycle_id: str
    content: str
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")
    created_at: datetime = Field(default_factory=utc_now)
