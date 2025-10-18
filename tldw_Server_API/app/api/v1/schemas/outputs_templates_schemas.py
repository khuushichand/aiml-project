from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, validator


TemplateType = Literal[
    "newsletter_markdown",
    "briefing_markdown",
    "mece_markdown",
    "newsletter_html",
    "tts_audio",
]

TemplateFormat = Literal["md", "html", "mp3"]


class OutputTemplateCreate(BaseModel):
    """Create an output template used for rendering collections (items or runs)."""

    name: str = Field(..., min_length=1, max_length=200)
    type: TemplateType
    format: TemplateFormat
    body: str = Field(..., description="Template body (e.g., Jinja2/Markdown/HTML)")
    description: Optional[str] = Field(None, max_length=500)
    is_default: bool = False
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Arbitrary template metadata. For tts, supports keys tts_default_model, tts_default_voice, tts_default_speed.")

    @validator("format")
    def validate_format_matches_type(cls, v: TemplateFormat, values: Dict[str, object]):  # type: ignore[override]
        t = values.get("type")
        if t in ("newsletter_markdown", "briefing_markdown", "mece_markdown") and v != "md":
            raise ValueError("Markdown-type templates must use format 'md'.")
        if t == "newsletter_html" and v != "html":
            raise ValueError("newsletter_html templates must use format 'html'.")
        if t == "tts_audio" and v != "mp3":
            raise ValueError("tts_audio templates must use format 'mp3'.")
        return v


class OutputTemplateUpdate(BaseModel):
    """Partial update for an existing template."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[TemplateType] = None
    format: Optional[TemplateFormat] = None
    body: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    is_default: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class OutputTemplate(BaseModel):
    """Template model used in responses."""

    id: int
    user_id: Optional[str] = None
    name: str
    type: TemplateType
    format: TemplateFormat
    body: str
    description: Optional[str] = None
    is_default: bool = False
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class OutputTemplateList(BaseModel):
    items: List[OutputTemplate]
    total: int


class TemplatePreviewRequest(BaseModel):
    """Preview rendering without persisting an output artifact.

    Advanced users can pass inline `data` to dry-run rendering with a custom
    context. When `data` is provided, `item_ids`/`run_id` are optional.
    """

    template_id: int
    item_ids: Optional[List[int]] = Field(default=None, description="Items to render.")
    run_id: Optional[int] = Field(default=None, description="Use items from this run.")
    limit: int = Field(default=50, ge=1, le=1000)
    data: Optional[Dict[str, object]] = Field(
        default=None,
        description="Inline context for preview. Example: { 'items': [...], 'date': '...', 'job': {...} }",
    )

    @validator("item_ids")
    def validate_sources(cls, v, values):  # type: ignore[override]
        # Allow inline data to satisfy preview requirements
        data = values.get("data")
        run_id = values.get("run_id")
        if not v and not run_id and not data:
            raise ValueError("Provide item_ids, run_id, or inline data for preview.")
        return v


class TemplatePreviewResponse(BaseModel):
    rendered: str
    format: Literal["md", "html"]
