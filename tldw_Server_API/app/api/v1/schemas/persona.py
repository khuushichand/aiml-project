"""
Pydantic schemas for Persona Agent API.

Scaffold only - minimal models to enable endpoint stubs.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PersonaInfo(BaseModel):
    id: str
    name: str
    description: str | None = None
    voice: str | None = None
    avatar_url: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    default_tools: list[str] = Field(default_factory=list)


class PersonaSessionRequest(BaseModel):
    persona_id: str
    project_id: str | None = None
    resume_session_id: str | None = None


class PersonaSessionResponse(BaseModel):
    session_id: str
    persona: PersonaInfo
    scopes: list[str] = Field(default_factory=list)


class PersonaSessionSummary(BaseModel):
    session_id: str
    persona_id: str
    created_at: str
    updated_at: str
    turn_count: int = 0
    pending_plan_count: int = 0
    preferences: dict[str, object] = Field(default_factory=dict)


class PersonaSessionDetail(PersonaSessionSummary):
    turns: list[dict[str, object]] = Field(default_factory=list)
