from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ScopeType = Literal["global", "org", "team", "user"]
ProfileMode = Literal["preset", "custom"]
AssignmentTargetType = Literal["default", "group", "persona"]


class ACPProfileCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    profile: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ACPProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType | None = None
    owner_scope_id: int | None = None
    profile: dict[str, Any] | None = None
    is_active: bool | None = None


class ACPProfileResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    profile: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class PermissionProfileCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=512)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    mode: ProfileMode = "custom"
    policy_document: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PermissionProfileResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    mode: ProfileMode
    policy_document: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class PolicyAssignmentCreateRequest(BaseModel):
    target_type: AssignmentTargetType
    target_id: str | None = Field(default=None, max_length=200)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    profile_id: int | None = None
    inline_policy_document: dict[str, Any] = Field(default_factory=dict)
    approval_policy_id: int | None = None
    is_active: bool = True


class PolicyAssignmentResponse(BaseModel):
    id: int
    target_type: AssignmentTargetType
    target_id: str | None = None
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    profile_id: int | None = None
    inline_policy_document: dict[str, Any] = Field(default_factory=dict)
    approval_policy_id: int | None = None
    is_active: bool
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class ExternalServerCreateRequest(BaseModel):
    server_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)
    transport: str = Field(..., min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)
    owner_scope_type: ScopeType = Field(default="global")
    owner_scope_id: int | None = None
    enabled: bool = True


class ExternalServerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    transport: str | None = Field(default=None, min_length=1, max_length=64)
    config: dict[str, Any] | None = None
    owner_scope_type: ScopeType | None = None
    owner_scope_id: int | None = None
    enabled: bool | None = None


class ExternalServerResponse(BaseModel):
    id: str
    name: str
    enabled: bool
    owner_scope_type: ScopeType
    owner_scope_id: int | None = None
    transport: str
    config: dict[str, Any] = Field(default_factory=dict)
    secret_configured: bool
    key_hint: str | None = None
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class ExternalSecretSetRequest(BaseModel):
    secret: str = Field(..., min_length=1, max_length=8192)


class ExternalSecretSetResponse(BaseModel):
    server_id: str
    secret_configured: bool
    key_hint: str | None = None
    updated_at: datetime | str | None = None


class MCPHubDeleteResponse(BaseModel):
    ok: bool
