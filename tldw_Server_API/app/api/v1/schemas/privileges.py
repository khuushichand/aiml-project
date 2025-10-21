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
    trends: List["PrivilegeTrend"] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PrivilegeDependency(BaseModel):
    id: str
    type: str = "dependency"
    module: Optional[str] = None


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
    dependencies: List[PrivilegeDependency] = Field(default_factory=list)
    dependency_sources: List[str] = Field(default_factory=list)
    rate_limit_class: Optional[str] = None
    rate_limit_resources: List[str] = Field(default_factory=list)
    source_module: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PrivilegeDetailResponse(BaseModel):
    catalog_version: str
    generated_at: datetime
    page: int
    page_size: int
    total_items: int
    items: List[PrivilegeDetailItem]
    recommended_actions: Optional[List["PrivilegeRecommendedAction"]] = None


PrivilegeOrgResponse = Union[PrivilegeSummaryResponse, PrivilegeDetailResponse]


class PrivilegeSnapshotSummary(BaseModel):
    users: int
    scopes: int
    endpoints: Optional[int] = None
    sensitivity_breakdown: Dict[str, int] = Field(default_factory=dict)
    scope_ids: List[str] = Field(default_factory=list)
    endpoint_paths: List[str] = Field(default_factory=list)


class PrivilegeSnapshotListItem(BaseModel):
    snapshot_id: str
    generated_at: datetime
    generated_by: str
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    catalog_version: str
    summary: Optional[PrivilegeSnapshotSummary] = None
    target_scope: Optional[Literal["org", "team", "user"]] = None


class PrivilegeSnapshotListResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    items: List[PrivilegeSnapshotListItem]
    filters: Dict[str, Any] = Field(default_factory=dict)


class PrivilegeTrendWindow(BaseModel):
    start: datetime
    end: datetime


class PrivilegeTrend(BaseModel):
    key: str
    window: PrivilegeTrendWindow
    delta_users: int = 0
    delta_endpoints: int = 0
    delta_scopes: int = 0


class PrivilegeRecommendedAction(BaseModel):
    privilege_scope_id: Optional[str] = None
    action: str
    reason: Optional[str] = None


class PrivilegeSelfItem(BaseModel):
    endpoint: str
    method: str
    privilege_scope_id: str
    feature_flag_id: Optional[str] = None
    sensitivity_tier: Optional[str] = None
    ownership_predicates: List[str] = Field(default_factory=list)
    status: Literal["allowed", "blocked"]
    blocked_reason: Optional[str] = None
    dependencies: List[PrivilegeDependency] = Field(default_factory=list)
    dependency_sources: List[str] = Field(default_factory=list)
    rate_limit_class: Optional[str] = None
    rate_limit_resources: List[str] = Field(default_factory=list)
    source_module: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PrivilegeSelfResponse(BaseModel):
    catalog_version: str
    generated_at: datetime
    items: List[PrivilegeSelfItem]
    recommended_actions: List[PrivilegeRecommendedAction] = Field(default_factory=list)


class PrivilegeSnapshotCreateRequest(BaseModel):
    target_scope: Literal["org", "team", "user"]
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    user_ids: Optional[List[str]] = None
    catalog_version: Optional[str] = None
    notes: Optional[str] = None
    async_job: bool = Field(False, alias="async")

    class Config:
        allow_population_by_field_name = True
        populate_by_name = True


class PrivilegeSnapshotAcceptedResponse(BaseModel):
    request_id: str
    status: Literal["queued", "processing"]
    estimated_ready_at: Optional[datetime] = None


class PrivilegeSnapshotRecord(BaseModel):
    snapshot_id: str
    generated_at: datetime
    generated_by: str
    target_scope: Literal["org", "team", "user"]
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    catalog_version: str
    summary: Optional[PrivilegeSnapshotSummary] = None


class PrivilegeSnapshotDetailItem(BaseModel):
    user_id: Optional[str] = None
    endpoint: str
    method: str
    privilege_scope_id: str
    feature_flag_id: Optional[str] = None
    sensitivity_tier: Optional[str] = None
    ownership_predicates: List[str] = Field(default_factory=list)
    status: Literal["allowed", "blocked"]
    blocked_reason: Optional[str] = None
    dependencies: List[PrivilegeDependency] = Field(default_factory=list)
    dependency_sources: List[str] = Field(default_factory=list)
    rate_limit_class: Optional[str] = None
    rate_limit_resources: List[str] = Field(default_factory=list)
    source_module: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class PrivilegeSnapshotDetailMatrix(BaseModel):
    page: int
    page_size: int
    total_items: int
    items: List[PrivilegeSnapshotDetailItem]


class PrivilegeSnapshotDetailResponse(BaseModel):
    snapshot_id: str
    catalog_version: str
    generated_at: datetime
    generated_by: str
    target_scope: Literal["org", "team", "user"]
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    summary: Optional[PrivilegeSnapshotSummary] = None
    detail: Optional[PrivilegeSnapshotDetailMatrix] = None
    etag: Optional[str] = None
