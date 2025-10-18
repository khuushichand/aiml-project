from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, AnyUrl, validator


SourceType = Literal["rss", "site"]  # forums moved to Phase 3 (feature-flagged later)


class SourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: AnyUrl
    source_type: SourceType
    active: bool = True
    settings: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = Field(default=None, description="Tag names; server normalizes and resolves to IDs")
    group_ids: Optional[List[int]] = None


class SourceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[AnyUrl] = None
    source_type: Optional[SourceType] = None
    active: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = Field(default=None, description="Replace tags with these names")
    group_ids: Optional[List[int]] = None


class Source(BaseModel):
    id: int
    name: str
    url: str
    source_type: SourceType
    active: bool
    tags: List[str] = []
    settings: Optional[Dict[str, Any]] = None
    last_scraped_at: Optional[str] = None
    status: Optional[str] = None
    created_at: str
    updated_at: str


class SourcesListResponse(BaseModel):
    items: List[Source]
    total: int


class SourcesBulkCreateRequest(BaseModel):
    sources: List[SourceCreateRequest]


class GroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    parent_group_id: Optional[int] = None


class GroupUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    parent_group_id: Optional[int] = None


class Group(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent_group_id: Optional[int] = None


class GroupsListResponse(BaseModel):
    items: List[Group]
    total: int


class Tag(BaseModel):
    id: int
    name: str


class TagsListResponse(BaseModel):
    items: List[Tag]
    total: int


class JobCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    scope: Dict[str, Any] = Field(default_factory=dict, description="Selection: {sources:[], groups:[], tags:[]}")
    schedule_expr: Optional[str] = Field(None, description="Cron or interval expression; stored as provided")
    timezone: Optional[str] = Field(None, description="Timezone for schedule; PRD default UTC+8")
    active: bool = True
    max_concurrency: Optional[int] = None
    per_host_delay_ms: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    output_prefs: Optional[Dict[str, Any]] = None


class JobUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[Dict[str, Any]] = None
    schedule_expr: Optional[str] = None
    timezone: Optional[str] = None
    active: Optional[bool] = None
    max_concurrency: Optional[int] = None
    per_host_delay_ms: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    output_prefs: Optional[Dict[str, Any]] = None


class Job(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    scope: Dict[str, Any]
    schedule_expr: Optional[str]
    timezone: Optional[str]
    active: bool
    max_concurrency: Optional[int] = None
    per_host_delay_ms: Optional[int] = None
    retry_policy: Optional[Dict[str, Any]] = None
    output_prefs: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None


class JobsListResponse(BaseModel):
    items: List[Job]
    total: int


class Run(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    error_msg: Optional[str] = None


class RunsListResponse(BaseModel):
    items: List[Run]
    total: int

