"""Pydantic config models for RAG adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class RAGSearchConfig(BaseAdapterConfig):
    """Config for RAG search adapter."""

    query: str = Field(..., description="Search query (templated)")
    collection: Optional[str] = Field(None, description="Collection/namespace to search")
    top_k: int = Field(5, ge=1, le=100, description="Number of results to return")
    min_score: Optional[float] = Field(None, ge=0, le=1, description="Minimum similarity score")
    filters: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    rerank: bool = Field(False, description="Apply reranking to results")
    rerank_model: Optional[str] = Field(None, description="Model for reranking")
    hybrid: bool = Field(True, description="Use hybrid search (vector + keyword)")
    fts_weight: float = Field(0.3, ge=0, le=1, description="Weight for full-text search")
    include_content: bool = Field(True, description="Include full content in results")


class WebSearchConfig(BaseAdapterConfig):
    """Config for web search adapter."""

    query: str = Field(..., description="Search query (templated)")
    provider: Literal["serper", "tavily", "brave", "duckduckgo", "searxng"] = Field(
        "tavily", description="Search provider"
    )
    num_results: int = Field(10, ge=1, le=50, description="Number of results")
    include_domains: Optional[List[str]] = Field(None, description="Limit to specific domains")
    exclude_domains: Optional[List[str]] = Field(None, description="Exclude specific domains")
    time_range: Optional[Literal["day", "week", "month", "year"]] = Field(
        None, description="Time range filter"
    )
    safe_search: bool = Field(True, description="Enable safe search")
    fetch_content: bool = Field(False, description="Fetch and extract page content")


class RSSFetchConfig(BaseAdapterConfig):
    """Config for RSS/Atom feed fetching adapter."""

    url: str = Field(..., description="RSS/Atom feed URL (required)")
    limit: int = Field(10, ge=1, le=100, description="Maximum items to fetch")
    since: Optional[str] = Field(None, description="Fetch items since date (ISO format)")
    include_content: bool = Field(True, description="Include full content if available")


class QueryRewriteConfig(BaseAdapterConfig):
    """Config for query rewriting adapter."""

    query: str = Field(..., description="Original query to rewrite (templated)")
    style: Literal["expand", "clarify", "simplify", "academic", "conversational"] = Field(
        "expand", description="Rewriting style"
    )
    provider: Optional[str] = Field(None, description="LLM provider for rewriting")
    model: Optional[str] = Field(None, description="Model for rewriting")
    num_variants: int = Field(1, ge=1, le=5, description="Number of rewritten variants")


class QueryExpandConfig(BaseAdapterConfig):
    """Config for query expansion adapter."""

    query: str = Field(..., description="Original query to expand (templated)")
    method: Literal["synonyms", "related", "llm", "hybrid"] = Field(
        "llm", description="Expansion method"
    )
    provider: Optional[str] = Field(None, description="LLM provider for expansion")
    model: Optional[str] = Field(None, description="Model for expansion")
    max_terms: int = Field(10, ge=1, le=50, description="Maximum expansion terms")


class HyDEGenerateConfig(BaseAdapterConfig):
    """Config for HyDE (Hypothetical Document Embeddings) adapter."""

    query: str = Field(..., description="Query to generate hypothetical doc for (templated)")
    provider: Optional[str] = Field(None, description="LLM provider")
    model: Optional[str] = Field(None, description="Model for generation")
    num_docs: int = Field(1, ge=1, le=5, description="Number of hypothetical docs")
    doc_type: Optional[str] = Field(None, description="Type of document to generate")


class SemanticCacheCheckConfig(BaseAdapterConfig):
    """Config for semantic cache check adapter."""

    query: str = Field(..., description="Query to check in cache (templated)")
    threshold: float = Field(0.95, ge=0.5, le=1.0, description="Similarity threshold for cache hit")
    namespace: Optional[str] = Field(None, description="Cache namespace")
    ttl_seconds: Optional[int] = Field(None, ge=0, description="Cache TTL in seconds")


class SearchAggregateConfig(BaseAdapterConfig):
    """Config for search results aggregation adapter."""

    results: List[Dict[str, Any]] = Field(..., description="List of search result sets to aggregate")
    strategy: Literal["merge", "interleave", "dedupe", "rerank"] = Field(
        "merge", description="Aggregation strategy"
    )
    top_k: int = Field(10, ge=1, le=100, description="Number of results after aggregation")
    dedupe_field: Optional[str] = Field(None, description="Field to use for deduplication")
