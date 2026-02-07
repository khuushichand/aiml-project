from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class UserProviderKeyUpsertRequest(BaseModel):
    provider: str = Field(..., description="Provider name (e.g., 'openai').")
    api_key: str = Field(..., description="Provider API key.")
    credential_fields: dict[str, Any] | None = Field(
        default=None,
        description="Optional provider-specific credential fields (e.g., base_url).",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional non-sensitive metadata tags.",
    )


class ProviderKeyTestRequest(BaseModel):
    provider: str = Field(..., description="Provider name (e.g., 'openai').")
    model: str | None = Field(
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
    key_hint: str | None = None
    last_used_at: datetime | None = None


class UserProviderKeysResponse(BaseModel):
    items: list[UserProviderKeyStatusItem]


class ProviderKeyTestResponse(BaseModel):
    provider: str
    status: Literal["valid"] = "valid"
    model: str | None = None


class SharedProviderKeyUpsertRequest(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    api_key: str
    credential_fields: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


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
    model: str | None = None


class SharedProviderKeyTestResponse(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    status: Literal["valid"] = "valid"
    model: str | None = None


class SharedProviderKeyStatusItem(BaseModel):
    scope_type: Literal["org", "team"]
    scope_id: int
    provider: str
    key_hint: str | None = None
    last_used_at: datetime | None = None


class SharedProviderKeysResponse(BaseModel):
    items: list[SharedProviderKeyStatusItem]


class AdminUserKeyStatusItem(BaseModel):
    provider: str
    key_hint: str | None = None
    last_used_at: datetime | None = None
    allowed: bool


class AdminUserKeysResponse(BaseModel):
    user_id: int
    items: list[AdminUserKeyStatusItem]
