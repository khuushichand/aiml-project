# world_book_schemas.py
# Description: Pydantic schemas for World Book API endpoints
#
"""
Pydantic schemas for World Book/Lorebook functionality.

These schemas define the request and response models for the world book
API endpoints, ensuring proper validation and serialization.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorldBookEntryBase(BaseModel):
    """Base schema for world book entries."""
    keywords: list[str] = Field(..., min_length=1, description="Keywords to match")
    content: str = Field(..., min_length=1, description="Content to inject when matched")
    group: Optional[str] = Field(
        None,
        max_length=120,
        description="Optional entry group/category label for organization.",
    )
    appendable: Optional[bool] = Field(
        None,
        description="Whether this entry can be concatenated with other appendable blocks",
    )
    priority: int = Field(0, description="Priority for ordering (higher = more important)")
    enabled: bool = Field(True, description="Whether entry is active")
    case_sensitive: bool = Field(False, description="Whether keyword matching is case-sensitive")
    regex_match: bool = Field(False, description="Whether keywords are regex patterns")
    whole_word_match: bool = Field(True, description="Whether to match whole words only")
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class WorldBookEntryCreate(WorldBookEntryBase):
    """Schema for creating a world book entry."""
    pass


class WorldBookEntryUpdate(BaseModel):
    """Schema for updating a world book entry."""
    keywords: Optional[list[str]] = Field(None, description="New keywords")
    content: Optional[str] = Field(None, description="New content (empty string allowed; validated server-side)")
    group: Optional[str] = Field(None, max_length=120, description="New entry group/category label")
    appendable: Optional[bool] = Field(None, description="New appendable flag")
    priority: Optional[int] = Field(None, description="New priority")
    enabled: Optional[bool] = Field(None, description="New enabled status")
    case_sensitive: Optional[bool] = Field(None, description="New case sensitivity")
    regex_match: Optional[bool] = Field(None, description="New regex match setting")
    whole_word_match: Optional[bool] = Field(None, description="New whole word match setting")
    metadata: Optional[dict[str, Any]] = Field(None, description="New metadata")


class WorldBookEntryResponse(WorldBookEntryBase):
    """Schema for world book entry response."""
    id: int = Field(..., description="Entry ID")
    world_book_id: int = Field(..., description="Parent world book ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_modified: datetime = Field(..., description="Last modification timestamp")

    model_config = ConfigDict(from_attributes=True)


class WorldBookBase(BaseModel):
    """Base schema for world books."""
    name: str = Field(..., min_length=1, max_length=200, description="Unique world book name")
    description: Optional[str] = Field(None, max_length=1000, description="World book description")
    scan_depth: int = Field(
        3,
        ge=1,
        le=20,
        description="Maximum matched entries per world book during a processing call",
    )
    token_budget: int = Field(500, ge=50, le=5000, description="Maximum tokens to use for world info")
    recursive_scanning: bool = Field(False, description="Whether to scan matched entries for more keywords")
    enabled: bool = Field(True, description="Whether the world book is active")


class WorldBookCreate(BaseModel):
    """Schema for creating a world book."""
    name: str = Field(..., min_length=1, max_length=200, description="Unique world book name")
    description: Optional[str] = Field(None, max_length=1000, description="World book description")
    scan_depth: int = Field(
        3,
        ge=1,
        le=20,
        description="Maximum matched entries per world book during a processing call",
    )
    token_budget: int = Field(500, ge=50, le=5000, description="Maximum tokens to use")
    recursive_scanning: bool = Field(False, description="Enable recursive scanning")
    enabled: bool = Field(True, description="Whether the world book is active")


class WorldBookUpdate(BaseModel):
    """Schema for updating a world book."""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="New name")
    description: Optional[str] = Field(None, max_length=1000, description="New description")
    scan_depth: Optional[int] = Field(None, ge=1, le=20, description="New scan depth")
    token_budget: Optional[int] = Field(None, ge=50, le=5000, description="New token budget")
    recursive_scanning: Optional[bool] = Field(None, description="New recursive scanning setting")
    enabled: Optional[bool] = Field(None, description="New enabled status")


class WorldBookResponse(WorldBookBase):
    """Schema for world book response."""
    id: int = Field(..., description="World book ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_modified: datetime = Field(..., description="Last modification timestamp")
    version: int = Field(..., description="Version number for optimistic locking")
    entry_count: Optional[int] = Field(None, description="Number of entries in the world book")

    model_config = ConfigDict(from_attributes=True)


class WorldBookWithEntries(WorldBookResponse):
    """Schema for world book with its entries."""
    entries: list[WorldBookEntryResponse] = Field(default_factory=list, description="World book entries")


class CharacterWorldBookAttachment(BaseModel):
    """Schema for attaching a world book to a character."""
    world_book_id: int = Field(..., description="World book ID to attach")
    enabled: bool = Field(True, description="Whether the attachment is active")
    priority: int = Field(0, description="Priority for this character")


class CharacterWorldBookResponse(WorldBookResponse):
    """Schema for world book attached to a character."""
    world_book_id: int = Field(..., description="World book ID (alias of id)")
    attachment_enabled: bool = Field(..., description="Whether attachment is enabled")
    attachment_priority: int = Field(..., description="Priority for this character")


class ProcessContextRequest(BaseModel):
    """Request schema for processing text with world info."""
    text: str = Field(..., description="Text to scan for keywords")
    world_book_ids: Optional[list[int]] = Field(None, description="Specific world books to use")
    character_id: Optional[int] = Field(None, description="Character whose world books to use")
    scan_depth: int = Field(
        3,
        ge=1,
        le=20,
        description="Override maximum matched entries per world book for this processing call",
    )
    token_budget: int = Field(500, ge=50, le=5000, description="Maximum tokens to inject")
    recursive_scanning: Optional[bool] = Field(
        None,
        description="Enable recursive scanning override; omit to inherit world-book setting",
    )


class ProcessContextDiagnostic(BaseModel):
    """Per-entry diagnostics for world book context processing."""
    entry_id: Optional[int] = Field(None, description="Matched entry ID")
    world_book_id: Optional[int] = Field(None, description="Parent world book ID")
    activation_reason: str = Field(..., description="Activation reason: keyword_match, regex_match, or depth")
    keyword: Optional[str] = Field(None, description="Keyword or regex pattern that matched when available")
    token_cost: int = Field(..., description="Estimated token cost for this entry")
    priority: int = Field(..., description="Entry priority")
    regex_match: bool = Field(..., description="Whether this entry uses regex matching")
    content_preview: str = Field(..., description="Preview of matched entry content")
    depth_level: Optional[int] = Field(None, description="Recursive depth level for depth-triggered matches")


class ProcessContextResponse(BaseModel):
    """Response schema for processed context."""
    injected_content: str = Field(..., description="World info content to inject")
    entries_matched: int = Field(..., description="Number of entries that matched")
    tokens_used: int = Field(..., description="Estimated tokens used")
    books_used: int = Field(..., description="Number of world books that had matches")
    entry_ids: list[int] = Field(..., description="IDs of matched entries")
    token_budget: Optional[int] = Field(
        None,
        description="Token budget used for this processing call",
    )
    budget_exhausted: Optional[bool] = Field(
        None,
        description="Whether token budget was fully consumed during matching",
    )
    skipped_entries_due_to_budget: Optional[int] = Field(
        None,
        description="Number of matched entries skipped due to token budget",
    )
    diagnostics: list[ProcessContextDiagnostic] = Field(
        default_factory=list,
        description="Matched entry diagnostics for debugging",
    )


class WorldBookListResponse(BaseModel):
    """Response schema for listing world books."""
    world_books: list[WorldBookResponse] = Field(..., description="List of world books")
    total: int = Field(..., description="Total number of world books")
    enabled_count: int = Field(..., description="Number of enabled world books")
    disabled_count: int = Field(..., description="Number of disabled world books")


class WorldBookRuntimeConfig(BaseModel):
    """Runtime world-book config surfaced to frontend UIs."""
    max_recursive_depth: int = Field(
        ...,
        description="Maximum recursive scanning depth before recursive matching stops."
    )


class EntryListResponse(BaseModel):
    """Response schema for listing entries."""
    entries: list[WorldBookEntryResponse] = Field(..., description="List of entries")
    total: int = Field(..., description="Total number of entries")
    world_book_id: Optional[int] = Field(None, description="World book ID if filtered")


class WorldBookExport(BaseModel):
    """Schema for world book export."""
    world_book: dict[str, Any] = Field(..., description="World book data")
    entries: list[dict[str, Any]] = Field(..., description="World book entries")
    export_date: datetime = Field(default_factory=datetime.now, description="Export timestamp")
    format_version: str = Field("1.0", description="Export format version")


class WorldBookImportRequest(BaseModel):
    """Request schema for importing a world book."""
    world_book: dict[str, Any] = Field(..., description="World book data")
    entries: list[dict[str, Any]] = Field(default_factory=list, description="World book entries")
    merge_on_conflict: bool = Field(False, description="Merge with existing book of same name")


class WorldBookImportResponse(BaseModel):
    """Response schema for world book import."""
    world_book_id: int = Field(..., description="ID of imported/merged world book")
    name: str = Field(..., description="World book name")
    entries_imported: int = Field(..., description="Number of entries imported")
    merged: bool = Field(..., description="Whether merged with existing book")


class WorldBookStatistics(BaseModel):
    """Statistics for a world book."""
    world_book_id: int = Field(..., description="World book ID")
    name: str = Field(..., description="World book name")
    total_entries: int = Field(..., description="Total number of entries")
    enabled_entries: int = Field(..., description="Number of enabled entries")
    disabled_entries: int = Field(..., description="Number of disabled entries")
    total_keywords: int = Field(..., description="Total number of keywords")
    regex_entries: int = Field(..., description="Number of regex entries")
    case_sensitive_entries: int = Field(..., description="Number of case-sensitive entries")
    average_priority: float = Field(..., description="Average entry priority")
    total_content_length: int = Field(..., description="Total characters in all content")
    estimated_tokens: int = Field(..., description="Estimated total tokens")


class BulkEntryOperation(BaseModel):
    """Schema for bulk entry operations."""
    entry_ids: list[int] = Field(..., min_length=1, description="List of entry IDs")
    operation: str = Field(..., pattern="^(enable|disable|delete|set_priority)$", description="Operation to perform")
    priority: Optional[int] = Field(None, description="New priority (for set_priority operation)")


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations."""
    success: bool = Field(..., description="Whether operation succeeded")
    affected_count: int = Field(..., description="Number of entries affected")
    failed_ids: list[int] = Field(default_factory=list, description="IDs that failed")
    message: str = Field(..., description="Operation result message")


# Error response schemas
class WorldBookError(BaseModel):
    """Error response for world book operations."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[dict[str, Any]] = Field(None, description="Additional error details")


class WorldBookConflictError(WorldBookError):
    """Conflict error response."""
    error: str = Field("conflict", description="Error type")
    conflicting_name: Optional[str] = Field(None, description="Conflicting world book name")
    conflicting_id: Optional[int] = Field(None, description="Conflicting world book ID")


class WorldBookNotFoundError(WorldBookError):
    """Not found error response."""
    error: str = Field("not_found", description="Error type")
    resource_type: str = Field(..., description="Type of resource not found")
    resource_id: Optional[int] = Field(None, description="ID of missing resource")
