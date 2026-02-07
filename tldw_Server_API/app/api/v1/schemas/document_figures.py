# Document Figures Schemas
# Schemas for figure/image extraction from PDF documents
#
from __future__ import annotations

from pydantic import BaseModel, Field


class Figure(BaseModel):
    """A single figure/image extracted from a document."""

    id: str = Field(..., description="Unique identifier for this figure")
    page: int = Field(..., ge=1, description="1-indexed page number where figure appears")
    width: int = Field(..., ge=1, description="Width of the image in pixels")
    height: int = Field(..., ge=1, description="Height of the image in pixels")
    format: str = Field(..., description="Image format (png, jpeg, etc.)")
    data_url: str | None = Field(
        default=None,
        description="Base64-encoded data URL for the image"
    )
    caption: str | None = Field(
        default=None,
        description="Figure caption if detected"
    )


class DocumentFiguresResponse(BaseModel):
    """Response containing extracted figures from a document."""

    media_id: int = Field(..., description="ID of the media item")
    has_figures: bool = Field(..., description="Whether the document has extractable figures")
    figures: list[Figure] = Field(
        default_factory=list,
        description="List of extracted figures"
    )
    total_count: int = Field(..., ge=0, description="Total number of figures found")


__all__ = ["Figure", "DocumentFiguresResponse"]
