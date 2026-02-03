# Document Insights Schemas
# Schemas for AI-generated document insights
#
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class InsightCategory(str, Enum):
    """Categories of insights that can be extracted from a document."""

    RESEARCH_GAP = "research_gap"
    RESEARCH_QUESTION = "research_question"
    MOTIVATION = "motivation"
    METHODS = "methods"
    KEY_FINDINGS = "key_findings"
    LIMITATIONS = "limitations"
    FUTURE_WORK = "future_work"
    SUMMARY = "summary"


class InsightItem(BaseModel):
    """A single insight extracted from the document."""

    category: InsightCategory = Field(..., description="Category of the insight")
    title: str = Field(..., description="Short title for the insight")
    content: str = Field(..., description="Detailed insight content")
    confidence: float | None = Field(
        None, ge=0, le=1, description="Confidence score for the insight"
    )


class GenerateInsightsRequest(BaseModel):
    """Request parameters for generating document insights."""

    categories: list[InsightCategory] | None = Field(
        None,
        description="Specific categories to generate (None = all categories)",
    )
    model: str | None = Field(
        None,
        description="LLM model to use for insight generation",
    )
    max_content_length: int | None = Field(
        5000,
        ge=500,
        le=50000,
        description="Maximum characters of document content to analyze",
    )
    force: bool | None = Field(
        False,
        description="Bypass cached insights and force a fresh LLM call",
    )


class DocumentInsightsResponse(BaseModel):
    """Response containing generated document insights."""

    media_id: int = Field(..., description="ID of the media item")
    insights: list[InsightItem] = Field(
        default_factory=list, description="List of generated insights"
    )
    model_used: str = Field(..., description="LLM model used for generation")
    cached: bool = Field(
        False, description="Whether the result was retrieved from cache"
    )


__all__ = [
    "InsightCategory",
    "InsightItem",
    "GenerateInsightsRequest",
    "DocumentInsightsResponse",
]
