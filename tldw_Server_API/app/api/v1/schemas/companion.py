from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CompanionActivityItem(BaseModel):
    id: str
    event_type: str
    source_type: str
    source_id: str
    surface: str
    tags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CompanionActivityListResponse(BaseModel):
    items: list[CompanionActivityItem]
    total: int
    limit: int
    offset: int


class CompanionActivityCreate(BaseModel):
    event_type: str
    source_type: str
    source_id: str
    surface: str
    dedupe_key: str | None = None
    tags: list[str] = Field(default_factory=list)
    provenance: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_provenance(self) -> "CompanionActivityCreate":
        if not self.provenance:
            raise ValueError("provenance is required")
        return self


class CompanionCheckInCreate(BaseModel):
    title: str | None = None
    summary: str
    surface: str | None = None
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "summary", "surface", mode="before")
    @classmethod
    def _strip_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("tags", mode="before")
    @classmethod
    def _normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("tags must be a list")
        return [str(item).strip() for item in value if str(item).strip()]

    @model_validator(mode="after")
    def validate_summary(self) -> "CompanionCheckInCreate":
        if not self.summary:
            raise ValueError("summary is required")
        if self.title == "":
            self.title = None
        if self.surface == "":
            self.surface = None
        return self


class CompanionKnowledgeCard(BaseModel):
    id: str
    card_type: str
    title: str
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    score: float
    status: str
    updated_at: datetime


class CompanionKnowledgeListResponse(BaseModel):
    items: list[CompanionKnowledgeCard]
    total: int


class CompanionGoal(BaseModel):
    id: str
    title: str
    description: str | None = None
    goal_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime


class CompanionGoalCreate(BaseModel):
    title: str
    description: str | None = None
    goal_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class CompanionGoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None
    progress: dict[str, Any] | None = None
    status: str | None = None

    model_config = ConfigDict(extra="forbid")


class CompanionGoalListResponse(BaseModel):
    items: list[CompanionGoal]
    total: int


class CompanionReflectionItem(BaseModel):
    id: str
    cadence: str | None = None
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
