# app/api/v1/schemas/notes_schemas.py
#
# Imports
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

# 3rd-party Libraries
from pydantic import BaseModel, ConfigDict, Field, field_validator

#
# Local Imports
#
#######################################################################################################################
#
# Schemas:

def _split_keywords(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [p.strip() for p in value.split(',')]
    if isinstance(value, list):
        return [p.strip() for p in value if isinstance(p, str)]
    raise ValueError("Keywords must be a list of strings or a comma-separated string.")


# --- Note Schemas ---
class NoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Title of the note")
    content: str = Field(..., min_length=1, max_length=5000000, description="Content of the note (max 5MB)")
    conversation_id: str | None = Field(None, description="Optional conversation ID backlink")
    message_id: str | None = Field(None, description="Optional message ID backlink")


class NoteCreate(NoteBase):
    # Override to allow optional title when auto_title is used
    title: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Title of the note. Optional when auto_title=true."
    )
    id: str | None = Field(None,
                              description="Optional client-provided UUID for the note. If None, will be auto-generated.")
    keywords: str | list[str] | None = Field(
        default=None,
        description="Optional keywords to attach to the note. Accepts a list of strings or a comma-separated string."
    )
    # Title auto-generation controls
    # MVP: heuristic-only; Phase 2: 'llm' available behind flag
    auto_title: bool = Field(False, description="If true and no title provided, auto-generate a title from content.")
    title_strategy: Literal["heuristic", "llm", "llm_fallback"] = Field(
        "heuristic",
        description="Strategy for title generation. MVP supports 'heuristic'."
    )
    title_max_len: int = Field(250, ge=1, le=500, description="Max title length when auto-generating.")
    language: str | None = Field(None, description="Optional language hint for title generation.")

    # Normalize keywords input to a clean list of strings (if provided)
    @field_validator("keywords", mode="before")
    @classmethod
    def validate_keywords(cls, value: Any):
        parts = _split_keywords(value)
        if parts is None:
            return value
        for part in parts:
            if not part:
                continue
            if len(part) > 100:
                raise ValueError("Keyword entries must be 100 characters or fewer.")
        return value

    @property
    def normalized_keywords(self) -> list[str] | None:
        parts = _split_keywords(getattr(self, 'keywords', None))
        if parts is None:
            return None
        # Remove empties and deduplicate while preserving order
        seen = set()
        result: list[str] = []
        for p in parts:
            if not p:
                continue
            # Dedup case-insensitive
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(p)
        return result or None


class NoteUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255, description="New title for the note")
    content: str | None = Field(None, min_length=1, max_length=5000000, description="New content for the note (max 5MB)")
    conversation_id: str | None = Field(None, description="Optional conversation ID backlink")
    message_id: str | None = Field(None, description="Optional message ID backlink")
    keywords: str | list[str] | None = Field(
        default=None,
        description="Optional keywords to attach to the note. Accepts a list of strings or a comma-separated string."
    )
    # Ensure at least one field is provided for update, or handle in endpoint if empty update is no-op
    # Pydantic v2: model_validator

    @field_validator("keywords", mode="before")
    @classmethod
    def validate_keywords(cls, value: Any):
        parts = _split_keywords(value)
        if parts is None:
            return value
        for part in parts:
            if not part:
                continue
            if len(part) > 100:
                raise ValueError("Keyword entries must be 100 characters or fewer.")
        return value

    @property
    def normalized_keywords(self) -> list[str] | None:
        parts = _split_keywords(getattr(self, 'keywords', None))
        if parts is None:
            return None
        seen = set()
        result: list[str] = []
        for p in parts:
            if not p:
                continue
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(p)
        return result or None


class NoteResponse(NoteBase):
    id: str = Field(..., description="UUID of the note")
    created_at: datetime = Field(..., description="Timestamp of note creation")
    last_modified: datetime = Field(..., description="Timestamp of last modification")
    version: int = Field(..., description="Version number for optimistic locking")
    client_id: str = Field(..., description="Client ID that last modified the note")
    deleted: bool = Field(..., description="Whether the note is soft-deleted")
    keywords: list[KeywordResponse] | None = Field(default=None, description="Keywords linked to this note")

    model_config = ConfigDict(from_attributes=True)  # Pydantic V2 (formerly orm_mode)


# --- Keyword Schemas ---
class KeywordBase(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100, description="The keyword text")


class KeywordCreate(KeywordBase):
    pass


class KeywordResponse(KeywordBase):
    id: int = Field(..., description="Integer ID of the keyword")
    created_at: datetime = Field(..., description="Timestamp of keyword creation")
    last_modified: datetime = Field(..., description="Timestamp of last modification")
    version: int = Field(..., description="Version number for optimistic locking")
    client_id: str = Field(..., description="Client ID that last modified the keyword")
    deleted: bool = Field(..., description="Whether the keyword is soft-deleted")

    model_config = ConfigDict(from_attributes=True)


# --- Linking Schemas ---
class NoteKeywordLinkResponse(BaseModel):
    success: bool
    message: str | None = None


class KeywordsForNoteResponse(BaseModel):
    note_id: str
    keywords: list[KeywordResponse]


class NotesForKeywordResponse(BaseModel):
    keyword_id: int
    notes: list[NoteResponse]


# --- General API Response Schemas ---
class DetailResponse(BaseModel):
    detail: str


# --- Bulk Create Schemas ---
class NoteBulkCreateRequest(BaseModel):
    notes: list[NoteCreate] = Field(..., min_length=1, max_length=200, description="List of notes to create")


class NoteBulkCreateItemResult(BaseModel):
    success: bool
    note: NoteResponse | None = None
    error: str | None = None


class NoteBulkCreateResponse(BaseModel):
    results: list[NoteBulkCreateItemResult]
    created_count: int = 0
    failed_count: int = 0


# --- List/Export Response Schemas ---
class NotesListResponse(BaseModel):
    notes: list[NoteResponse]
    items: list[NoteResponse]
    results: list[NoteResponse]
    count: int
    limit: int
    offset: int
    total: int | None = None


class NotesExportResponse(BaseModel):
    notes: list[NoteResponse]
    data: list[NoteResponse]
    items: list[NoteResponse]
    results: list[NoteResponse]
    count: int
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    exported_at: str


class NotesExportRequest(BaseModel):
    """Export request for selected notes.

    Accepts explicit note IDs and optional flags for including keywords and
    selecting the output format.
    """
    model_config = ConfigDict(extra='forbid')

    note_ids: list[str] = Field(..., description="List of note IDs to export")
    include_keywords: bool = Field(default=False)
    format: Literal['json', 'csv'] = Field(default='json', description="Use /export.csv for CSV exports.")


# --- Title Suggestion Schemas ---
class TitleSuggestRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000000, description="Source content of the note")
    title_strategy: Literal["heuristic", "llm", "llm_fallback"] = Field(
        "heuristic",
        description="Strategy for title generation. MVP supports 'heuristic'."
    )
    title_max_len: int = Field(250, ge=1, le=500, description="Max title length for suggestion.")
    language: str | None = Field(None, description="Optional language hint.")


class TitleSuggestResponse(BaseModel):
    title: str = Field(..., description="Suggested title")


# Resolve forward references for nested schemas.
NoteResponse.model_rebuild()
KeywordsForNoteResponse.model_rebuild()
NotesForKeywordResponse.model_rebuild()

#
# End of notes_schemas.py
#######################################################################################################################
