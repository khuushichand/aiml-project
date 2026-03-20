"""Pydantic schemas for consent endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConsentRecordResponse(BaseModel):
    """Serializable consent record returned by the consent endpoints."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    user_id: int
    purpose: str
    granted_at: datetime | None = None
    withdrawn_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: str | None = None


class ConsentPreferencesResponse(BaseModel):
    """List response for a user's consent preferences."""

    user_id: int
    consents: list[ConsentRecordResponse]
