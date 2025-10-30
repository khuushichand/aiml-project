from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field


class OrganizationCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    slug: Optional[str] = None
    owner_user_id: Optional[int] = None


class OrganizationResponse(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    owner_user_id: Optional[int] = None
    is_active: Optional[bool] = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OrganizationListResponse(BaseModel):
    items: List[OrganizationResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    slug: Optional[str] = None
    description: Optional[str] = None


class TeamResponse(BaseModel):
    id: int
    org_id: int
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class TeamMemberAddRequest(BaseModel):
    user_id: int
    role: Optional[str] = Field("member", pattern=r"^(owner|admin|lead|member)$")


class TeamMemberResponse(BaseModel):
    team_id: int
    user_id: int
    role: str
    org_id: Optional[int] = None


class VirtualKeyCreateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    expires_in_days: Optional[int] = Field(30, ge=1)
    org_id: Optional[int] = None
    team_id: Optional[int] = None
    allowed_endpoints: Optional[List[str]] = Field(default_factory=lambda: ["chat.completions", "embeddings"])
    allowed_providers: Optional[List[str]] = None
    allowed_models: Optional[List[str]] = None
    budget_day_tokens: Optional[int] = None
    budget_month_tokens: Optional[int] = None
    budget_day_usd: Optional[float] = None
    budget_month_usd: Optional[float] = None
    # Additional generic constraints stored in metadata for non-LLM enforcement
    allowed_methods: Optional[List[str]] = None
    allowed_paths: Optional[List[str]] = None
    max_calls: Optional[int] = Field(None, ge=0)
    max_runs: Optional[int] = Field(None, ge=0)


# ============================
# Organization membership schemas
# ============================

class OrgMemberAddRequest(BaseModel):
    user_id: int
    role: Optional[str] = Field("member", pattern=r"^(owner|admin|lead|member)$")


class OrgMemberResponse(BaseModel):
    org_id: int
    user_id: int
    role: str


class OrgMemberRoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(owner|admin|lead|member)$")


class OrgMemberListItem(BaseModel):
    user_id: int
    role: str
    status: Optional[str] = None
    added_at: Optional[str] = None


class OrgMembershipItem(BaseModel):
    org_id: int
    role: str


# ============================
# Organization settings: Watchlists
# ============================

class OrganizationWatchlistsSettingsUpdate(BaseModel):
    require_include_default: Optional[bool] = Field(
        default=None,
        description="When true, include-only gating is enabled by default for jobs in this organization",
    )


class OrganizationWatchlistsSettingsResponse(BaseModel):
    org_id: int
    require_include_default: Optional[bool] = None
