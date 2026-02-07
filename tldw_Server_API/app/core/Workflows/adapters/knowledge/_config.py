"""Pydantic config models for knowledge adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class NotesConfig(BaseAdapterConfig):
    """Config for notes adapter."""

    action: Literal["create", "read", "update", "delete", "list", "search"] = Field(
        "create", description="Action to perform"
    )
    note_id: str | None = Field(None, description="Note ID for read/update/delete")
    title: str | None = Field(None, description="Note title (for create/update)")
    content: str | None = Field(None, description="Note content (templated)")
    tags: list[str] | None = Field(None, description="Tags for the note")
    notebook_id: str | None = Field(None, description="Notebook to associate with")
    query: str | None = Field(None, description="Search query (for search action)")
    limit: int = Field(20, ge=1, le=100, description="Maximum results for list/search")


class PromptsConfig(BaseAdapterConfig):
    """Config for prompts adapter."""

    action: Literal["create", "read", "update", "delete", "list", "search"] = Field(
        "create", description="Action to perform"
    )
    prompt_id: str | None = Field(None, description="Prompt ID for read/update/delete")
    name: str | None = Field(None, description="Prompt name")
    content: str | None = Field(None, description="Prompt content (templated)")
    description: str | None = Field(None, description="Prompt description")
    tags: list[str] | None = Field(None, description="Tags for the prompt")
    category: str | None = Field(None, description="Prompt category")
    query: str | None = Field(None, description="Search query (for search action)")
    limit: int = Field(20, ge=1, le=100, description="Maximum results for list/search")


class CollectionsConfig(BaseAdapterConfig):
    """Config for collections adapter."""

    action: Literal["create", "read", "update", "delete", "list", "add_items", "remove_items"] = Field(
        "create", description="Action to perform"
    )
    collection_id: str | None = Field(None, description="Collection ID")
    name: str | None = Field(None, description="Collection name")
    description: str | None = Field(None, description="Collection description")
    items: list[str] | None = Field(None, description="Item IDs to add/remove")
    metadata: dict[str, Any] | None = Field(None, description="Collection metadata")
    limit: int = Field(20, ge=1, le=100, description="Maximum results for list")


class ChunkingConfig(BaseAdapterConfig):
    """Config for text chunking adapter."""

    text: str = Field(..., description="Text to chunk (templated)")
    method: Literal["sentences", "words", "paragraphs", "tokens", "semantic", "recursive"] = Field(
        "sentences", description="Chunking method"
    )
    max_size: int = Field(500, ge=50, le=10000, description="Maximum chunk size")
    overlap: int = Field(50, ge=0, le=500, description="Overlap between chunks")
    language: str | None = Field(None, description="Language hint for chunking")
    separator: str | None = Field(None, description="Custom separator for splitting")


class ClaimsExtractConfig(BaseAdapterConfig):
    """Config for claims extraction adapter."""

    text: str = Field(..., description="Text to extract claims from (templated)")
    claim_types: list[str] | None = Field(
        None, description="Types of claims to extract (factual, opinion, etc.)"
    )
    min_confidence: float = Field(0.5, ge=0, le=1, description="Minimum confidence threshold")
    include_evidence: bool = Field(True, description="Include supporting evidence")
    provider: str | None = Field(None, description="LLM provider for extraction")
    model: str | None = Field(None, description="Model for extraction")


class VoiceIntentConfig(BaseAdapterConfig):
    """Config for voice intent detection adapter."""

    audio_uri: str | None = Field(None, description="file:// path to audio file")
    text: str | None = Field(None, description="Transcribed text (if already available)")
    intents: list[str] | None = Field(None, description="List of possible intents")
    include_entities: bool = Field(True, description="Extract named entities")
    include_sentiment: bool = Field(True, description="Include sentiment analysis")
    provider: str | None = Field(None, description="LLM provider for intent detection")
    model: str | None = Field(None, description="Model for intent detection")
