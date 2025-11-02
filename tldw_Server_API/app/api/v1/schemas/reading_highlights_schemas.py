from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


AnchorStrategy = Literal["fuzzy_quote", "exact_offset"]
HighlightState = Literal["active", "stale"]


class HighlightCreateRequest(BaseModel):
    """Create a highlight anchored to a content item.

    Offsets are advisory; `fuzzy_quote` anchoring is preferred and will attempt
    to re-anchor on content changes using the stored quote and context.
    """

    item_id: int
    quote: str = Field(..., min_length=1)
    start_offset: Optional[int] = Field(None, ge=0)
    end_offset: Optional[int] = Field(None, ge=0)
    color: Optional[str] = Field(None, max_length=32)
    note: Optional[str] = Field(None, max_length=2000)
    anchor_strategy: AnchorStrategy = "fuzzy_quote"


class HighlightUpdateRequest(BaseModel):
    """Update mutable highlight properties."""

    color: Optional[str] = Field(None, max_length=32)
    note: Optional[str] = Field(None, max_length=2000)
    state: Optional[HighlightState] = None


class Highlight(BaseModel):
    id: int
    item_id: int
    quote: str
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    color: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime

    # Anchoring
    anchor_strategy: AnchorStrategy
    content_hash_ref: Optional[str] = None
    context_before: Optional[str] = None
    context_after: Optional[str] = None
    state: HighlightState = "active"
