"""Pydantic config models for knowledge adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class NotesConfig(BaseAdapterConfig):
    """Config for notes adapter."""

    action: Literal["create", "read", "update", "delete", "list", "search"] = Field(
        "create", description="Action to perform"
    )
    note_id: Optional[str] = Field(None, description="Note ID for read/update/delete")
    title: Optional[str] = Field(None, description="Note title (for create/update)")
    content: Optional[str] = Field(None, description="Note content (templated)")
    tags: Optional[List[str]] = Field(None, description="Tags for the note")
    notebook_id: Optional[str] = Field(None, description="Notebook to associate with")
    query: Optional[str] = Field(None, description="Search query (for search action)")
    limit: int = Field(20, ge=1, le=100, description="Maximum results for list/search")


class PromptsConfig(BaseAdapterConfig):
    """Config for prompts adapter."""

    action: Literal["create", "read", "update", "delete", "list", "search"] = Field(
        "create", description="Action to perform"
    )
    prompt_id: Optional[str] = Field(None, description="Prompt ID for read/update/delete")
    name: Optional[str] = Field(None, description="Prompt name")
    content: Optional[str] = Field(None, description="Prompt content (templated)")
    description: Optional[str] = Field(None, description="Prompt description")
    tags: Optional[List[str]] = Field(None, description="Tags for the prompt")
    category: Optional[str] = Field(None, description="Prompt category")
    query: Optional[str] = Field(None, description="Search query (for search action)")
    limit: int = Field(20, ge=1, le=100, description="Maximum results for list/search")


class CollectionsConfig(BaseAdapterConfig):
    """Config for collections adapter."""

    action: Literal["create", "read", "update", "delete", "list", "add_items", "remove_items"] = Field(
        "create", description="Action to perform"
    )
    collection_id: Optional[str] = Field(None, description="Collection ID")
    name: Optional[str] = Field(None, description="Collection name")
    description: Optional[str] = Field(None, description="Collection description")
    items: Optional[List[str]] = Field(None, description="Item IDs to add/remove")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Collection metadata")
    limit: int = Field(20, ge=1, le=100, description="Maximum results for list")


class ChunkingConfig(BaseAdapterConfig):
    """Config for text chunking adapter."""

    text: str = Field(..., description="Text to chunk (templated)")
    method: Literal["sentences", "words", "paragraphs", "tokens", "semantic", "recursive"] = Field(
        "sentences", description="Chunking method"
    )
    max_size: int = Field(500, ge=50, le=10000, description="Maximum chunk size")
    overlap: int = Field(50, ge=0, le=500, description="Overlap between chunks")
    language: Optional[str] = Field(None, description="Language hint for chunking")
    separator: Optional[str] = Field(None, description="Custom separator for splitting")


class ClaimsExtractConfig(BaseAdapterConfig):
    """Config for claims extraction adapter."""

    text: str = Field(..., description="Text to extract claims from (templated)")
    claim_types: Optional[List[str]] = Field(
        None, description="Types of claims to extract (factual, opinion, etc.)"
    )
    min_confidence: float = Field(0.5, ge=0, le=1, description="Minimum confidence threshold")
    include_evidence: bool = Field(True, description="Include supporting evidence")
    provider: Optional[str] = Field(None, description="LLM provider for extraction")
    model: Optional[str] = Field(None, description="Model for extraction")


class VoiceIntentConfig(BaseAdapterConfig):
    """Config for voice intent detection adapter."""

    audio_uri: Optional[str] = Field(None, description="file:// path to audio file")
    text: Optional[str] = Field(None, description="Transcribed text (if already available)")
    intents: Optional[List[str]] = Field(None, description="List of possible intents")
    include_entities: bool = Field(True, description="Extract named entities")
    include_sentiment: bool = Field(True, description="Include sentiment analysis")
    provider: Optional[str] = Field(None, description="LLM provider for intent detection")
    model: Optional[str] = Field(None, description="Model for intent detection")
