from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Dict


HandlerFunc = Callable[[str, str], Dict[str, Any]]


def handle_generic_html(html: str, url: str) -> Dict[str, Any]:
    """Default handler: extract article metadata and convert content to Markdown."""
    # Lazy import to avoid circular dependency with Article_Extractor_Lib.
    from tldw_Server_API.app.core.Web_Scraping.Article_Extractor_Lib import (
        extract_article_data_from_html,
        convert_html_to_markdown,
    )

    data = extract_article_data_from_html(html, url)
    if data.get("extraction_successful") and data.get("content"):
        data["content"] = convert_html_to_markdown(data["content"])
    return data


def resolve_handler(handler_path: str) -> HandlerFunc:
    """Resolve a handler import string to a callable, falling back to the default."""
    if not handler_path or ":" not in handler_path:
        return handle_generic_html
    module_path, func_name = handler_path.split(":", 1)
    if not module_path or not func_name:
        return handle_generic_html
    try:
        module = import_module(module_path)
        func = getattr(module, func_name, None)
        if callable(func):
            return func
    except Exception:
        pass
    return handle_generic_html


__all__ = [
    "handle_generic_html",
    "resolve_handler",
    "HandlerFunc",
]
