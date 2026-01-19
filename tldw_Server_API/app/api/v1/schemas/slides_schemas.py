"""Pydantic models for Slides/Presentation module."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SlideLayout(str, Enum):
    TITLE = "title"
    CONTENT = "content"
    TWO_COLUMN = "two_column"
    QUOTE = "quote"
    SECTION = "section"
    BLANK = "blank"


class Slide(BaseModel):
    order: int
    layout: SlideLayout
    title: Optional[str] = None
    content: str = ""
    speaker_notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PresentationBase(BaseModel):
    title: str
    description: Optional[str] = None
    theme: str = "black"
    marp_theme: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    slides: List[Slide] = Field(default_factory=list)
    custom_css: Optional[str] = None


class PresentationCreateRequest(PresentationBase):
    pass


class PresentationUpdateRequest(PresentationBase):
    pass


class PresentationPatchRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[str] = None
    marp_theme: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    slides: Optional[List[Slide]] = None
    custom_css: Optional[str] = None


class PresentationResponse(PresentationBase):
    id: str
    source_type: Optional[str] = None
    source_ref: Optional[Any] = None
    source_query: Optional[str] = None
    created_at: datetime
    last_modified: datetime
    deleted: bool
    client_id: str
    version: int


class PresentationSummary(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    theme: str
    created_at: datetime
    last_modified: datetime
    deleted: bool
    version: int


class PresentationListResponse(BaseModel):
    presentations: List[PresentationSummary]
    total: int
    limit: int
    offset: int


class PresentationSearchResponse(BaseModel):
    presentations: List[PresentationSummary]
    total: int
    limit: int
    offset: int


class SlideGenerationBase(BaseModel):
    title_hint: Optional[str] = None
    theme: Optional[str] = None
    marp_theme: Optional[str] = None
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
    prompt: str


class GenerateFromChatRequest(SlideGenerationBase):
    conversation_id: str


class GenerateFromNotesRequest(SlideGenerationBase):
    note_ids: List[str]


class GenerateFromMediaRequest(SlideGenerationBase):
    media_id: str


class GenerateFromRagRequest(SlideGenerationBase):
    query: str
    top_k: Optional[int] = Field(default=8, ge=1)


class ExportFormat(str, Enum):
    REVEAL = "revealjs"
    MARKDOWN = "markdown"
    JSON = "json"


class SlidesHealthResponse(BaseModel):
    service: str
    status: str
    detail: Optional[str] = None
