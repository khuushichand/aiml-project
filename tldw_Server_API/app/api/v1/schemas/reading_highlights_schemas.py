from __future__ import annotations

from datetime import datetime
from typing import Literal

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
    start_offset: int | None = Field(None, ge=0)
    end_offset: int | None = Field(None, ge=0)
    color: str | None = Field(None, max_length=32)
    note: str | None = Field(None, max_length=2000)
    anchor_strategy: AnchorStrategy = "fuzzy_quote"


class HighlightUpdateRequest(BaseModel):
    """Update mutable highlight properties."""

    color: str | None = Field(None, max_length=32)
    note: str | None = Field(None, max_length=2000)
    state: HighlightState | None = None


class Highlight(BaseModel):
    id: int
    item_id: int
    quote: str
    start_offset: int | None = None
    end_offset: int | None = None
    color: str | None = None
    note: str | None = None
    created_at: datetime

    # Anchoring
    anchor_strategy: AnchorStrategy
    content_hash_ref: str | None = None
    context_before: str | None = None
    context_after: str | None = None
    state: HighlightState = "active"
