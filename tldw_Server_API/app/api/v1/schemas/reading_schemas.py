from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, HttpUrl, validator

from tldw_Server_API.app.api.v1.schemas._compat import Field


class ReadingSaveRequest(BaseModel):
    url: HttpUrl = Field(example="https://example.com/article")
    title: Optional[str] = Field(default=None, example="Example Article")
    tags: List[str] = Field(default_factory=list, example=["ai", "reading"])
    status: Optional[str] = Field(default="saved", description="saved|reading|read|archived", example="saved")
    favorite: bool = False
    summary: Optional[str] = Field(default=None, example="Short summary for quick scan.")
    notes: Optional[str] = Field(default=None, example="Why this matters for the project.")
    content: Optional[str] = Field(
        default=None,
        description="Optional inline content override (testing/offline)",
        example="Inline article content used for testing.",
    )

    @validator("tags", pre=True, each_item=True)
    def _strip_tags(cls, value: str) -> str:
        return value.strip()


class ReadingItem(BaseModel):
    id: int
    media_id: Optional[int] = Field(default=None, example=42)
    media_uuid: Optional[str] = None
    title: str = Field(example="Example Article")
    url: Optional[str] = Field(default=None, example="https://example.com/article")
    canonical_url: Optional[str] = Field(default=None, example="https://example.com/article")
    domain: Optional[str] = Field(default=None, example="example.com")
    summary: Optional[str] = Field(default=None, example="Short summary for quick scan.")
    notes: Optional[str] = Field(default=None, example="Why this matters for the project.")
    published_at: Optional[str] = None
    status: Optional[str] = Field(default=None, example="saved")
    processing_status: Optional[str] = None
    favorite: bool = False
    tags: List[str] = Field(default_factory=list, example=["ai", "reading"])
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    read_at: Optional[str] = None


class ReadingItemDetail(ReadingItem):
    text: Optional[str] = Field(default=None, example="Full extracted article text.")
    clean_html: Optional[str] = Field(default=None, example="<p>Sanitized HTML...</p>")
    metadata: Optional[Dict[str, Any]] = None


class ReadingItemsListResponse(BaseModel):
    items: List[ReadingItem]
    total: int
    page: int
    size: int
    offset: Optional[int] = None
    limit: Optional[int] = None


class ReadingImportResponse(BaseModel):
    source: str
    imported: int
    updated: int
    skipped: int
    errors: List[str] = Field(default_factory=list)


class ReadingImportJobResponse(BaseModel):
    """Response payload for a newly created reading import job."""

    job_id: int
    job_uuid: Optional[str] = None
    status: str


class ReadingImportJobStatus(BaseModel):
    """Status payload for tracking a reading import job."""

    job_id: int
    job_uuid: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress_percent: Optional[float] = None
    progress_message: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[ReadingImportResponse] = None


class ReadingImportJobsListResponse(BaseModel):
    jobs: List[ReadingImportJobStatus]
    total: int
    limit: Optional[int] = None
    offset: Optional[int] = None


class ReadingDigestScheduleFilters(BaseModel):
    status: Optional[List[Literal["saved", "reading", "read", "archived"]]] = None
    tags: Optional[List[str]] = None
    favorite: Optional[bool] = None
    domain: Optional[str] = None
    q: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    sort: Optional[str] = Field(
        default=None,
        description="updated_desc|updated_asc|created_desc|created_asc|title_asc|title_desc|relevance",
    )
    limit: Optional[int] = Field(default=None, ge=1, le=500)

    @validator("status", pre=True)
    def _coerce_status_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [value]
        return value

    @validator("tags", pre=True)
    def _coerce_tags_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [value]
        return value

    @validator("tags", pre=True, each_item=True)
    def _strip_digest_tags(cls, value: str) -> str:
        return value.strip()


class ReadingDigestScheduleCreateRequest(BaseModel):
    name: Optional[str] = None
    cron: str = Field(..., description="Cron expression, e.g., '0 8 * * *'")
    timezone: Optional[str] = Field(
        None,
        description="IANA timezone name (e.g., 'UTC', 'America/New_York')",
    )
    enabled: bool = True
    require_online: bool = False
    format: Literal["md", "html"] = Field(default="md")
    template_id: Optional[int] = None
    template_name: Optional[str] = None
    retention_days: Optional[int] = Field(default=None, ge=0, le=3650)
    filters: Optional[ReadingDigestScheduleFilters] = None


class ReadingDigestScheduleUpdateRequest(BaseModel):
    name: Optional[str] = None
    cron: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None
    require_online: Optional[bool] = None
    format: Optional[Literal["md", "html"]] = None
    template_id: Optional[int] = None
    template_name: Optional[str] = None
    retention_days: Optional[int] = Field(default=None, ge=0, le=3650)
    filters: Optional[ReadingDigestScheduleFilters] = None


class ReadingDigestScheduleResponse(BaseModel):
    id: str
    name: Optional[str] = None
    cron: str
    timezone: Optional[str] = None
    enabled: bool
    require_online: bool
    format: Literal["md", "html"]
    template_id: Optional[int] = None
    template_name: Optional[str] = None
    retention_days: Optional[int] = None
    filters: Optional[ReadingDigestScheduleFilters] = None
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    last_status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReadingDigestOutput(BaseModel):
    output_id: int
    title: str
    format: Literal["md", "html"]
    created_at: Optional[str] = None
    download_url: str
    schedule_id: Optional[str] = None
    schedule_name: Optional[str] = None
    item_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ReadingDigestOutputsListResponse(BaseModel):
    items: List[ReadingDigestOutput]
    total: int
    limit: Optional[int] = None
    offset: Optional[int] = None


class ReadingArchiveCreateRequest(BaseModel):
    format: Literal["html", "md"] = Field(
        default="html",
        description="Archive format (html or md).",
        example="html",
    )
    source: Literal["auto", "clean_html", "text"] = Field(
        default="auto",
        description="Source content preference (auto uses clean_html then text).",
        example="auto",
    )
    title: Optional[str] = Field(default=None, max_length=200, description="Optional archive title override")
    retention_days: Optional[int] = Field(
        default=None,
        ge=0,
        le=3650,
        description="Retention window in days (0 to disable retention). Ignored if retention_until is provided.",
    )
    retention_until: Optional[str] = Field(
        default=None,
        description="ISO timestamp when this archive can be purged. Takes precedence over retention_days when set.",
        example="2025-12-31T00:00:00Z",
    )


class ReadingArchiveResponse(BaseModel):
    output_id: int
    title: str
    format: Literal["html", "md"]
    storage_path: str
    created_at: Optional[str] = None
    retention_until: Optional[str] = None
    download_url: str


class ReadingDeleteResponse(BaseModel):
    status: str = Field(example="archived")
    item_id: int = Field(example=123)
    hard: bool = False


class ReadingSummarizeRequest(BaseModel):
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider (e.g., openai, anthropic)",
        example="openai",
    )
    model: Optional[str] = Field(default=None, description="Optional model override", example="gpt-4o-mini")
    prompt: Optional[str] = Field(
        default=None,
        description="Optional user prompt override",
        example="Summarize for a product brief.",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional system prompt override",
        example="You are a concise research assistant.",
    )
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, example=0.4)
    recursive: bool = Field(default=False, description="Enable recursive summarization")
    chunked: bool = Field(default=False, description="Summarize chunks and concatenate")


class ReadingCitation(BaseModel):
    item_id: int = Field(example=123)
    url: Optional[str] = Field(default=None, example="https://example.com/article")
    canonical_url: Optional[str] = Field(default=None, example="https://example.com/article")
    title: Optional[str] = Field(default=None, example="Example Article")
    source: str = "reading"


class ReadingSummaryResponse(BaseModel):
    item_id: int = Field(example=123)
    summary: str = Field(example="Short summary text...")
    provider: str = Field(example="openai")
    model: Optional[str] = Field(default=None, example="gpt-4o-mini")
    citations: List[ReadingCitation] = Field(default_factory=list)
    generated_at: Optional[str] = None


class ReadingTTSRequest(BaseModel):
    model: str = Field(default="kokoro", description="TTS model identifier", example="kokoro")
    voice: str = Field(default="af_heart", description="TTS voice identifier", example="af_heart")
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = Field(default="mp3")
    stream: bool = Field(default=True)
    speed: Optional[float] = Field(default=None, ge=0.25, le=4.0, example=1.0)
    max_chars: Optional[int] = Field(default=None, ge=1, le=200000, example=12000)
    text_source: Optional[Literal["text", "summary", "notes"]] = Field(
        default=None,
        description="Optional override for which field to render",
        example="text",
    )


class ReadingUpdateRequest(BaseModel):
    status: Optional[str] = Field(
        default=None,
        description="saved|reading|read|archived",
        example="read",
    )
    favorite: Optional[bool] = None
    tags: Optional[List[str]] = Field(default=None, example=["ai", "priority"])
    notes: Optional[str] = Field(default=None, example="Follow up in the next sprint.")
    title: Optional[str] = Field(default=None, example="Updated Article Title")

    @validator("tags", pre=True, each_item=True)
    def _strip_tags(cls, value: str) -> str:
        return value.strip()
