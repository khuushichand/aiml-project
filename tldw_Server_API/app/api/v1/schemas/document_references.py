# Document References Schemas
# Schemas for bibliography/reference extraction from documents
#
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ReferenceEntry(BaseModel):
    """A single reference/citation extracted from the document."""

    raw_text: str = Field(..., description="Original reference text as found in document")
    title: Optional[str] = Field(None, description="Parsed title of the referenced work")
    authors: Optional[str] = Field(None, description="Authors of the referenced work")
    year: Optional[int] = Field(None, ge=1000, le=2100, description="Publication year")
    venue: Optional[str] = Field(None, description="Journal, conference, or publisher")
    doi: Optional[str] = Field(None, description="Digital Object Identifier")
    arxiv_id: Optional[str] = Field(None, description="arXiv paper ID (e.g., 2301.12345)")
    url: Optional[str] = Field(None, description="URL to the referenced work")
    # Enriched fields from external APIs
    citation_count: Optional[int] = Field(None, ge=0, description="Citation count from external API")
    semantic_scholar_id: Optional[str] = Field(None, description="Semantic Scholar paper ID")
    open_access_pdf: Optional[str] = Field(None, description="URL to open access PDF")


class DocumentReferencesResponse(BaseModel):
    """Response containing references extracted from a document."""

    media_id: int = Field(..., description="ID of the media item")
    has_references: bool = Field(..., description="Whether references were found")
    references: List[ReferenceEntry] = Field(
        default_factory=list, description="List of extracted references"
    )
    enrichment_source: Optional[str] = Field(
        None,
        description="External API used for enrichment (semantic_scholar, crossref, arxiv)",
    )


__all__ = ["ReferenceEntry", "DocumentReferencesResponse"]
