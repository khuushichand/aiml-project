from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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

