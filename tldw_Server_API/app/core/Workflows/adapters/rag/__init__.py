"""RAG and search adapters.

This module includes adapters for RAG operations:
- rag_search: Execute RAG search
- web_search: Web search
- rss_fetch: Fetch RSS/Atom feeds
- atom_fetch: Fetch Atom feeds (alias)
- query_rewrite: Rewrite search queries
- query_expand: Expand search queries
- hyde_generate: Generate hypothetical documents (HyDE)
- semantic_cache_check: Check semantic cache
- search_aggregate: Aggregate search results
"""

from tldw_Server_API.app.core.Workflows.adapters.rag.search import (
    run_rag_search_adapter,
    run_web_search_adapter,
    run_rss_fetch_adapter,
    run_atom_fetch_adapter,
)

from tldw_Server_API.app.core.Workflows.adapters.rag.query import (
    run_query_rewrite_adapter,
    run_query_expand_adapter,
    run_hyde_generate_adapter,
    run_semantic_cache_check_adapter,
    run_search_aggregate_adapter,
)

__all__ = [
    "run_rag_search_adapter",
    "run_web_search_adapter",
    "run_rss_fetch_adapter",
    "run_atom_fetch_adapter",
    "run_query_rewrite_adapter",
    "run_query_expand_adapter",
    "run_hyde_generate_adapter",
    "run_semantic_cache_check_adapter",
    "run_search_aggregate_adapter",
]
