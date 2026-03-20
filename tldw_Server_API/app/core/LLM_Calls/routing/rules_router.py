"""Deterministic fallback routing for auto-model selection."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Optional

from .candidate_pool import RoutingCandidate, choose_ranked_candidate
from .models import RoutingDecision


def route_with_rules(
    *,
    objective: str,
    candidates: Iterable[RoutingCandidate | Mapping[str, object]],
    provider_order: Optional[Mapping[str, list[str]]] = None,
) -> RoutingDecision | None:
    """Choose the best candidate using deterministic ranking and admin order."""

    chosen = choose_ranked_candidate(
        candidates,
        provider_order=provider_order,
        objective=objective,
    )
    if chosen is None:
        return None

    return RoutingDecision(
        provider=chosen.provider,
        model=chosen.model,
        canonical=True,
        decision_source="rules_router",
        metadata={"objective": objective},
    )
