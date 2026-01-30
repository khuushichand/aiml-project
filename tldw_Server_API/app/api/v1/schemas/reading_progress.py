# Reading Progress Schemas
# Schemas for document reading progress tracking
#
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ViewMode(str, Enum):
    """Document view modes."""

    single = "single"
    continuous = "continuous"
    thumbnails = "thumbnails"


class ReadingProgressUpdate(BaseModel):
    """Request body for updating reading progress."""

    current_page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    total_pages: int = Field(..., ge=1, description="Total pages in the document")
    zoom_level: int = Field(default=100, ge=25, le=400, description="Zoom level percentage")
    view_mode: ViewMode = Field(default=ViewMode.single, description="View mode")
    cfi: Optional[str] = Field(
        None, description="EPUB CFI (Canonical Fragment Identifier) for precise position"
    )
    percentage: Optional[float] = Field(
        None, ge=0, le=100, description="Reading progress percentage for EPUB"
    )


class ReadingProgressResponse(BaseModel):
    """Response containing reading progress for a document."""

    media_id: int = Field(..., description="ID of the media item")
    current_page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    total_pages: int = Field(..., ge=1, description="Total pages in the document")
    zoom_level: int = Field(default=100, ge=25, le=400, description="Zoom level percentage")
    view_mode: ViewMode = Field(default=ViewMode.single, description="View mode")
    percent_complete: float = Field(..., ge=0, le=100, description="Reading progress percentage")
    cfi: Optional[str] = Field(
        None, description="EPUB CFI for precise position restoration"
    )
    last_read_at: datetime = Field(..., description="When the document was last read")


class ReadingProgressNotFound(BaseModel):
    """Response when no reading progress exists for a document."""

    media_id: int = Field(..., description="ID of the media item")
    has_progress: bool = Field(default=False, description="Whether progress exists")


__all__ = [
    "ViewMode",
    "ReadingProgressUpdate",
    "ReadingProgressResponse",
    "ReadingProgressNotFound",
]
