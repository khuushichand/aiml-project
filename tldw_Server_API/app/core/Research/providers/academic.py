"""Academic search provider for deep research collection."""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Callable

from tldw_Server_API.app.core.Third_Party.Arxiv import search_arxiv_custom_api
from tldw_Server_API.app.core.Third_Party.Crossref import search_crossref
from tldw_Server_API.app.core.Third_Party.PubMed import search_pubmed
from tldw_Server_API.app.core.testing import is_test_mode

ArxivFn = Callable[[str | None, str | None, str | None, int, int], tuple[list[dict[str, Any]] | None, int, str | None]]
PubmedFn = Callable[..., tuple[list[dict[str, Any]] | None, int, str | None]]
CrossrefFn = Callable[..., tuple[list[dict[str, Any]] | None, int, str | None]]


def _build_query(query: str, focus_area: str) -> str:
    return " ".join(part.strip() for part in (query, focus_area) if part and part.strip())


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()
    return f"acad_{digest[:12]}"


class AcademicResearchProvider:
    """Collect academic references from a small provider set."""

    def __init__(
        self,
        *,
        arxiv_search_fn: ArxivFn = search_arxiv_custom_api,
        pubmed_search_fn: PubmedFn = search_pubmed,
        crossref_search_fn: CrossrefFn = search_crossref,
    ) -> None:
        self._arxiv_search_fn = arxiv_search_fn
        self._pubmed_search_fn = pubmed_search_fn
        self._crossref_search_fn = crossref_search_fn

    async def search(
        self,
        *,
        focus_area: str,
        query: str,
        owner_user_id: str,
        config: dict[str, Any],
    ) -> list[dict[str, Any]]:
        _ = owner_user_id
        providers = [str(item).strip().lower() for item in config.get("providers", []) if str(item).strip()]
        max_results = int(config.get("max_results", 5))
        combined_query = _build_query(query, focus_area)

        if is_test_mode():
            simulated: list[dict[str, Any]] = []
            for provider in providers or ["arxiv", "pubmed"]:
                simulated.append(
                    {
                        "id": _stable_id(provider, combined_query),
                        "title": f"{provider.title()} findings on {focus_area}",
                        "url": f"https://example.com/{provider}/{focus_area.replace(' ', '-')}",
                        "snippet": f"Simulated academic evidence about {query}",
                        "provider": provider,
                        "metadata": {"provider": provider},
                    }
                )
            return simulated

        records: list[dict[str, Any]] = []
        errors: list[str] = []

        if "arxiv" in providers:
            items, _, error = await asyncio.to_thread(self._arxiv_search_fn, combined_query, None, None, 0, max_results)
            if error:
                errors.append(error)
            elif items:
                records.extend(self._normalize_arxiv_item(item) for item in items)

        if "pubmed" in providers:
            items, _, error = await asyncio.to_thread(self._pubmed_search_fn, combined_query, 0, max_results)
            if error:
                errors.append(error)
            elif items:
                records.extend(self._normalize_pubmed_item(item) for item in items)

        if "crossref" in providers:
            items, _, error = await asyncio.to_thread(self._crossref_search_fn, combined_query, 0, max_results, None, None, None)
            if error:
                errors.append(error)
            elif items:
                records.extend(self._normalize_crossref_item(item) for item in items)

        if records:
            return records
        if errors:
            raise ValueError("; ".join(errors))
        return []

    @staticmethod
    def _normalize_arxiv_item(item: dict[str, Any]) -> dict[str, Any]:
        arxiv_id = str(item.get("id") or "").strip()
        return {
            "id": arxiv_id or _stable_id("arxiv", str(item.get("title") or "")),
            "title": str(item.get("title") or "").strip(),
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else item.get("pdf_url"),
            "snippet": str(item.get("abstract") or "").strip(),
            "provider": "arxiv",
            "doi": item.get("doi"),
            "published_at": item.get("published_date"),
            "metadata": dict(item),
        }

    @staticmethod
    def _normalize_pubmed_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(item.get("pmid") or _stable_id("pubmed", str(item.get("title") or ""))),
            "title": str(item.get("title") or "").strip(),
            "url": item.get("url"),
            "snippet": str(item.get("abstract") or item.get("journal") or item.get("title") or "").strip(),
            "provider": "pubmed",
            "doi": item.get("doi"),
            "published_at": item.get("pub_date"),
            "metadata": dict(item),
        }

    @staticmethod
    def _normalize_crossref_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(item.get("id") or item.get("doi") or _stable_id("crossref", str(item.get("title") or ""))),
            "title": str(item.get("title") or "").strip(),
            "url": item.get("url"),
            "snippet": str(item.get("abstract") or item.get("journal") or item.get("title") or "").strip(),
            "provider": "crossref",
            "doi": item.get("doi"),
            "published_at": item.get("pub_date"),
            "metadata": dict(item),
        }


__all__ = ["AcademicResearchProvider"]
