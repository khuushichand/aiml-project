"""Reranking adapter.

This module includes the reranking adapter.
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.content._config import RerankConfig


@registry.register(
    "rerank",
    category="content",
    description="Rerank search results",
    parallelizable=False,
    tags=["content", "ranking"],
    config_model=RerankConfig,
)
async def run_rerank_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Rerank search results using cross-encoder or LLM reranking.

    Config:
      - query: str (templated) - Query for relevance scoring
      - documents: list[dict] - Documents to rerank
      - provider: str = "cohere" - Reranking provider
      - model: str (optional) - Model to use
      - top_k: int = 10 - Number of results to return
    Output:
      - {"documents": [dict], "count": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_rerank_adapter as _legacy
    return await _legacy(config, context)
