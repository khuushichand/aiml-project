"""RAG and web search adapters.

This module includes adapters for search operations:
- rag_search: Execute RAG search using unified pipeline
- web_search: Web search via various engines
- rss_fetch: Fetch RSS/Atom feeds
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.rag._config import (
    RAGSearchConfig,
    RSSFetchConfig,
    WebSearchConfig,
)


@registry.register(
    "rag_search",
    category="rag",
    description="Execute RAG search",
    parallelizable=True,
    tags=["rag", "search"],
    config_model=RAGSearchConfig,
)
async def run_rag_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a RAG search via the unified pipeline.

    Config:
      - query: str (templated) - Search query
      - sources: list[str] = ["media_db"] - Data sources
      - search_mode: Literal["fts", "vector", "hybrid"] = "hybrid"
      - top_k: int = 10 - Number of results
      - hybrid_alpha: float = 0.7 - Weight for hybrid search
      - min_score: float - Minimum relevance score
      - expand_query: bool - Enable query expansion
      - enable_cache: bool - Enable caching
      - enable_reranking: bool - Enable reranking
      - enable_citations: bool - Enable citation generation
      - enable_generation: bool - Enable answer generation
    Output:
      - {"documents": [...], "metadata": {...}}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_rag_search_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "web_search",
    category="rag",
    description="Web search",
    parallelizable=True,
    tags=["rag", "search", "web"],
    config_model=WebSearchConfig,
)
async def run_web_search_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Perform web search using various search engines.

    Config:
      - query: str (templated) - Search query
      - engine: Literal["google", "bing", "duckduckgo", "brave", "searxng", "kagi", "serper", "tavily"] = "google"
      - num_results: int = 10 - Number of results
      - content_country: str = "US"
      - search_lang: str = "en"
      - output_lang: str = "en"
      - safesearch: str = "active"
      - date_range: Optional[str]
      - summarize: bool = False - Summarize results with LLM
      - api_name: Optional[str] - LLM provider for summarization
    Output:
      - {"results": [{title, link, snippet}], "count": int, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_web_search_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "rss_fetch",
    category="rag",
    description="Fetch RSS/Atom feeds",
    parallelizable=True,
    tags=["rag", "feed"],
    config_model=RSSFetchConfig,
)
async def run_rss_fetch_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch RSS/Atom feeds and return items.

    Config:
      - urls: list[str] | str - Feed URLs (newline/comma separated)
      - limit: int = 10 - Maximum items to return
      - include_content: bool = True - Include summary/content in results
    Output:
      - {"results": [{title, link, summary, published}], "count": int, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_rss_fetch_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "atom_fetch",
    category="rag",
    description="Fetch Atom feeds (alias)",
    parallelizable=True,
    tags=["rag", "feed"],
    config_model=RSSFetchConfig,
)
async def run_atom_fetch_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch Atom feeds (alias for rss_fetch).

    Config:
      - urls: list[str] | str - Feed URLs
      - limit: int = 10
      - include_content: bool = True
    Output:
      - {"results": [...], "count": int, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_rss_fetch_adapter as _legacy
    return await _legacy(config, context)
