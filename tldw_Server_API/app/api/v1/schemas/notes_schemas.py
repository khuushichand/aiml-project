# app/api/v1/schemas/notes_schemas.py
#
# Imports
from typing import Optional, List, Any, Dict, Union
from datetime import datetime
# 3rd-party Libraries
from pydantic import BaseModel, Field, ConfigDict
#
# Local Imports
#
#######################################################################################################################
#
# Schemas:

# --- Note Schemas ---
class NoteBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Title of the note")
    content: str = Field(..., min_length=1, max_length=5000000, description="Content of the note (max 5MB)")


class NoteCreate(NoteBase):
    id: Optional[str] = Field(None,
                              description="Optional client-provided UUID for the note. If None, will be auto-generated.")
    keywords: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Optional keywords to attach to the note. Accepts a list of strings or a comma-separated string."
    )

    # Normalize keywords input to a clean list of strings (if provided)
    @property
    def normalized_keywords(self) -> Optional[List[str]]:
        value = getattr(self, 'keywords', None)
        if value is None:
            return None
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(',')]
        elif isinstance(value, list):
            parts = [str(p).strip() for p in value]
        else:
            return None
        # Remove empties and deduplicate while preserving order
        seen = set()
        result: List[str] = []
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
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="New title for the note")
    content: Optional[str] = Field(None, min_length=1, max_length=5000000, description="New content for the note (max 5MB)")
    # Ensure at least one field is provided for update, or handle in endpoint if empty update is no-op
    # Pydantic v2: model_validator


class NoteResponse(NoteBase):
    id: str = Field(..., description="UUID of the note")
    created_at: datetime = Field(..., description="Timestamp of note creation")
    last_modified: datetime = Field(..., description="Timestamp of last modification")
    version: int = Field(..., description="Version number for optimistic locking")
    client_id: str = Field(..., description="Client ID that last modified the note")
    deleted: bool = Field(..., description="Whether the note is soft-deleted")
    keywords: Optional[List['KeywordResponse']] = Field(default=None, description="Keywords linked to this note")

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
    message: Optional[str] = None


class KeywordsForNoteResponse(BaseModel):
    note_id: str
    keywords: List[KeywordResponse]


class NotesForKeywordResponse(BaseModel):
    keyword_id: int
    notes: List[NoteResponse]


# --- General API Response Schemas ---
class DetailResponse(BaseModel):
    detail: str


# --- Bulk Create Schemas ---
class NoteBulkCreateRequest(BaseModel):
    notes: List[NoteCreate] = Field(..., min_length=1, max_length=200, description="List of notes to create")


class NoteBulkCreateItemResult(BaseModel):
    success: bool
    note: Optional[NoteResponse] = None
    error: Optional[str] = None


class NoteBulkCreateResponse(BaseModel):
    results: List[NoteBulkCreateItemResult]
    created_count: int = 0
    failed_count: int = 0


# --- List/Export Response Schemas ---
class NotesListResponse(BaseModel):
    notes: List[NoteResponse]
    items: List[NoteResponse]
    results: List[NoteResponse]
    count: int
    limit: int
    offset: int
    total: Optional[int] = None


class NotesExportResponse(BaseModel):
    notes: List[NoteResponse]
    data: List[NoteResponse]
    items: List[NoteResponse]
    results: List[NoteResponse]
    count: int
    total: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    exported_at: str

#
# End of notes_schemas.py
#######################################################################################################################
