from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class PrivilegeBucket(BaseModel):
    key: str
    users: int
    endpoints: int
    scopes: int
    metadata: Optional[Dict[str, Any]] = None


class PrivilegeSummaryResponse(BaseModel):
    catalog_version: str
    generated_at: datetime
    group_by: str
    buckets: List[PrivilegeBucket]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PrivilegeDetailItem(BaseModel):
    user_id: str
    user_name: str
    role: str
    endpoint: str
    method: str
    privilege_scope_id: str
    feature_flag_id: Optional[str] = None
    sensitivity_tier: str
    ownership_predicates: List[str] = Field(default_factory=list)
    status: Literal["allowed", "blocked"]
    blocked_reason: Optional[str] = None


class PrivilegeDetailResponse(BaseModel):
    catalog_version: str
    generated_at: datetime
    page: int
    page_size: int
    total_items: int
    items: List[PrivilegeDetailItem]


PrivilegeOrgResponse = Union[PrivilegeSummaryResponse, PrivilegeDetailResponse]


class PrivilegeSnapshotSummary(BaseModel):
    users: int
    scopes: int
    sensitivity_breakdown: Dict[str, int] = Field(default_factory=dict)
    scope_ids: List[str] = Field(default_factory=list)


class PrivilegeSnapshotListItem(BaseModel):
    snapshot_id: str
    generated_at: datetime
    generated_by: str
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    catalog_version: str
    summary: Optional[PrivilegeSnapshotSummary] = None


class PrivilegeSnapshotListResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    items: List[PrivilegeSnapshotListItem]
    filters: Dict[str, Any] = Field(default_factory=dict)
