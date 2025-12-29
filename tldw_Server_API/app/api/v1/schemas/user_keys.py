from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class UserProviderKeyUpsertRequest(BaseModel):
    provider: str = Field(..., description="Provider name (e.g., 'openai').")
    api_key: str = Field(..., description="Provider API key.")
    credential_fields: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional provider-specific credential fields (e.g., base_url).",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional non-sensitive metadata tags.",
    )


class ProviderKeyTestRequest(BaseModel):
    provider: str = Field(..., description="Provider name (e.g., 'openai').")
    model: Optional[str] = Field(
        default=None,
        description="Optional model override for the test call.",
    )


class UserProviderKeyResponse(BaseModel):
    provider: str
    status: Literal["stored"] = "stored"
    key_hint: str
    updated_at: datetime


class UserProviderKeyStatusItem(BaseModel):
    provider: str
    has_key: bool
    source: Literal["user", "team", "org", "server_default", "none", "disabled"]
    key_hint: Optional[str] = None
    last_used_at: Optional[datetime] = None


class UserProviderKeysResponse(BaseModel):
    items: List[UserProviderKeyStatusItem]


class ProviderKeyTestResponse(BaseModel):
    provider: str
    status: Literal["valid"] = "valid"
    model: Optional[str] = None


class SharedProviderKeyUpsertRequest(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    api_key: str
    credential_fields: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class SharedProviderKeyResponse(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    status: Literal["stored"] = "stored"
    key_hint: str
    updated_at: datetime


class SharedProviderKeyTestRequest(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    model: Optional[str] = None


class SharedProviderKeyTestResponse(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    status: Literal["valid"] = "valid"
    model: Optional[str] = None


class SharedProviderKeyStatusItem(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    key_hint: Optional[str] = None
    last_used_at: Optional[datetime] = None


class SharedProviderKeysResponse(BaseModel):
    items: List[SharedProviderKeyStatusItem]


class AdminUserKeyStatusItem(BaseModel):
    provider: str
    key_hint: Optional[str] = None
    last_used_at: Optional[datetime] = None
    allowed: bool


class AdminUserKeysResponse(BaseModel):
    user_id: int
    items: List[AdminUserKeyStatusItem]
