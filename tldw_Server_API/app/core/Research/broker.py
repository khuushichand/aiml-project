"""Deterministic broker for deep research collecting lanes."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, Protocol

from tldw_Server_API.app.core.testing import is_test_mode

from .models import (
    ResearchCollectionResult,
    ResearchEvidenceNote,
    ResearchPlan,
    ResearchSourceRecord,
)

LaneFn = Callable[..., Awaitable[list[dict[str, Any]]]]


class ResearchLaneProvider(Protocol):
    async def search(
        self,
        *,
        focus_area: str,
        query: str,
        owner_user_id: str,
        config: dict[str, Any],
    ) -> list[dict[str, Any]]: ...


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
        local_provider: ResearchLaneProvider | None = None,
        academic_provider: ResearchLaneProvider | None = None,
        web_provider: ResearchLaneProvider | None = None,
        local_search_fn: LaneFn | None = None,
        academic_search_fn: LaneFn | None = None,
        web_search_fn: LaneFn | None = None,
    ) -> None:
        self._local_provider = local_provider
        self._academic_provider = academic_provider
        self._web_provider = web_provider
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
        provider_config: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ResearchCollectionResult:
        context = dict(context or {})
        resolved_provider_config = provider_config if isinstance(provider_config, dict) else {}
        lanes, lane_errors, lane_attempts = await self._collect_lanes_for_policy(
            source_policy=plan.source_policy,
            focus_area=focus_area,
            query=plan.query,
            owner_user_id=owner_user_id,
            provider_config=resolved_provider_config,
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
        external_count = sum(
            len([item for lane, items in lanes if lane == lane_name for item in items])
            for lane_name in ("academic", "web")
        )
        if plan.source_policy in {"balanced", "local_first"} and external_count == 0:
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
                "lane_attempts": lane_attempts,
                "lane_errors": lane_errors,
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
        provider_config: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[list[tuple[str, list[dict[str, Any]]]], list[dict[str, str]], dict[str, int]]:
        lane_errors: list[dict[str, str]] = []
        lane_attempts = {"local": 0, "academic": 0, "web": 0}

        local_records, local_error = await self._run_lane(
            lane_name="local",
            provider=self._local_provider,
            search_fn=self._local_search_fn,
            focus_area=focus_area,
            query=query,
            owner_user_id=owner_user_id,
            config=provider_config.get("local", {}) if isinstance(provider_config.get("local"), dict) else {},
            context=context,
        )
        lane_attempts["local"] += 1
        if local_error is not None:
            lane_errors.append(local_error)

        if source_policy == "local_only":
            return [("local", local_records)], lane_errors, lane_attempts

        if source_policy == "external_only":
            academic_records, academic_error = await self._run_lane(
                lane_name="academic",
                provider=self._academic_provider,
                search_fn=self._academic_search_fn,
                focus_area=focus_area,
                query=query,
                owner_user_id=owner_user_id,
                config=provider_config.get("academic", {}) if isinstance(provider_config.get("academic"), dict) else {},
                context=context,
            )
            lane_attempts["academic"] += 1
            if academic_error is not None:
                lane_errors.append(academic_error)

            web_records, web_error = await self._run_lane(
                lane_name="web",
                provider=self._web_provider,
                search_fn=self._web_search_fn,
                focus_area=focus_area,
                query=query,
                owner_user_id=owner_user_id,
                config=provider_config.get("web", {}) if isinstance(provider_config.get("web"), dict) else {},
                context=context,
            )
            lane_attempts["web"] += 1
            if web_error is not None:
                lane_errors.append(web_error)
            return [("academic", academic_records), ("web", web_records)], lane_errors, lane_attempts

        if source_policy == "local_first" and len(local_records) >= 2:
            return [("local", local_records)], lane_errors, lane_attempts

        academic_records, academic_error = await self._run_lane(
            lane_name="academic",
            provider=self._academic_provider,
            search_fn=self._academic_search_fn,
            focus_area=focus_area,
            query=query,
            owner_user_id=owner_user_id,
            config=provider_config.get("academic", {}) if isinstance(provider_config.get("academic"), dict) else {},
            context=context,
        )
        lane_attempts["academic"] += 1
        if academic_error is not None:
            lane_errors.append(academic_error)

        web_records, web_error = await self._run_lane(
            lane_name="web",
            provider=self._web_provider,
            search_fn=self._web_search_fn,
            focus_area=focus_area,
            query=query,
            owner_user_id=owner_user_id,
            config=provider_config.get("web", {}) if isinstance(provider_config.get("web"), dict) else {},
            context=context,
        )
        lane_attempts["web"] += 1
        if web_error is not None:
            lane_errors.append(web_error)

        if source_policy == "external_first":
            return [("academic", academic_records), ("web", web_records), ("local", local_records)], lane_errors, lane_attempts
        return [("local", local_records), ("academic", academic_records), ("web", web_records)], lane_errors, lane_attempts

    async def _run_lane(
        self,
        *,
        lane_name: str,
        provider: ResearchLaneProvider | None,
        search_fn: LaneFn,
        focus_area: str,
        query: str,
        owner_user_id: str,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
        try:
            if provider is not None:
                records = await provider.search(
                    focus_area=focus_area,
                    query=query,
                    owner_user_id=owner_user_id,
                    config=dict(config),
                )
            else:
                records = await search_fn(
                    focus_area=focus_area,
                    query=query,
                    owner_user_id=owner_user_id,
                    context=context,
                )
        except Exception as exc:
            message = str(exc).strip() or exc.__class__.__name__
            return [], {"focus_area": focus_area, "lane": lane_name, "message": message}

        normalized_records = [record for record in records if isinstance(record, dict)]
        return normalized_records, None

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
        provider = str(
            raw.get("provider")
            or {
                "local": "local_corpus",
                "academic": "academic_search",
                "web": "web_search",
            }[lane_name]
        ).strip()

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
