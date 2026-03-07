"""Deterministic broker for deep research collecting lanes."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

from tldw_Server_API.app.core.testing import is_test_mode

from .models import (
    ResearchCollectionResult,
    ResearchEvidenceNote,
    ResearchPlan,
    ResearchSourceRecord,
)

LaneFn = Callable[..., Awaitable[list[dict[str, Any]]]]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _stable_digest(*parts: str) -> str:
    joined = "::".join(part.strip().lower() for part in parts if part and part.strip())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _short_digest(*parts: str, length: int = 8) -> str:
    return _stable_digest(*parts)[:length]


class ResearchBroker:
    """Choose collection lanes by source policy and normalize their outputs."""

    def __init__(
        self,
        *,
        local_search_fn: LaneFn | None = None,
        academic_search_fn: LaneFn | None = None,
        web_search_fn: LaneFn | None = None,
    ) -> None:
        self._local_search_fn = local_search_fn or self._default_local_search
        self._academic_search_fn = academic_search_fn or self._default_academic_search
        self._web_search_fn = web_search_fn or self._default_web_search

    async def collect_focus_area(
        self,
        *,
        session_id: str,
        owner_user_id: str,
        focus_area: str,
        plan: ResearchPlan,
        context: dict[str, Any] | None = None,
    ) -> ResearchCollectionResult:
        context = dict(context or {})
        lanes = await self._collect_lanes_for_policy(
            source_policy=plan.source_policy,
            focus_area=focus_area,
            query=plan.query,
            owner_user_id=owner_user_id,
            context=context,
        )

        sources_by_fingerprint: dict[str, ResearchSourceRecord] = {}
        evidence_notes: list[ResearchEvidenceNote] = []
        deduped_sources = 0

        for lane_name, records in lanes:
            for record in records:
                source = self._normalize_source(
                    session_id=session_id,
                    focus_area=focus_area,
                    lane_name=lane_name,
                    raw=record,
                )
                if source.fingerprint in sources_by_fingerprint:
                    deduped_sources += 1
                    continue
                sources_by_fingerprint[source.fingerprint] = source
                evidence_notes.append(
                    self._build_evidence_note(
                        focus_area=focus_area,
                        lane_name=lane_name,
                        source=source,
                    )
                )

        remaining_gaps: list[str] = []
        if not sources_by_fingerprint:
            remaining_gaps.append("no_sources_collected")
        if plan.source_policy in {"balanced", "local_first"} and len(sources_by_fingerprint) < 2:
            remaining_gaps.append("weak_external_coverage")

        lane_counts = {
            "local": len([item for lane, items in lanes if lane == "local" for item in items]),
            "academic": len([item for lane, items in lanes if lane == "academic" for item in items]),
            "web": len([item for lane, items in lanes if lane == "web" for item in items]),
        }

        return ResearchCollectionResult(
            sources=list(sources_by_fingerprint.values()),
            evidence_notes=evidence_notes,
            collection_metrics={
                "lane_counts": lane_counts,
                "deduped_sources": deduped_sources,
                "source_policy": plan.source_policy,
            },
            remaining_gaps=remaining_gaps,
        )

    async def _collect_lanes_for_policy(
        self,
        *,
        source_policy: str,
        focus_area: str,
        query: str,
        owner_user_id: str,
        context: dict[str, Any],
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        local_records = await self._local_search_fn(
            focus_area=focus_area,
            query=query,
            owner_user_id=owner_user_id,
            context=context,
        )

        if source_policy == "local_only":
            return [("local", local_records)]

        if source_policy == "external_only":
            academic_records = await self._academic_search_fn(
                focus_area=focus_area,
                query=query,
                owner_user_id=owner_user_id,
                context=context,
            )
            web_records = await self._web_search_fn(
                focus_area=focus_area,
                query=query,
                owner_user_id=owner_user_id,
                context=context,
            )
            return [("academic", academic_records), ("web", web_records)]

        if source_policy == "local_first" and len(local_records) >= 2:
            return [("local", local_records)]

        academic_records = await self._academic_search_fn(
            focus_area=focus_area,
            query=query,
            owner_user_id=owner_user_id,
            context=context,
        )
        web_records = await self._web_search_fn(
            focus_area=focus_area,
            query=query,
            owner_user_id=owner_user_id,
            context=context,
        )

        if source_policy == "external_first":
            return [("academic", academic_records), ("web", web_records), ("local", local_records)]
        return [("local", local_records), ("academic", academic_records), ("web", web_records)]

    def _normalize_source(
        self,
        *,
        session_id: str,
        focus_area: str,
        lane_name: str,
        raw: dict[str, Any],
    ) -> ResearchSourceRecord:
        source_type = {
            "local": "local_document",
            "academic": "academic_paper",
            "web": "web_page",
        }[lane_name]
        provider = {
            "local": "local_corpus",
            "academic": "academic_search",
            "web": "web_search",
        }[lane_name]

        title = str(raw.get("title") or raw.get("name") or focus_area).strip()
        url = raw.get("url")
        url_text = str(url).strip() if url else None
        snippet = str(
            raw.get("snippet")
            or raw.get("summary")
            or raw.get("content")
            or ""
        ).strip()
        published_at = raw.get("published_at") or raw.get("published") or raw.get("updated")
        fingerprint = _stable_digest(
            str(raw.get("doi") or ""),
            url_text or "",
            str(raw.get("id") or ""),
            title,
        )
        source_id = f"src_{fingerprint[:12]}"
        return ResearchSourceRecord(
            source_id=source_id,
            focus_area=focus_area,
            source_type=source_type,
            provider=provider,
            title=title,
            url=url_text,
            snippet=snippet,
            published_at=str(published_at) if published_at else None,
            retrieved_at=_utc_now(),
            fingerprint=fingerprint,
            trust_tier="internal" if lane_name == "local" else "external",
            metadata={k: v for k, v in raw.items() if k not in {"title", "name", "summary", "snippet", "content", "url"}},
        )

    def _build_evidence_note(
        self,
        *,
        focus_area: str,
        lane_name: str,
        source: ResearchSourceRecord,
    ) -> ResearchEvidenceNote:
        note_digest = _stable_digest(source.source_id, focus_area, source.snippet or source.title)
        return ResearchEvidenceNote(
            note_id=f"note_{note_digest[:12]}",
            source_id=source.source_id,
            focus_area=focus_area,
            kind="summary",
            text=source.snippet or source.title,
            citation_locator=source.url,
            confidence=0.7 if lane_name == "local" else 0.6,
            metadata={"provider": source.provider},
        )

    async def _default_local_search(
        self,
        *,
        focus_area: str,
        query: str,
        owner_user_id: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if isinstance(context.get("local_results"), list):
            return [item for item in context["local_results"] if isinstance(item, dict)]
        if is_test_mode():
            return [
                {
                    "id": f"local-{owner_user_id}-{focus_area}",
                    "title": f"Local evidence for {focus_area}",
                    "content": f"Simulated local corpus note about {query}",
                }
            ]
        return []

    async def _default_academic_search(
        self,
        *,
        focus_area: str,
        query: str,
        owner_user_id: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        _ = owner_user_id
        if isinstance(context.get("academic_results"), list):
            return [item for item in context["academic_results"] if isinstance(item, dict)]
        if is_test_mode():
            return [
                {
                    "doi": f"10.1000/{_short_digest(focus_area)}",
                    "title": f"Academic findings on {focus_area}",
                    "summary": f"Simulated academic evidence about {query}",
                }
            ]
        return []

    async def _default_web_search(
        self,
        *,
        focus_area: str,
        query: str,
        owner_user_id: str,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        _ = owner_user_id
        if isinstance(context.get("web_results"), list):
            return [item for item in context["web_results"] if isinstance(item, dict)]
        if is_test_mode():
            slug = _short_digest(focus_area)
            return [
                {
                    "url": f"https://example.com/research/{slug}",
                    "title": f"Web coverage for {focus_area}",
                    "snippet": f"Simulated web evidence about {query}",
                }
            ]
        return []

__all__ = ["ResearchBroker"]
