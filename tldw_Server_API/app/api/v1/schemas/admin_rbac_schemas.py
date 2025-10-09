# admin_rbac_schemas.py
# Description: Schemas for RBAC admin endpoints (roles, permissions, overrides, limits)

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


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
    roles: List[RoleResponse]


class UserOverrideUpsertRequest(BaseModel):
    permission_id: Optional[int] = None
    permission_name: Optional[str] = None
    effect: str = Field(..., pattern="^(allow|deny)$")
    expires_at: Optional[str] = None  # ISO timestamp


class UserOverrideEntry(BaseModel):
    permission_id: int
    permission_name: str
    granted: bool
    expires_at: Optional[str] = None


class UserOverridesResponse(BaseModel):
    user_id: int
    overrides: List[UserOverrideEntry]


class EffectivePermissionsResponse(BaseModel):
    user_id: int
    permissions: List[str]


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

