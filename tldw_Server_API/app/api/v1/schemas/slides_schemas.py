"""Pydantic models for Slides/Presentation module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
    title: Optional[str] = None
    content: str = ""
    speaker_notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PresentationBase(BaseModel):
    """Shared fields for presentation create/update payloads."""

    title: str
    description: Optional[str] = None
    theme: str = "black"
    marp_theme: Optional[str] = None
    template_id: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    slides: List[Slide] = Field(default_factory=list)
    custom_css: Optional[str] = None


class PresentationCreateRequest(PresentationBase):
    """Request payload for creating a presentation."""

    pass


class PresentationUpdateRequest(PresentationBase):
    """Request payload for updating a presentation."""

    pass


class PresentationPatchRequest(BaseModel):
    """Request payload for patching a presentation."""

    title: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    marp_theme: Optional[str] = None
    template_id: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    slides: Optional[List[Slide]] = None
    custom_css: Optional[str] = None


class PresentationReorderRequest(BaseModel):
    """Request payload for reordering presentation slides."""

    order: List[int] = Field(..., min_items=1)


class PresentationResponse(PresentationBase):
    """Presentation response model."""

    id: str
    source_type: Optional[str] = None
    source_ref: Optional[Any] = None
    source_query: Optional[str] = None
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
    title: Optional[str] = None
    deleted: Optional[bool] = None


class PresentationVersionListResponse(BaseModel):
    """Paginated list of presentation versions."""

    versions: List[PresentationVersionSummary]
    total: int
    limit: int
    offset: int


class SlidesTemplateResponse(BaseModel):
    """Template details for slide generation."""

    id: str
    name: str
    theme: str
    marp_theme: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    default_slides: Optional[List[Slide]] = None
    custom_css: Optional[str] = None


class SlidesTemplateListResponse(BaseModel):
    """List response for slide templates."""

    templates: List[SlidesTemplateResponse]


class PresentationSummary(BaseModel):
    """Summary item for presentation listings."""

    id: str
    title: str
    description: Optional[str] = None
    theme: str
    created_at: datetime
    last_modified: datetime
    deleted: bool
    version: int


class PresentationListResponse(BaseModel):
    """Paginated list response for presentations."""

    presentations: List[PresentationSummary]
    total: int
    limit: int
    offset: int


class PresentationSearchResponse(BaseModel):
    """Paginated list response for presentation search results."""

    presentations: List[PresentationSummary]
    total: int
    limit: int
    offset: int


class SlideGenerationBase(BaseModel):
    """Shared settings for slide generation requests."""

    title_hint: Optional[str] = None
    theme: Optional[str] = None
    marp_theme: Optional[str] = None
    template_id: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    custom_css: Optional[str] = None
    max_source_tokens: Optional[int] = Field(default=None, ge=1)
    max_source_chars: Optional[int] = Field(default=None, ge=1)
    enable_chunking: bool = False
    chunk_size_tokens: Optional[int] = Field(default=None, ge=1)
    summary_tokens: Optional[int] = Field(default=None, ge=1)
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class GenerateFromPromptRequest(SlideGenerationBase):
    """Request payload for generating slides from a prompt."""

    prompt: str


class GenerateFromChatRequest(SlideGenerationBase):
    """Request payload for generating slides from chat history."""

    conversation_id: str


class GenerateFromNotesRequest(SlideGenerationBase):
    """Request payload for generating slides from notes."""

    note_ids: List[str]


class GenerateFromMediaRequest(SlideGenerationBase):
    """Request payload for generating slides from media."""

    media_id: int = Field(..., ge=1)


class GenerateFromRagRequest(SlideGenerationBase):
    """Request payload for generating slides from a RAG query."""

    query: str
    top_k: Optional[int] = Field(default=8, ge=1)


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
    detail: Optional[str] = None
