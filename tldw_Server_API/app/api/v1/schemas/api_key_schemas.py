"""Pydantic schemas for API key management endpoints."""

from datetime import datetime
from typing import Optional, List, Any, Dict
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
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    usage_count: Optional[int] = 0
    last_used_at: Optional[datetime] = None
    last_used_ip: Optional[str] = None


class APIKeyCreateResponse(APIKeyMetadata):
    key: Optional[str] = Field(None, description="The actual API key (returned only at creation/rotation)")
    message: Optional[str] = None


class APIKeyUpdateRequest(BaseModel):
    rate_limit: Optional[int] = Field(None, description="Requests per minute for this key")
    allowed_ips: Optional[List[str]] = Field(None, description="Restrict usage to these IPs")


class APIKeyAuditEntry(BaseModel):
    id: int
    api_key_id: int
    action: str
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Any] = None
    created_at: Optional[datetime] = None


class APIKeyAuditListResponse(BaseModel):
    key_id: int
    items: List[APIKeyAuditEntry]
    total: Optional[int] = None
