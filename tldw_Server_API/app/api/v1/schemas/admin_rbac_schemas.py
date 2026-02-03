# admin_rbac_schemas.py
# Description: Schemas for RBAC admin endpoints (roles, permissions, overrides, limits)

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64)
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_system: bool = False
    model_config = ConfigDict(from_attributes=True)


class PermissionCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=128, description="Permission code e.g., media.read")
    description: Optional[str] = None
    category: Optional[str] = None


class PermissionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class UserRoleListResponse(BaseModel):
    user_id: int
    roles: list[RoleResponse]


class OverrideEffect(str, Enum):
    """Allowed override effects for user permissions."""

    allow = "allow"
    deny = "deny"


class UserOverrideUpsertRequest(BaseModel):
    permission_id: Optional[int] = None
    permission_name: Optional[str] = None
    effect: OverrideEffect = Field(
        ...,
        description="Override effect: 'allow' to grant, 'deny' to revoke",
    )
    expires_at: Optional[str] = None  # ISO timestamp


class UserOverrideEntry(BaseModel):
    permission_id: int
    permission_name: str
    granted: bool
    expires_at: Optional[str] = None


class UserOverridesResponse(BaseModel):
    user_id: int
    overrides: list[UserOverrideEntry]


class EffectivePermissionsResponse(BaseModel):
    user_id: int
    permissions: list[str]


class RateLimitUpsertRequest(BaseModel):
    resource: str = Field(..., min_length=1)
    limit_per_min: Optional[int] = Field(None, ge=1)
    burst: Optional[int] = Field(None, ge=1)


class RateLimitResponse(BaseModel):
    scope: str  # 'role' or 'user'
    id: int     # role_id or user_id
    resource: str
    limit_per_min: Optional[int]
    burst: Optional[int]


class RolePermissionGrant(BaseModel):
    role_id: int
    permission_id: int


class RolePermissionMatrixResponse(BaseModel):
    roles: list[RoleResponse]
    permissions: list[PermissionResponse]
    grants: list[RolePermissionGrant]
    total_roles: int


class RolePermissionBooleanMatrixResponse(BaseModel):
    roles: list[RoleResponse]
    permission_names: list[str]
    matrix: list[list[bool]]
    total_roles: int


class RoleEffectivePermissionsResponse(BaseModel):
    role_id: int
    role_name: str
    permissions: list[str]
    tool_permissions: list[str]
    all_permissions: list[str]
