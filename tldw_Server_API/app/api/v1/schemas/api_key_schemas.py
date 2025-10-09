"""Pydantic schemas for API key management endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


class APIKeyCreateRequest(BaseModel):
    name: Optional[str] = Field(None, description="Optional display name for the key")
    description: Optional[str] = Field(None, description="Optional description")
    scope: str = Field("read", description="Permission scope: read|write|admin|service")
    expires_in_days: Optional[int] = Field(365, ge=1, description="Days until expiration (None = never)")


class APIKeyRotateRequest(BaseModel):
    expires_in_days: Optional[int] = Field(365, ge=1, description="Expiration for the new key")


class APIKeyMetadata(BaseModel):
    id: int
    key_prefix: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    scope: str
    status: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    usage_count: Optional[int] = 0
    last_used_at: Optional[str] = None
    last_used_ip: Optional[str] = None


class APIKeyCreateResponse(APIKeyMetadata):
    key: Optional[str] = Field(None, description="The actual API key (returned only at creation/rotation)")
    message: Optional[str] = None

