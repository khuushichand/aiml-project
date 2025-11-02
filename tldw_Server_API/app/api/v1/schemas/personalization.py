"""
Pydantic schemas for Personalization API.

Scaffold only - minimal models to enable endpoint stubs.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class OptInRequest(BaseModel):
    enabled: bool = Field(..., description="Enable/disable personalization for the user")


class PersonalizationProfile(BaseModel):
    enabled: bool = True
    alpha: float = 0.2
    beta: float = 0.6
    gamma: float = 0.2
    recency_half_life_days: int = 14
    topic_count: int = 0
    memory_count: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.utcnow())


class PreferencesUpdate(BaseModel):
    alpha: Optional[float] = None
    beta: Optional[float] = None
    gamma: Optional[float] = None
    recency_half_life_days: Optional[int] = None


class MemoryItem(BaseModel):
    id: str
    type: Literal["semantic", "episodic"] = "semantic"
    content: str
    pinned: bool = False
    tags: Optional[List[str]] = None
    timestamp: Optional[datetime] = None


class MemoryListResponse(BaseModel):
    items: List[MemoryItem]
    total: int
    page: int = 1
    size: int = 50


class ExplanationSignal(BaseModel):
    name: str
    value: float
    detail: Optional[str] = None


class ExplanationEntry(BaseModel):
    timestamp: datetime
    context: Literal["rag", "chat"]
    signals: List[ExplanationSignal]


class ExplanationListResponse(BaseModel):
    items: List[ExplanationEntry]
    total: int


class DetailResponse(BaseModel):
    detail: str
    model_config = ConfigDict(from_attributes=True)
