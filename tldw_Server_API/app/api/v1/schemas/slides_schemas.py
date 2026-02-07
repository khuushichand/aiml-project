"""Pydantic models for Slides/Presentation module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SlideLayout(str, Enum):
    """Supported slide layout identifiers."""

    TITLE = "title"
    CONTENT = "content"
    TWO_COLUMN = "two_column"
    QUOTE = "quote"
    SECTION = "section"
    BLANK = "blank"


class Slide(BaseModel):
    """Slide payload for presentation content."""

    order: int
    layout: SlideLayout
    title: str | None = None
    content: str = ""
    speaker_notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PresentationBase(BaseModel):
    """Shared fields for presentation create/update payloads."""

    title: str
    description: str | None = None
    theme: str = "black"
    marp_theme: str | None = None
    template_id: str | None = None
    settings: dict[str, Any] | None = None
    slides: list[Slide] = Field(default_factory=list)
    custom_css: str | None = None


class PresentationCreateRequest(PresentationBase):
    """Request payload for creating a presentation."""

    pass


class PresentationUpdateRequest(PresentationBase):
    """Request payload for updating a presentation."""

    pass


class PresentationPatchRequest(BaseModel):
    """Request payload for patching a presentation."""

    title: str | None = None
    description: str | None = None
    theme: str | None = None
    marp_theme: str | None = None
    template_id: str | None = None
    settings: dict[str, Any] | None = None
    slides: list[Slide] | None = None
    custom_css: str | None = None


class PresentationReorderRequest(BaseModel):
    """Request payload for reordering presentation slides."""

    order: list[int] = Field(..., min_items=1)


class PresentationResponse(PresentationBase):
    """Presentation response model."""

    id: str
    source_type: str | None = None
    source_ref: Any | None = None
    source_query: str | None = None
    created_at: datetime
    last_modified: datetime
    deleted: bool
    client_id: str
    version: int


class PresentationVersionSummary(BaseModel):
    """Summary for a presentation version entry."""

    presentation_id: str
    version: int
    created_at: datetime
    title: str | None = None
    deleted: bool | None = None


class PresentationVersionListResponse(BaseModel):
    """Paginated list of presentation versions."""

    versions: list[PresentationVersionSummary]
    total: int
    limit: int
    offset: int


class SlidesTemplateResponse(BaseModel):
    """Template details for slide generation."""

    id: str
    name: str
    theme: str
    marp_theme: str | None = None
    settings: dict[str, Any] | None = None
    default_slides: list[Slide] | None = None
    custom_css: str | None = None


class SlidesTemplateListResponse(BaseModel):
    """List response for slide templates."""

    templates: list[SlidesTemplateResponse]


class PresentationSummary(BaseModel):
    """Summary item for presentation listings."""

    id: str
    title: str
    description: str | None = None
    theme: str
    created_at: datetime
    last_modified: datetime
    deleted: bool
    version: int


class PresentationListResponse(BaseModel):
    """Paginated list response for presentations."""

    presentations: list[PresentationSummary]
    total: int
    limit: int
    offset: int


class PresentationSearchResponse(BaseModel):
    """Paginated list response for presentation search results."""

    presentations: list[PresentationSummary]
    total: int
    limit: int
    offset: int


class SlideGenerationBase(BaseModel):
    """Shared settings for slide generation requests."""

    title_hint: str | None = None
    theme: str | None = None
    marp_theme: str | None = None
    template_id: str | None = None
    settings: dict[str, Any] | None = None
    custom_css: str | None = None
    max_source_tokens: int | None = Field(default=None, ge=1)
    max_source_chars: int | None = Field(default=None, ge=1)
    enable_chunking: bool = False
    chunk_size_tokens: int | None = Field(default=None, ge=1)
    summary_tokens: int | None = Field(default=None, ge=1)
    provider: str | None = None
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class GenerateFromPromptRequest(SlideGenerationBase):
    """Request payload for generating slides from a prompt."""

    prompt: str


class GenerateFromChatRequest(SlideGenerationBase):
    """Request payload for generating slides from chat history."""

    conversation_id: str


class GenerateFromNotesRequest(SlideGenerationBase):
    """Request payload for generating slides from notes."""

    note_ids: list[str]


class GenerateFromMediaRequest(SlideGenerationBase):
    """Request payload for generating slides from media."""

    media_id: int = Field(..., ge=1)


class GenerateFromRagRequest(SlideGenerationBase):
    """Request payload for generating slides from a RAG query."""

    query: str
    top_k: int | None = Field(default=8, ge=1)


class ExportFormat(str, Enum):
    """Supported presentation export formats."""

    REVEAL = "revealjs"
    MARKDOWN = "markdown"
    JSON = "json"
    PDF = "pdf"


class SlidesHealthResponse(BaseModel):
    """Health status response for the slides service."""

    service: str
    status: str
    detail: str | None = None
