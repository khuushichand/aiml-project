"""Web search provider for deep research collection."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Callable

from tldw_Server_API.app.core.testing import is_test_mode
from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import perform_websearch

SearchFn = Callable[..., dict[str, Any]]


def _build_query(query: str, focus_area: str) -> str:
    return " ".join(part.strip() for part in (query, focus_area) if part and part.strip())


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return f"web_{digest[:12]}"


def _truncate_text(text: str, *, max_len: int = 400) -> str:
    value = str(text or "").strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


class WebResearchProvider:
    """Perform one bounded web query for a focus area."""

    def __init__(self, *, search_fn: SearchFn = perform_websearch) -> None:
        self._search_fn = search_fn

    async def search(
        self,
        *,
        focus_area: str,
        query: str,
        owner_user_id: str,
        config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        _ = owner_user_id
        engine = str(config.get("engine") or "duckduckgo").strip().lower()
        result_count = int(config.get("result_count", 5))
        combined_query = _build_query(query, focus_area)

        if is_test_mode():
            return [
                {
                    "id": _stable_id(engine, combined_query),
                    "title": f"Web coverage for {focus_area}",
                    "url": f"https://example.com/research/{engine}",
                    "snippet": f"Simulated web evidence about {query}",
                    "provider": engine,
                    "metadata": {"engine": engine},
                }
            ]

        payload = await asyncio.to_thread(
            self._search_fn,
            search_engine=engine,
            search_query=combined_query,
            content_country=str(config.get("content_country") or "US"),
            search_lang=str(config.get("search_lang") or "en"),
            output_lang=str(config.get("output_lang") or "en"),
            result_count=result_count,
            date_range=config.get("date_range"),
            safesearch=config.get("safesearch"),
            site_blacklist=config.get("site_blacklist"),
            exactTerms=config.get("exactTerms"),
            excludeTerms=config.get("excludeTerms"),
            filter=config.get("filter"),
            geolocation=config.get("geolocation"),
            search_result_language=config.get("search_result_language"),
            sort_results_by=config.get("sort_results_by"),
        )
        raw_results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(raw_results, list):
            raise ValueError("web search returned invalid results payload")
        return [
            self._normalize_result(item, engine=engine, fallback_query=combined_query, position=index)
            for index, item in enumerate(raw_results)
            if isinstance(item, dict)
        ]

    @staticmethod
    def _normalize_result(
        item: dict[str, Any],
        *,
        engine: str,
        fallback_query: str,
        position: int,
    ) -> dict[str, Any]:
        title = str(item.get("title") or item.get("name") or fallback_query).strip()
        url = item.get("url") or item.get("link")
        snippet = str(
            item.get("snippet")
            or item.get("description")
            or item.get("body")
            or item.get("content")
            or ""
        ).strip()
        return {
            "id": str(item.get("id") or _stable_id(engine, title, str(url or ""), str(position))),
            "title": title,
            "url": str(url).strip() if url else None,
            "snippet": _truncate_text(snippet),
            "provider": engine,
            "metadata": {k: v for k, v in item.items() if k not in {"id", "title", "name", "url", "link", "snippet", "description", "body", "content"}},
        }


__all__ = ["WebResearchProvider"]
