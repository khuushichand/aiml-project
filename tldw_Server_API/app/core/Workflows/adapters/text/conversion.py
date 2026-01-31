"""Text conversion adapters.

This module includes adapters for format conversion operations:
- html_to_markdown: Convert HTML to Markdown
- markdown_to_html: Convert Markdown to HTML
- csv_to_json: Convert CSV to JSON
- json_to_csv: Convert JSON to CSV
"""

from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.Workflows.adapters._registry import registry
from tldw_Server_API.app.core.Workflows.adapters.text._config import (
    CSVToJSONConfig,
    HTMLToMarkdownConfig,
    JSONToCSVConfig,
    MarkdownToHTMLConfig,
)


@registry.register(
    "html_to_markdown",
    category="text",
    description="Convert HTML to Markdown",
    parallelizable=True,
    tags=["text", "conversion"],
    config_model=HTMLToMarkdownConfig,
)
async def run_html_to_markdown_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert HTML content to Markdown format.

    Config:
      - html: str (templated) - HTML content to convert
      - strip_tags: list[str] (optional) - Tags to remove
      - preserve_links: bool = True - Keep hyperlinks
    Output:
      - {"markdown": str, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_html_to_markdown_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "markdown_to_html",
    category="text",
    description="Convert Markdown to HTML",
    parallelizable=True,
    tags=["text", "conversion"],
    config_model=MarkdownToHTMLConfig,
)
async def run_markdown_to_html_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Markdown content to HTML format.

    Config:
      - markdown: str (templated) - Markdown content to convert
      - extensions: list[str] (optional) - Markdown extensions to use
      - safe_mode: bool = True - Sanitize output
    Output:
      - {"html": str, "text": str}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_markdown_to_html_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "csv_to_json",
    category="text",
    description="Convert CSV to JSON",
    parallelizable=True,
    tags=["text", "conversion"],
    config_model=CSVToJSONConfig,
)
async def run_csv_to_json_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert CSV data to JSON format.

    Config:
      - csv: str (templated) - CSV content to convert
      - delimiter: str = "," - CSV delimiter
      - has_header: bool = True - First row is header
    Output:
      - {"json": list[dict], "rows": int, "columns": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_csv_to_json_adapter as _legacy
    return await _legacy(config, context)


@registry.register(
    "json_to_csv",
    category="text",
    description="Convert JSON to CSV",
    parallelizable=True,
    tags=["text", "conversion"],
    config_model=JSONToCSVConfig,
)
async def run_json_to_csv_adapter(config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Convert JSON data to CSV format.

    Config:
      - json: list[dict] (templated) - JSON data to convert
      - delimiter: str = "," - CSV delimiter
      - include_header: bool = True - Include header row
    Output:
      - {"csv": str, "rows": int, "columns": int}
    """
    from tldw_Server_API.app.core.Workflows._adapters_legacy import run_json_to_csv_adapter as _legacy
    return await _legacy(config, context)
