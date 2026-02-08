from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import AnyUrl, BaseModel, Field

SourceType = Literal["rss", "site", "forum"]  # forums are feature-flagged for Phase 3


# --------------------
# Job Filters
# --------------------
FilterType = Literal["keyword", "author", "date_range", "regex", "all"]
FilterAction = Literal["include", "exclude", "flag"]


class WatchlistFilter(BaseModel):
    type: FilterType
    action: FilterAction
    value: dict[str, Any] = Field(default_factory=dict)
    priority: int | None = None
    is_active: bool = True


class WatchlistFiltersPayload(BaseModel):
    filters: list[WatchlistFilter] = Field(default_factory=list)
    require_include: bool | None = Field(
        default=None,
        description=(
            "Include-only gating toggle. When true and any include rules exist, only include-"
            "matched items are ingested; others are treated as filtered. If unset, the job"
            " inherits the organization default when available (organizations.metadata.watchlists."
            "require_include_default or flat key watchlists_require_include_default) and finally"
            " the WATCHLISTS_REQUIRE_INCLUDE_DEFAULT env var."
        ),
    )


class WatchlistIngestPrefs(BaseModel):
    persist_to_media_db: bool = Field(
        default=False,
        description="When true, also persist ingested items to the Media DB.",
    )


class SourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: AnyUrl
    source_type: SourceType
    active: bool = True
    settings: dict[str, Any] | None = None
    tags: list[str] | None = Field(default=None, description="Tag names; server normalizes and resolves to IDs")
    group_ids: list[int] | None = None


class SourceUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    url: AnyUrl | None = None
    source_type: SourceType | None = None
    active: bool | None = None
    settings: dict[str, Any] | None = None
    tags: list[str] | None = Field(default=None, description="Replace tags with these names")
    group_ids: list[int] | None = None


class Source(BaseModel):
    id: int
    name: str
    url: str
    source_type: SourceType
    active: bool
    tags: list[str] = []
    group_ids: list[int] = []
    settings: dict[str, Any] | None = None
    last_scraped_at: str | None = None
    status: str | None = None
    created_at: str
    updated_at: str


class SourcesListResponse(BaseModel):
    items: list[Source]
    total: int


class SourceSeenStats(BaseModel):
    source_id: int
    user_id: int
    seen_count: int = 0
    latest_seen_at: str | None = None
    defer_until: str | None = None
    consec_not_modified: int | None = None
    recent_keys: list[str] = Field(default_factory=list)


class SourceSeenResetResponse(BaseModel):
    source_id: int
    user_id: int
    cleared: int
    cleared_backoff: bool


class SourcesBulkCreateRequest(BaseModel):
    sources: list[SourceCreateRequest]


# --------------------
# Bulk Sources Response (per-entry status)
# --------------------
class SourcesBulkCreateItem(BaseModel):
    name: str | None = None
    url: str
    id: int | None = None
    status: Literal["created", "error"]
    error: str | None = None
    source_type: SourceType | None = None


class SourcesBulkCreateResponse(BaseModel):
    items: list[SourcesBulkCreateItem]
    total: int
    created: int
    errors: int


class GroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    parent_group_id: int | None = None


class GroupUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    parent_group_id: int | None = None


class Group(BaseModel):
    id: int
    name: str
    description: str | None = None
    parent_group_id: int | None = None


class GroupsListResponse(BaseModel):
    items: list[Group]
    total: int


class Tag(BaseModel):
    id: int
    name: str


class TagsListResponse(BaseModel):
    items: list[Tag]
    total: int


class JobCreateRequest(BaseModel):
    name: str
    description: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict, description="Selection: {sources:[], groups:[], tags:[]}")
    schedule_expr: str | None = Field(None, description="Cron or interval expression; stored as provided")
    timezone: str | None = Field(None, description="Timezone for schedule; PRD default UTC")
    active: bool = True
    max_concurrency: int | None = None
    per_host_delay_ms: int | None = None
    retry_policy: dict[str, Any] | None = None
    output_prefs: dict[str, Any] | None = None
    ingest_prefs: WatchlistIngestPrefs | None = Field(
        default=None,
        description="Optional ingest preferences (e.g., Media DB persistence).",
    )
    job_filters: WatchlistFiltersPayload | None = Field(
        default=None,
        description="Optional job-level filters payload (bridge from SUBS Import Rules)",
    )


class JobUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    scope: dict[str, Any] | None = None
    schedule_expr: str | None = None
    timezone: str | None = None
    active: bool | None = None
    max_concurrency: int | None = None
    per_host_delay_ms: int | None = None
    retry_policy: dict[str, Any] | None = None
    output_prefs: dict[str, Any] | None = None
    ingest_prefs: WatchlistIngestPrefs | None = Field(
        default=None,
        description="Optional ingest preferences (replace).",
    )
    job_filters: WatchlistFiltersPayload | None = Field(
        default=None,
        description="Optional job-level filters payload (replace)",
    )


class Job(BaseModel):
    id: int
    name: str
    description: str | None = None
    scope: dict[str, Any]
    schedule_expr: str | None
    timezone: str | None
    active: bool
    max_concurrency: int | None = None
    per_host_delay_ms: int | None = None
    retry_policy: dict[str, Any] | None = None
    output_prefs: dict[str, Any] | None = None
    ingest_prefs: WatchlistIngestPrefs | None = None
    job_filters: WatchlistFiltersPayload | None = None
    created_at: str
    updated_at: str
    last_run_at: str | None = None
    next_run_at: str | None = None
    wf_schedule_id: str | None = None


class JobsListResponse(BaseModel):
    items: list[Job]
    total: int


class Run(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    stats: dict[str, Any] | None = None
    error_msg: str | None = None


class RunsListResponse(BaseModel):
    items: list[Run]
    total: int
    has_more: bool | None = None


class PreviewItem(BaseModel):
    source_id: int
    source_type: SourceType
    url: str | None = None
    title: str | None = None
    summary: str | None = None
    published_at: str | None = None
    decision: Literal["ingest", "filtered"]
    matched_action: FilterAction | None = None
    matched_filter_key: str | None = None
    matched_filter_id: int | None = None
    matched_filter_type: FilterType | None = None
    flagged: bool = False


class PreviewResponse(BaseModel):
    items: list[PreviewItem]
    total: int
    ingestable: int
    filtered: int


class RunDetail(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    stats: dict[str, int] = Field(default_factory=lambda: {"items_found": 0, "items_ingested": 0})
    filter_tallies: dict[str, int] | None = None
    error_msg: str | None = None
    log_text: str | None = None
    log_path: str | None = None
    truncated: bool = False
    filtered_sample: list[dict[str, Any]] | None = None


class ScrapedItem(BaseModel):
    id: int
    run_id: int
    job_id: int
    source_id: int
    media_id: int | None = None
    media_uuid: UUID | None = None
    url: str | None = None
    title: str | None = None
    summary: str | None = None
    published_at: str | None = None
    tags: list[str] = []
    status: str
    reviewed: bool
    created_at: str


class ScrapedItemsListResponse(BaseModel):
    items: list[ScrapedItem]
    total: int


class ScrapedItemUpdateRequest(BaseModel):
    reviewed: bool | None = None
    status: str | None = Field(None, description="Optional status override (e.g., reviewed, ignored)")


class WatchlistOutputEmailDelivery(BaseModel):
    enabled: bool = True
    recipients: list[str] | None = Field(default=None, description="Explicit recipient emails; defaults to user email when empty")
    subject: str | None = Field(default=None, description="Overrides default subject (defaults to output title)")
    attach_file: bool = Field(default=True, description="Attach rendered content as a file")
    body_format: Literal["auto", "text", "html"] = Field(default="auto", description="Controls email body format")


class WatchlistOutputChatbookDelivery(BaseModel):
    enabled: bool = True
    title: str | None = Field(default=None, description="Override Chatbook document title")
    description: str | None = Field(default=None, description="Optional description stored alongside the document")
    conversation_id: int | None = Field(default=None, description="Optional conversation association")
    provider: str | None = Field(default="watchlists", description="Provider marker for the generated document")
    model: str | None = Field(default="watchlists", description="Model marker for the generated document")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata stored with the document")


class WatchlistOutputDeliveries(BaseModel):
    email: WatchlistOutputEmailDelivery | None = None
    chatbook: WatchlistOutputChatbookDelivery | None = None


class WatchlistOutputCreateRequest(BaseModel):
    run_id: int = Field(..., description="Run identifier the output is based on")
    item_ids: list[int] | None = Field(None, description="Explicit list of scraped item IDs to include")
    title: str | None = Field(None, description="Optional title to embed in the generated output")
    type: str = Field("briefing_markdown", description="Output template/type identifier")
    format: Literal["md", "html"] | None = Field(None, description="Rendered output format (overrides template)")
    metadata: dict[str, Any] | None = Field(None, description="Optional metadata stored alongside the output")
    template_name: str | None = Field(None, description="Name of a stored template to render with")
    template_version: int | None = Field(
        default=None,
        ge=1,
        description="Optional version of a watchlists template to render (supports template history).",
    )
    summarize: bool = Field(default=False, description="Generate LLM-based per-article summaries before rendering")
    llm_provider: str | None = Field(default=None, description="LLM provider for summarization (e.g., 'openai', 'anthropic')")
    llm_model: str | None = Field(default=None, description="LLM model override for summarization")
    summarize_prompt: str | None = Field(
        default=None,
        description="Custom prompt for per-article summarization. Default: 2-3 sentence summary.",
    )
    generate_mece: bool = Field(default=False, description="Generate a MECE variant output")
    mece_template_name: str | None = Field(default=None, description="Override template name for MECE output")
    generate_tts: bool = Field(default=False, description="Generate a TTS audio variant output")
    tts_template_name: str | None = Field(default=None, description="Override template name for TTS output")
    generate_audio: bool = Field(default=False, description="Generate a multi-voice audio briefing via workflow")
    target_audio_minutes: int = Field(default=10, ge=1, le=60, description="Target audio briefing duration in minutes")
    audio_model: str | None = Field(default=None, description="TTS model for audio briefing, e.g., 'kokoro'")
    audio_voice: str | None = Field(default=None, description="Default voice for audio briefing, e.g., 'af_heart'")
    audio_speed: float | None = Field(default=None, ge=0.25, le=4.0, description="Audio briefing speed override")
    llm_provider: str | None = Field(default=None, description="LLM provider for summarization and script composition")
    llm_model: str | None = Field(default=None, description="LLM model for summarization and script composition")
    voice_map: dict[str, str] | None = Field(
        default=None,
        description="Voice marker to Kokoro voice ID mapping, e.g., {'HOST': 'af_bella', 'REPORTER': 'am_adam'}",
    )
    ingest_to_media_db: bool = Field(default=False, description="Ingest outputs into Media DB")
    tts_model: str | None = Field(default=None, description="TTS model id, e.g., 'kokoro', 'tts-1'")
    tts_voice: str | None = Field(default=None, description="TTS voice id, e.g., 'af_heart'")
    tts_speed: float | None = Field(default=None, ge=0.25, le=4.0, description="TTS speed override")
    retention_seconds: int | None = Field(None, ge=0, description="Optional custom retention in seconds (0 = no expiry)")
    temporary: bool | None = Field(False, description="Whether to use temporary retention defaults")
    deliveries: WatchlistOutputDeliveries | None = Field(
        default=None,
        description="Optional delivery configuration (email, chatbook). Overrides job defaults when provided.",
    )


class WatchlistOutput(BaseModel):
    id: int
    run_id: int
    job_id: int
    type: str
    format: str
    title: str | None = None
    content: str | None = None
    storage_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    media_item_id: int | None = None
    chatbook_path: str | None = None
    version: int
    expires_at: str | None = None
    expired: bool = False
    created_at: str


class WatchlistOutputsListResponse(BaseModel):
    items: list[WatchlistOutput]
    total: int


class WatchlistTemplateSummary(BaseModel):
    name: str
    format: Literal["md", "html"]
    description: str | None = None
    updated_at: str
    version: int = 1
    history_count: int = 0


class WatchlistTemplateDetail(WatchlistTemplateSummary):
    content: str
    available_versions: list[int] = Field(default_factory=list)


class WatchlistTemplateVersionSummary(BaseModel):
    version: int
    format: Literal["md", "html"]
    description: str | None = None
    updated_at: str
    is_current: bool = False


class WatchlistTemplateVersionsResponse(BaseModel):
    items: list[WatchlistTemplateVersionSummary]


class WatchlistTemplateListResponse(BaseModel):
    items: list[WatchlistTemplateSummary]


class WatchlistTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")
    format: Literal["md", "html"] = "md"
    content: str = Field(..., description="Template content")
    description: str | None = Field(None, description="Optional human-readable description")
    overwrite: bool = Field(False, description="If false, creation fails when template already exists")


class WatchlistTemplateValidationErrorDetail(BaseModel):
    error: Literal["template_validation_error"] = "template_validation_error"
    message: str = Field(..., description="Validation error message")


class WatchlistTemplateValidationErrorResponse(BaseModel):
    detail: WatchlistTemplateValidationErrorDetail


# --------------------
# OPML Import/Export
# --------------------
class SourcesImportItem(BaseModel):
    url: str
    name: str | None = None
    id: int | None = None
    status: Literal["created", "skipped", "error"]
    error: str | None = None


class SourcesImportResponse(BaseModel):
    items: list[SourcesImportItem]
    total: int
    created: int
    skipped: int
    errors: int
