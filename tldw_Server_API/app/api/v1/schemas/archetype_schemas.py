"""Pydantic schemas for persona archetype YAML templates."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ArchetypePersona(BaseModel):
    """Minimal persona payload embedded in an archetype template."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str
    system_prompt: str
    personality_traits: list[str] = Field(default_factory=list)


class ArchetypeTemplate(BaseModel):
    """Full archetype definition loaded from YAML."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    key: str
    label: str
    tagline: str
    icon: str
    persona: ArchetypePersona | None = None


class ArchetypeSummary(BaseModel):
    """Compact summary used by archetype listings."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    key: str
    label: str
    tagline: str
    icon: str
