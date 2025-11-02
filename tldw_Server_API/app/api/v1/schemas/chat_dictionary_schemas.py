# chat_dictionary_schemas.py
# Description: Pydantic schemas for Chat Dictionary API endpoints
#
"""
Pydantic schemas for Chat Dictionary functionality.

These schemas define the request and response models for the chat dictionary
API endpoints, ensuring proper validation and serialization.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TimedEffects(BaseModel):
    """Timed effects configuration for dictionary entries."""
    sticky: int = Field(0, ge=0, description="Sticky duration in seconds")
    cooldown: int = Field(0, ge=0, description="Cooldown between triggers in seconds")
    delay: int = Field(0, ge=0, description="Initial delay before first trigger in seconds")


class DictionaryEntryBase(BaseModel):
    """Base schema for dictionary entries."""
    pattern: str = Field(..., min_length=1, description="Pattern to match (literal or regex)")
    replacement: str = Field(..., description="Replacement text")
    probability: float = Field(1.0, ge=0.0, le=1.0, description="Chance of replacement (0.0-1.0)")
    group: Optional[str] = Field(None, description="Optional group name for organization")
    timed_effects: Optional[TimedEffects] = Field(None, description="Timing effects configuration")
    max_replacements: int = Field(0, ge=0, description="Maximum replacements per processing (0 = unlimited)")


class DictionaryEntryCreate(DictionaryEntryBase):
    """Schema for creating a dictionary entry."""
    type: str = Field("literal", pattern="^(literal|regex)$", description="Entry type")
    enabled: bool = Field(True, description="Whether the entry is enabled")
    case_sensitive: bool = Field(True, description="Case-sensitive matching for literal patterns")


class DictionaryEntryUpdate(BaseModel):
    """Schema for updating a dictionary entry."""
    pattern: Optional[str] = Field(None, min_length=1, description="New pattern to match")
    replacement: Optional[str] = Field(None, description="New replacement text")
    probability: Optional[float] = Field(None, ge=0.0, le=1.0, description="New probability (0.0-1.0)")
    group: Optional[str] = Field(None, description="New group name")
    timed_effects: Optional[TimedEffects] = Field(None, description="New timing effects")
    max_replacements: Optional[int] = Field(None, ge=0, description="New max replacements (0 = unlimited)")
    type: Optional[str] = Field(None, pattern="^(literal|regex)$", description="Entry type")
    enabled: Optional[bool] = Field(None, description="Whether the entry is enabled")
    case_sensitive: Optional[bool] = Field(None, description="Case-sensitive matching for literal patterns")


class DictionaryEntryResponse(DictionaryEntryBase):
    """Schema for dictionary entry response."""
    id: int = Field(..., description="Entry ID")
    dictionary_id: int = Field(..., description="Parent dictionary ID")
    type: str = Field(..., description="Entry type")
    enabled: bool = Field(..., description="Whether the entry is enabled")
    case_sensitive: bool = Field(..., description="Case-sensitive matching for literal patterns")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class ChatDictionaryBase(BaseModel):
    """Base schema for chat dictionaries."""
    name: str = Field(..., min_length=1, max_length=100, description="Unique dictionary name")
    description: Optional[str] = Field(None, max_length=500, description="Dictionary description")
    is_active: bool = Field(True, description="Whether the dictionary is active")


class ChatDictionaryCreate(BaseModel):
    """Schema for creating a chat dictionary."""
    name: str = Field(..., min_length=1, max_length=100, description="Unique dictionary name")
    description: Optional[str] = Field(None, max_length=500, description="Dictionary description")


class ChatDictionaryUpdate(BaseModel):
    """Schema for updating a chat dictionary."""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New dictionary name")
    description: Optional[str] = Field(None, max_length=500, description="New description")
    is_active: Optional[bool] = Field(None, description="New active status")


class ChatDictionaryResponse(ChatDictionaryBase):
    """Schema for chat dictionary response."""
    id: int = Field(..., description="Dictionary ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    version: int = Field(..., description="Version number for optimistic locking")
    entry_count: Optional[int] = Field(None, description="Number of entries in the dictionary")

    model_config = ConfigDict(from_attributes=True)


class ChatDictionaryWithEntries(ChatDictionaryResponse):
    """Schema for chat dictionary with its entries."""
    entries: List[DictionaryEntryResponse] = Field(default_factory=list, description="Dictionary entries")


class ProcessTextRequest(BaseModel):
    """Request schema for processing text through dictionaries."""
    text: str = Field(..., description="Text to process")
    dictionary_id: Optional[int] = Field(None, description="Specific dictionary to use")
    group: Optional[str] = Field(None, description="Specific group to filter entries")
    max_iterations: int = Field(5, ge=1, le=20, description="Maximum processing iterations")
    token_budget: Optional[int] = Field(None, ge=1, description="Optional token limit")


class ProcessTextResponse(BaseModel):
    """Response schema for processed text."""
    original_text: str = Field(..., description="Original input text")
    processed_text: str = Field(..., description="Text after processing")
    replacements: int = Field(..., description="Total number of replacements made")
    iterations: int = Field(..., description="Number of iterations performed")
    entries_used: List[int] = Field(..., description="IDs of entries that made replacements")
    token_budget_exceeded: bool = Field(False, description="Whether token budget was exceeded")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")


class ImportDictionaryRequest(BaseModel):
    """Request schema for importing a dictionary from markdown."""
    name: str = Field(..., min_length=1, max_length=100, description="Name for the imported dictionary")
    content: str = Field(..., description="Markdown content to import")
    activate: bool = Field(True, description="Whether to activate the dictionary after import")


class ImportDictionaryResponse(BaseModel):
    """Response schema for dictionary import."""
    dictionary_id: int = Field(..., description="ID of the created dictionary")
    name: str = Field(..., description="Dictionary name")
    entries_imported: int = Field(..., description="Number of entries imported")
    groups_created: List[str] = Field(..., description="List of groups found and created")


class ExportDictionaryResponse(BaseModel):
    """Response schema for dictionary export."""
    name: str = Field(..., description="Dictionary name")
    content: str = Field(..., description="Exported content in markdown format")
    entry_count: int = Field(..., description="Number of entries exported")
    group_count: int = Field(..., description="Number of groups in the dictionary")

class ImportDictionaryJSONRequest(BaseModel):
    """Request schema for importing a dictionary from JSON."""
    data: Dict[str, Any] = Field(..., description="Dictionary JSON data with 'name' and 'entries'")
    activate: bool = Field(True, description="Whether to activate the dictionary after import")

class ExportDictionaryJSONResponse(BaseModel):
    """Response schema for JSON export of a dictionary."""
    name: str = Field(..., description="Dictionary name")
    description: Optional[str] = Field(None, description="Dictionary description")
    entries: List[Dict[str, Any]] = Field(..., description="Entries with pattern, replacement, type, probability, etc.")


class BulkEntryOperation(BaseModel):
    """Schema for bulk entry operations."""
    entry_ids: List[int] = Field(..., min_length=1, description="List of entry IDs to operate on")
    operation: str = Field(..., pattern="^(delete|activate|deactivate|group)$", description="Operation to perform")
    group_name: Optional[str] = Field(None, description="Group name (for group operation)")


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations."""
    success: bool = Field(..., description="Whether the operation succeeded")
    affected_count: int = Field(..., description="Number of entries affected")
    failed_ids: List[int] = Field(default_factory=list, description="IDs that failed to process")
    message: str = Field(..., description="Operation result message")


class DictionaryStatistics(BaseModel):
    """Statistics for a dictionary."""
    dictionary_id: int = Field(..., description="Dictionary ID")
    name: str = Field(..., description="Dictionary name")
    total_entries: int = Field(..., description="Total number of entries")
    regex_entries: int = Field(..., description="Number of regex entries")
    literal_entries: int = Field(..., description="Number of literal entries")
    groups: List[str] = Field(..., description="List of unique groups")
    average_probability: float = Field(..., description="Average replacement probability")
    total_usage_count: Optional[int] = Field(None, description="Total times used (if tracked)")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp (if tracked)")


class DictionaryListResponse(BaseModel):
    """Response schema for listing dictionaries."""
    dictionaries: List[ChatDictionaryResponse] = Field(..., description="List of dictionaries")
    total: int = Field(..., description="Total number of dictionaries")
    active_count: int = Field(..., description="Number of active dictionaries")
    inactive_count: int = Field(..., description="Number of inactive dictionaries")


class EntryListResponse(BaseModel):
    """Response schema for listing entries."""
    entries: List[DictionaryEntryResponse] = Field(..., description="List of entries")
    total: int = Field(..., description="Total number of entries")
    dictionary_id: Optional[int] = Field(None, description="Dictionary ID if filtered")
    group: Optional[str] = Field(None, description="Group name if filtered")


# Error response schemas
class DictionaryError(BaseModel):
    """Error response for dictionary operations."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class DictionaryConflictError(DictionaryError):
    """Conflict error response."""
    error: str = Field("conflict", description="Error type")
    conflicting_name: Optional[str] = Field(None, description="Conflicting dictionary name")
    conflicting_id: Optional[int] = Field(None, description="Conflicting dictionary ID")


class DictionaryNotFoundError(DictionaryError):
    """Not found error response."""
    error: str = Field("not_found", description="Error type")
    resource_type: str = Field(..., description="Type of resource not found")
    resource_id: Optional[Union[int, str]] = Field(None, description="ID of missing resource")
