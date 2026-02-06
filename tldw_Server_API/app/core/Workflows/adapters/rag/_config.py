"""Pydantic config models for RAG adapters."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from tldw_Server_API.app.core.Workflows.adapters._base import BaseAdapterConfig


class RAGSearchConfig(BaseAdapterConfig):
    """Config for RAG search adapter."""

    query: str = Field(..., description="Search query (templated)")
    collection: str | None = Field(None, description="Collection/namespace to search")
    top_k: int = Field(5, ge=1, le=100, description="Number of results to return")
    min_score: float | None = Field(None, ge=0, le=1, description="Minimum similarity score")
    filters: dict[str, Any] | None = Field(None, description="Metadata filters")
    rerank: bool = Field(False, description="Apply reranking to results")
    rerank_model: str | None = Field(None, description="Model for reranking")
    hybrid: bool = Field(True, description="Use hybrid search (vector + keyword)")
    fts_weight: float = Field(0.3, ge=0, le=1, description="Weight for full-text search")
    include_content: bool = Field(True, description="Include full content in results")


class WebSearchConfig(BaseAdapterConfig):
    """Config for web search adapter."""

    query: str = Field(..., description="Search query (templated)")
    engine: Literal[
        "google",
        "duckduckgo",
        "brave",
        "kagi",
        "tavily",
        "searx",
        "searxng",
        "exa",
        "firecrawl",
        "baidu",
        "bing",
        "yandex",
        "sogou",
        "startpage",
        "stract",
        "serper",
    ] = Field(
        "google", description="Search engine/provider"
    )
    provider: str | None = Field(None, description="Deprecated alias for engine")
    auto_query_rewrite: bool = Field(False, description="Rewrite query before search using query_rewrite adapter")
    query_rewrite_strategy: Literal["expand", "clarify", "simplify", "all"] = Field(
        "simplify", description="Strategy for auto query rewrite"
    )
    query_rewrite_max_rewrites: int = Field(1, ge=1, le=5, description="Number of rewrite candidates to generate")
    query_rewrite_provider: str | None = Field(None, description="Optional LLM provider override for query rewrite")
    query_rewrite_model: str | None = Field(None, description="Optional LLM model override for query rewrite")
    num_results: int = Field(10, ge=1, le=50, description="Number of results")
    result_count: int | None = Field(None, ge=1, le=50, description="Deprecated alias for num_results")
    content_country: str = Field("US", description="Country code for localized results")
    country: str | None = Field(None, description="Deprecated alias for content_country")
    search_lang: str = Field("en", description="Search language")
    search_language: str | None = Field(None, description="Deprecated alias for search_lang")
    output_lang: str = Field("en", description="Output language")
    output_language: str | None = Field(None, description="Deprecated alias for output_lang")
    ui_lang: str | None = Field(None, description="Deprecated alias for output_lang")
    safesearch: str | bool = Field("active", description="Safe search mode (or bool)")
    date_range: str | None = Field(None, description="Provider date range filter")
    include_domains: list[str] | None = Field(None, description="Limit to specific domains")
    exclude_domains: list[str] | None = Field(None, description="Exclude specific domains")
    site_whitelist: list[str] | None = Field(None, description="Deprecated alias for include_domains")
    site_blacklist: list[str] | None = Field(None, description="Deprecated alias for exclude_domains")
    exact_terms: str | None = Field(None, description="Exact terms filter (alias: exactTerms)")
    exclude_terms: str | None = Field(None, description="Excluded terms filter (alias: excludeTerms)")
    time_range: Literal["day", "week", "month", "year"] | None = Field(
        None, description="Deprecated alias for date_range"
    )
    safe_search: bool = Field(True, description="Deprecated alias for safesearch")
    searx_url: str | None = Field(None, description="Optional custom Searx endpoint URL")
    searx_json_mode: bool = Field(False, description="Request JSON mode from Searx if available")
    summarize: bool = Field(False, description="Summarize results with LLM")
    api_name: str | None = Field(None, description="LLM provider for summarization")
    api_provider: str | None = Field(None, description="Deprecated alias for api_name")
    fetch_content: bool = Field(False, description="Fetch and extract page content")
    fetch_limit: int = Field(3, ge=0, le=50, description="Max results to enrich with fetched page content")
    filter_failed_fetches: bool = Field(True, description="Drop failed content fetches from enriched output")
    max_content_tokens: int = Field(1200, ge=32, description="Token budget per fetched page content")
    fetch_timeout_seconds: float = Field(12.0, gt=0, le=120.0, description="Timeout for each page-content fetch")
    tokenizer_model: str | None = Field(None, description="Optional model name for token counting during truncation")


class RSSFetchConfig(BaseAdapterConfig):
    """Config for RSS/Atom feed fetching adapter."""

    url: str = Field(..., description="RSS/Atom feed URL (required)")
    limit: int = Field(10, ge=1, le=100, description="Maximum items to fetch")
    since: str | None = Field(None, description="Fetch items since date (ISO format)")
    include_content: bool = Field(True, description="Include full content if available")


class QueryRewriteConfig(BaseAdapterConfig):
    """Config for query rewriting adapter."""

    query: str = Field(..., description="Original query to rewrite (templated)")
    style: Literal["expand", "clarify", "simplify", "academic", "conversational"] = Field(
        "expand", description="Rewriting style"
    )
    provider: str | None = Field(None, description="LLM provider for rewriting")
    model: str | None = Field(None, description="Model for rewriting")
    num_variants: int = Field(1, ge=1, le=5, description="Number of rewritten variants")


class QueryExpandConfig(BaseAdapterConfig):
    """Config for query expansion adapter."""

    query: str = Field(..., description="Original query to expand (templated)")
    method: Literal["synonyms", "related", "llm", "hybrid"] = Field(
        "llm", description="Expansion method"
    )
    provider: str | None = Field(None, description="LLM provider for expansion")
    model: str | None = Field(None, description="Model for expansion")
    max_terms: int = Field(10, ge=1, le=50, description="Maximum expansion terms")


class HyDEGenerateConfig(BaseAdapterConfig):
    """Config for HyDE (Hypothetical Document Embeddings) adapter."""

    query: str = Field(..., description="Query to generate hypothetical doc for (templated)")
    provider: str | None = Field(None, description="LLM provider")
    model: str | None = Field(None, description="Model for generation")
    num_docs: int = Field(1, ge=1, le=5, description="Number of hypothetical docs")
    doc_type: str | None = Field(None, description="Type of document to generate")


class SemanticCacheCheckConfig(BaseAdapterConfig):
    """Config for semantic cache check adapter."""

    query: str = Field(..., description="Query to check in cache (templated)")
    threshold: float = Field(0.95, ge=0.5, le=1.0, description="Similarity threshold for cache hit")
    namespace: str | None = Field(None, description="Cache namespace")
    ttl_seconds: int | None = Field(None, ge=0, description="Cache TTL in seconds")


class SearchAggregateConfig(BaseAdapterConfig):
    """Config for search results aggregation adapter."""

    results: list[dict[str, Any]] = Field(..., description="List of search result sets to aggregate")
    strategy: Literal["merge", "interleave", "dedupe", "rerank"] = Field(
        "merge", description="Aggregation strategy"
    )
    top_k: int = Field(10, ge=1, le=100, description="Number of results after aggregation")
    dedupe_field: str | None = Field(None, description="Field to use for deduplication")
