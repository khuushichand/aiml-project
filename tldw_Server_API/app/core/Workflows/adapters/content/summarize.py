"""Summarization adapter.

This module includes the summarization adapter.
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.content._config import SummarizeConfig


@registry.register(
    "summarize",
    category="content",
    description="Summarize text content",
    parallelizable=True,
    tags=["content", "summarization"],
    config_model=SummarizeConfig,
)
async def run_summarize_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize text content using an LLM.

    Config:
      - text: str (templated) - Text to summarize
      - provider: str - LLM provider
      - model: str - Model to use
      - max_length: int (optional) - Maximum summary length
      - style: Literal["brief", "detailed", "bullet"] = "brief"
      - language: str (optional) - Output language
    Output:
      - {"summary": str, "word_count": int, "style": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_summarize_adapter as _legacy
    return await _legacy(config, context)
