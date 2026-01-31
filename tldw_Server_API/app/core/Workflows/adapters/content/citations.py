"""Citation and bibliography adapters.

This module includes adapters for citation operations:
- citations: Generate citations
- bibliography_generate: Generate bibliography
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.content._config import (
    CitationsConfig,
    BibliographyGenerateConfig,
)


@registry.register(
    "citations",
    category="content",
    description="Generate citations",
    parallelizable=True,
    tags=["content", "citations"],
    config_model=CitationsConfig,
)
async def run_citations_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate citations from references.

    Config:
      - references: list[dict] - List of reference data
      - style: Literal["apa", "mla", "chicago", "ieee", "harvard"] = "apa"
      - format: Literal["text", "html", "markdown"] = "text"
    Output:
      - {"citations": [str], "count": int, "style": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_citations_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "bibliography_generate",
    category="content",
    description="Generate bibliography",
    parallelizable=True,
    tags=["content", "citations"],
    config_model=BibliographyGenerateConfig,
)
async def run_bibliography_generate_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a formatted bibliography from sources.

    Config:
      - sources: list[dict] - List of source data
      - style: Literal["apa", "mla", "chicago", "ieee", "harvard"] = "apa"
      - sort_by: Literal["author", "year", "title"] = "author"
      - format: Literal["text", "html", "markdown"] = "text"
    Output:
      - {"bibliography": str, "entries": int, "style": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_bibliography_generate_adapter as _legacy
    return await _legacy(config, context)
