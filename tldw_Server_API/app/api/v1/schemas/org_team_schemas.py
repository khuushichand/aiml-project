from __future__ import annotations

from typing import Optional, List
from datetime import datetime
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
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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


# ============================
# Self-service org schemas
# ============================

class OrgSelfCreateRequest(BaseModel):
    """Request to create a new organization (self-service)."""
    name: str = Field(..., min_length=2, max_length=100)
    slug: Optional[str] = Field(None, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", max_length=50)


class OrgUpdateRequest(BaseModel):
    """Request to update an organization."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    slug: Optional[str] = Field(None, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", max_length=50)


class OrgDetailResponse(BaseModel):
    """Detailed organization response with membership info."""
    id: int
    name: str
    slug: Optional[str] = None
    owner_user_id: Optional[int] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    member_count: Optional[int] = None
    team_count: Optional[int] = None
    user_role: Optional[str] = None


class OwnershipTransferRequest(BaseModel):
    """Request to transfer org ownership."""
    new_owner_user_id: int = Field(..., description="User ID of the new owner")


class TeamListResponse(BaseModel):
    """List of teams."""
    items: List[TeamResponse]
    total: int


class TeamUpdateRequest(BaseModel):
    """Request to update a team."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    slug: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=500)


class TeamMemberListResponse(BaseModel):
    """List of team members."""
    items: List[TeamMemberResponse]
    total: int


# ============================
# Organization invite schemas
# ============================

class OrgInviteCreateRequest(BaseModel):
    """Request to create an organization invite."""
    team_id: Optional[int] = Field(None, description="Optional team ID for team-specific invite")
    role_to_grant: str = Field("member", pattern=r"^(admin|lead|member)$")
    max_uses: int = Field(1, ge=1, le=1000)
    expiry_days: int = Field(7, ge=1, le=365)
    description: Optional[str] = Field(None, max_length=500)


class OrgInviteResponse(BaseModel):
    """Organization invite details."""
    id: int
    code: str
    org_id: int
    org_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    role_to_grant: str
    max_uses: int
    uses_count: int
    is_active: bool
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[int] = None
    description: Optional[str] = None


class OrgInviteListResponse(BaseModel):
    """List of organization invites."""
    items: List[OrgInviteResponse]
    total: int


class OrgInvitePreviewResponse(BaseModel):
    """Public preview of an invite (no auth required)."""
    org_name: Optional[str] = None
    org_slug: Optional[str] = None
    team_name: Optional[str] = None
    role_to_grant: str
    is_valid: bool
    status: str
    message: Optional[str] = None
    expires_at: Optional[str] = None


class OrgInviteRedeemRequest(BaseModel):
    """Request to redeem an invite code."""
    code: str = Field(..., min_length=8)


class OrgInviteRedeemResponse(BaseModel):
    """Result of redeeming an invite."""
    success: bool
    org_id: Optional[int] = None
    org_name: Optional[str] = None
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    role: Optional[str] = None
    was_already_member: bool = False
    message: Optional[str] = None


class OrgInviteAcceptRequest(BaseModel):
    """Request to accept an org-scoped registration code."""
    code: str = Field(..., min_length=8)


class OrgInviteAcceptResponse(BaseModel):
    """Result of accepting an org-scoped registration code."""
    success: bool
    org_id: Optional[int] = None
    team_id: Optional[int] = None
    org_role: Optional[str] = None
    was_already_member: bool = False
    message: Optional[str] = None
