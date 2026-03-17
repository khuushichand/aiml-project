"""Candidate pool filtering and ranking helpers for model routing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional


@dataclass(frozen=True)
class RoutingCandidate:
    provider: str
    model: str
    quality_rank: int | None = None
    latency_rank: int | None = None
    cost_rank: int | None = None
    context_window: int | None = None
    tool_support: bool = False
    vision_support: bool = False
    json_mode_support: bool = False
    reasoning_support: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def _normalize_provider(provider: Any) -> str:
    return str(provider or "").strip().lower()


def _normalize_model(model: Any) -> str:
    return str(model or "").strip()


def _to_optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _candidate_from_mapping(record: Mapping[str, Any]) -> RoutingCandidate:
    capabilities = record.get("capabilities")
    if not isinstance(capabilities, Mapping):
        capabilities = {}

    metadata = dict(record)
    return RoutingCandidate(
        provider=_normalize_provider(record.get("provider") or record.get("name")),
        model=_normalize_model(record.get("model") or record.get("id") or record.get("name")),
        quality_rank=_to_optional_int(record.get("quality_rank")),
        latency_rank=_to_optional_int(record.get("latency_rank")),
        cost_rank=_to_optional_int(record.get("cost_rank")),
        context_window=_to_optional_int(record.get("context_window")),
        tool_support=_to_bool(
            record.get("tool_support")
            if record.get("tool_support") is not None
            else capabilities.get("tool_use") or capabilities.get("function_calling")
        ),
        vision_support=_to_bool(
            record.get("vision_support")
            if record.get("vision_support") is not None
            else capabilities.get("vision")
        ),
        json_mode_support=_to_bool(
            record.get("json_mode_support")
            if record.get("json_mode_support") is not None
            else capabilities.get("json_mode")
        ),
        reasoning_support=_to_bool(
            record.get("reasoning_support")
            if record.get("reasoning_support") is not None
            else capabilities.get("thinking")
        ),
        metadata=metadata,
    )


def normalize_candidate(record: RoutingCandidate | Mapping[str, Any]) -> RoutingCandidate:
    if isinstance(record, RoutingCandidate):
        return record
    return _candidate_from_mapping(record)


_as_candidate = normalize_candidate


def _matches_capabilities(
    candidate: RoutingCandidate,
    requested_capabilities: Optional[Mapping[str, Any]],
) -> bool:
    if not requested_capabilities:
        return True

    if requested_capabilities.get("tools") and not candidate.tool_support:
        return False
    if requested_capabilities.get("vision") and not candidate.vision_support:
        return False
    if requested_capabilities.get("json_mode") and not candidate.json_mode_support:
        return False
    if requested_capabilities.get("reasoning") and not candidate.reasoning_support:
        return False

    required_context = _to_optional_int(requested_capabilities.get("context_window"))
    if required_context is not None:
        if candidate.context_window is None:
            return False
        if candidate.context_window < required_context:
            return False

    return True


def build_candidate_pool(
    *,
    boundary_mode: str,
    pinned_provider: str | None = None,
    server_default_provider: str | None = None,
    requested_capabilities: Optional[Mapping[str, Any]] = None,
    catalog: Iterable[RoutingCandidate | Mapping[str, Any]],
) -> list[RoutingCandidate]:
    """Normalize and filter the candidate catalog for routing."""

    boundary_mode = str(boundary_mode or "").strip().lower()
    pinned_provider_norm = _normalize_provider(pinned_provider)
    default_provider_norm = _normalize_provider(server_default_provider)

    candidates: list[RoutingCandidate] = []
    for record in catalog:
        candidate = normalize_candidate(record)
        if not candidate.provider or not candidate.model:
            continue

        if boundary_mode == "pinned_provider" and pinned_provider_norm and candidate.provider != pinned_provider_norm:
            continue
        if (
            boundary_mode == "server_default_provider"
            and default_provider_norm
            and candidate.provider != default_provider_norm
        ):
            continue
        if not _matches_capabilities(candidate, requested_capabilities):
            continue

        candidates.append(candidate)

    return candidates


def choose_ranked_candidate(
    candidates: Iterable[RoutingCandidate | Mapping[str, Any]],
    *,
    provider_order: Optional[Mapping[str, list[str]]] = None,
    objective: str = "highest_quality",
) -> RoutingCandidate | None:
    """Return the best candidate using explicit rank fields, then admin order."""

    normalized = [normalize_candidate(candidate) for candidate in candidates]
    if not normalized:
        return None

    rank_attr = {
        "highest_quality": "quality_rank",
        "lowest_cost": "cost_rank",
        "lowest_latency": "latency_rank",
    }.get(objective, "quality_rank")

    provider_order = provider_order or {}

    def _admin_index(candidate: RoutingCandidate) -> int:
        provider_models = provider_order.get(candidate.provider) or []
        try:
            return provider_models.index(candidate.model)
        except ValueError:
            return len(provider_models) if provider_models else 10_000

    def _rank_or_max(value: int | None) -> int:
        return value if value is not None else 10_000

    def _sort_key(candidate: RoutingCandidate) -> tuple[int, ...]:
        if objective == "balanced":
            quality_rank = _rank_or_max(candidate.quality_rank)
            latency_rank = _rank_or_max(candidate.latency_rank)
            cost_rank = _rank_or_max(candidate.cost_rank)
            return (
                quality_rank + latency_rank + cost_rank,
                quality_rank,
                latency_rank,
                cost_rank,
                _admin_index(candidate),
                0,
                candidate.provider,
                candidate.model,
            )

        rank_value = getattr(candidate, rank_attr)
        primary_rank = _rank_or_max(rank_value)
        return (
            primary_rank,
            _admin_index(candidate),
            0,
            candidate.provider,
            candidate.model,
        )

    return min(normalized, key=_sort_key)
