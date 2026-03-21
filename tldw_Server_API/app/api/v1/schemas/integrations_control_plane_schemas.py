"""Typed schemas for normalized integrations control-plane payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

IntegrationProvider = Literal["slack", "discord", "telegram"]
IntegrationScope = Literal["personal", "workspace"]
IntegrationStatus = Literal["connected", "disconnected", "disabled", "degraded", "needs_config"]


class IntegrationConnection(BaseModel):
    """One normalized connection or installation summary."""

    id: str
    provider: IntegrationProvider
    scope: IntegrationScope
    display_name: str
    status: IntegrationStatus
    enabled: bool
    connected_at: datetime | None = None
    updated_at: datetime | None = None
    health: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)


class IntegrationOverviewResponse(BaseModel):
    """Normalized list payload for integrations management surfaces."""

    scope: IntegrationScope
    items: list[IntegrationConnection] = Field(default_factory=list)
