"""Query processing and optimization adapters.

This module includes adapters for query operations:
- query_rewrite: Rewrite search queries for better retrieval
- query_expand: Expand queries with synonyms and related terms
- hyde_generate: Generate hypothetical documents (HyDE)
- semantic_cache_check: Check semantic cache for similar queries
- search_aggregate: Aggregate and deduplicate search results
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.rag._config import (
    HyDEGenerateConfig,
    QueryExpandConfig,
    QueryRewriteConfig,
    SearchAggregateConfig,
    SemanticCacheCheckConfig,
)


@registry.register(
    "query_rewrite",
    category="rag",
    description="Rewrite search queries",
    parallelizable=True,
    tags=["rag", "query"],
    config_model=QueryRewriteConfig,
)
async def run_query_rewrite_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Rewrite a search query for better retrieval results.

    Config:
      - query: str (required, templated) - Original query to rewrite
      - strategy: Literal["expand", "clarify", "simplify", "all"] = "all"
      - provider: str - LLM provider for rewriting
      - model: str - Model to use
      - max_rewrites: int = 3 - Maximum number of rewritten queries
    Output:
      - {"original_query": str, "rewritten_queries": [str], "strategy": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_query_rewrite_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "query_expand",
    category="rag",
    description="Expand search queries",
    parallelizable=True,
    tags=["rag", "query"],
    config_model=QueryExpandConfig,
)
async def run_query_expand_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Expand search queries using multiple strategies.

    Config:
      - query: str (templated) - Query to expand
      - strategies: List[str] = ["synonym"] - Strategies to use
        Options: "acronym", "synonym", "domain", "entity", "multi_query", "hybrid"
      - max_expansions: int = 5 - Max expansions per strategy
      - domain_context: Optional[str] (templated) - For domain strategy
      - api_name: Optional[str] - For LLM-based strategies
    Output:
      - {"original": str, "variations": [str], "synonyms": [str],
         "keywords": [str], "entities": [str], "combined": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_query_expand_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "hyde_generate",
    category="rag",
    description="Generate hypothetical documents (HyDE)",
    parallelizable=True,
    tags=["rag", "query"],
    config_model=HyDEGenerateConfig,
)
async def run_hyde_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a Hypothetical Document Embedding (HyDE) for improved similarity search.

    Config:
      - query: str (required, templated) - The search query
      - provider: str - LLM provider
      - model: str - Model to use
      - num_hypothetical: int = 1 - Number of hypothetical documents
      - document_type: Literal["answer", "passage", "article"] = "passage"
    Output:
      - {"query": str, "hypothetical_documents": [str], "document_type": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_hyde_generate_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "semantic_cache_check",
    category="rag",
    description="Check semantic cache",
    parallelizable=True,
    tags=["rag", "cache"],
    config_model=SemanticCacheCheckConfig,
)
async def run_semantic_cache_check_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Check semantic cache for similar queries before running expensive searches.

    Config:
      - query: str (required, templated) - Query to check
      - cache_collection: str = "semantic_cache" - ChromaDB collection for cache
      - similarity_threshold: float = 0.9 - Minimum similarity for cache hit
      - max_age_seconds: int = 3600 - Maximum age of cached results
    Output:
      - {"cache_hit": bool, "cached_query": str, "cached_result": dict,
         "similarity": float, "query": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_semantic_cache_check_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "search_aggregate",
    category="rag",
    description="Aggregate search results",
    parallelizable=False,
    tags=["rag", "search"],
    config_model=SearchAggregateConfig,
)
async def run_search_aggregate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate and deduplicate results from multiple search steps.

    Config:
      - results: list[dict] - List of search results to aggregate
      - dedup_field: str = "id" - Field to use for deduplication
      - sort_by: str = "score" - Field to sort by
      - sort_order: Literal["asc", "desc"] = "desc"
      - limit: int = 20 - Maximum results to return
      - merge_scores: Literal["max", "sum", "avg"] = "max" - How to merge scores
    Output:
      - {"documents": [dict], "total_before_dedup": int,
         "total_after_dedup": int, "sources": [str]}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_search_aggregate_adapter as _legacy
    return await _legacy(config, context)
