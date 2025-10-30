from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, AnyUrl, validator


SourceType = Literal["rss", "site"]  # forums moved to Phase 3 (feature-flagged later)


# --------------------
# Job Filters
# --------------------
FilterType = Literal["keyword", "author", "date_range", "regex", "all"]
FilterAction = Literal["include", "exclude", "flag"]


class WatchlistFilter(BaseModel):
    type: FilterType
    action: FilterAction
    value: Dict[str, Any] = Field(default_factory=dict)
    priority: Optional[int] = None
    is_active: bool = True


class WatchlistFiltersPayload(BaseModel):
    filters: List[WatchlistFilter] = Field(default_factory=list)
    require_include: Optional[bool] = Field(
        default=None,
        description=(
            "Include-only gating toggle. When true and any include rules exist, only include-"
            "matched items are ingested; others are treated as filtered. If unset, the job"
            " inherits the organization default when available (organizations.metadata.watchlists."
            "require_include_default or flat key watchlists_require_include_default) and finally"
            " the WATCHLISTS_REQUIRE_INCLUDE_DEFAULT env var."
        ),
    )


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


# --------------------
# Bulk Sources Response (per-entry status)
# --------------------
class SourcesBulkCreateItem(BaseModel):
    name: Optional[str] = None
    url: str
    id: Optional[int] = None
    status: Literal["created", "error"]
    error: Optional[str] = None
    source_type: Optional[SourceType] = None


class SourcesBulkCreateResponse(BaseModel):
    items: List[SourcesBulkCreateItem]
    total: int
    created: int
    errors: int


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
    job_filters: Optional[WatchlistFiltersPayload] = Field(
        default=None,
        description="Optional job-level filters payload (bridge from SUBS Import Rules)",
    )


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
    job_filters: Optional[WatchlistFiltersPayload] = Field(
        default=None,
        description="Optional job-level filters payload (replace)",
    )


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
    job_filters: Optional[WatchlistFiltersPayload] = None
    created_at: str
    updated_at: str
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    wf_schedule_id: Optional[str] = None


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
    has_more: Optional[bool] = None


class PreviewItem(BaseModel):
    source_id: int
    source_type: SourceType
    url: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    published_at: Optional[str] = None
    decision: Literal["ingest", "filtered"]
    matched_action: Optional[FilterAction] = None
    matched_filter_key: Optional[str] = None
    flagged: bool = False


class PreviewResponse(BaseModel):
    items: List[PreviewItem]
    total: int
    ingestable: int
    filtered: int


class RunDetail(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    stats: Dict[str, int] = Field(default_factory=lambda: {"items_found": 0, "items_ingested": 0})
    filter_tallies: Optional[Dict[str, int]] = None
    error_msg: Optional[str] = None
    log_text: Optional[str] = None
    log_path: Optional[str] = None
    truncated: bool = False
    filtered_sample: Optional[List[Dict[str, Any]]] = None


class ScrapedItem(BaseModel):
    id: int
    run_id: int
    job_id: int
    source_id: int
    media_id: Optional[int] = None
    media_uuid: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    published_at: Optional[str] = None
    tags: List[str] = []
    status: str
    reviewed: bool
    created_at: str


class ScrapedItemsListResponse(BaseModel):
    items: List[ScrapedItem]
    total: int


class ScrapedItemUpdateRequest(BaseModel):
    reviewed: Optional[bool] = None
    status: Optional[str] = Field(None, description="Optional status override (e.g., reviewed, ignored)")


class WatchlistOutputEmailDelivery(BaseModel):
    enabled: bool = True
    recipients: Optional[List[str]] = Field(default=None, description="Explicit recipient emails; defaults to user email when empty")
    subject: Optional[str] = Field(default=None, description="Overrides default subject (defaults to output title)")
    attach_file: bool = Field(default=True, description="Attach rendered content as a file")
    body_format: Literal["auto", "text", "html"] = Field(default="auto", description="Controls email body format")


class WatchlistOutputChatbookDelivery(BaseModel):
    enabled: bool = True
    title: Optional[str] = Field(default=None, description="Override Chatbook document title")
    description: Optional[str] = Field(default=None, description="Optional description stored alongside the document")
    conversation_id: Optional[int] = Field(default=None, description="Optional conversation association")
    provider: Optional[str] = Field(default="watchlists", description="Provider marker for the generated document")
    model: Optional[str] = Field(default="watchlists", description="Model marker for the generated document")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata stored with the document")


class WatchlistOutputDeliveries(BaseModel):
    email: Optional[WatchlistOutputEmailDelivery] = None
    chatbook: Optional[WatchlistOutputChatbookDelivery] = None


class WatchlistOutputCreateRequest(BaseModel):
    run_id: int = Field(..., description="Run identifier the output is based on")
    item_ids: Optional[List[int]] = Field(None, description="Explicit list of scraped item IDs to include")
    title: Optional[str] = Field(None, description="Optional title to embed in the generated output")
    type: str = Field("briefing_markdown", description="Output template/type identifier")
    format: Optional[Literal["md", "html"]] = Field(None, description="Rendered output format (overrides template)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata stored alongside the output")
    template_name: Optional[str] = Field(None, description="Name of a stored template to render with")
    retention_seconds: Optional[int] = Field(None, ge=60, description="Optional custom retention in seconds (0 = no expiry)")
    temporary: Optional[bool] = Field(False, description="Whether to use temporary retention defaults")
    deliveries: Optional[WatchlistOutputDeliveries] = Field(
        default=None,
        description="Optional delivery configuration (email, chatbook). Overrides job defaults when provided.",
    )


class WatchlistOutput(BaseModel):
    id: int
    run_id: int
    job_id: int
    type: str
    format: str
    title: Optional[str] = None
    content: Optional[str] = None
    storage_path: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    media_item_id: Optional[int] = None
    chatbook_path: Optional[str] = None
    version: int
    expires_at: Optional[str] = None
    expired: bool = False
    created_at: str


class WatchlistOutputsListResponse(BaseModel):
    items: List[WatchlistOutput]
    total: int


class WatchlistTemplateSummary(BaseModel):
    name: str
    format: Literal["md", "html"]
    description: Optional[str] = None
    updated_at: str


class WatchlistTemplateDetail(WatchlistTemplateSummary):
    content: str


class WatchlistTemplateListResponse(BaseModel):
    items: List[WatchlistTemplateSummary]


class WatchlistTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    format: Literal["md", "html"] = "md"
    content: str = Field(..., description="Template content")
    description: Optional[str] = Field(None, description="Optional human-readable description")
    overwrite: bool = Field(False, description="If false, creation fails when template already exists")


# --------------------
# OPML Import/Export
# --------------------
class SourcesImportItem(BaseModel):
    url: str
    name: Optional[str] = None
    id: Optional[int] = None
    status: Literal["created", "skipped", "error"]
    error: Optional[str] = None


class SourcesImportResponse(BaseModel):
    items: List[SourcesImportItem]
    total: int
    created: int
    skipped: int
    errors: int
