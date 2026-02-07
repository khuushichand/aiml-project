# Translation API Schemas
# Schemas for text translation endpoint
#
from __future__ import annotations

from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    """Request model for text translation."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Text to translate (max 10,000 characters)"
    )
    target_language: str = Field(
        default="English",
        description="Target language for translation"
    )
    source_language: str | None = Field(
        default=None,
        description="Source language (auto-detect if None)"
    )
    model: str | None = Field(
        default=None,
        description="LLM model to use for translation"
    )
    provider: str | None = Field(
        default=None,
        description="LLM provider to use (defaults to configured default)"
    )


class TranslateResponse(BaseModel):
    """Response model for text translation."""

    translated_text: str = Field(
        ...,
        description="The translated text"
    )
    detected_source_language: str | None = Field(
        default=None,
        description="Detected source language (if auto-detected)"
    )
    target_language: str = Field(
        ...,
        description="The target language used"
    )
    model_used: str = Field(
        ...,
        description="The LLM model used for translation"
    )


__all__ = ["TranslateRequest", "TranslateResponse"]
