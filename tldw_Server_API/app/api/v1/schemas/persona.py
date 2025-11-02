"""
Pydantic schemas for Persona Agent API.

Scaffold only - minimal models to enable endpoint stubs.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class PersonaInfo(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    voice: Optional[str] = None
    avatar_url: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    default_tools: List[str] = Field(default_factory=list)


class PersonaSessionRequest(BaseModel):
    persona_id: str
    project_id: Optional[str] = None
    resume_session_id: Optional[str] = None


class PersonaSessionResponse(BaseModel):
    session_id: str
    persona: PersonaInfo
    scopes: List[str] = Field(default_factory=list)
