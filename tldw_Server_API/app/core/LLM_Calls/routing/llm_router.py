"""Helpers for LLM-driven model routing."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .candidate_pool import RoutingCandidate, _as_candidate
from .models import RouterRequest, RoutingPolicy


def build_router_prompt(
    *,
    request: RouterRequest,
    policy: RoutingPolicy,
    candidates: Iterable[RoutingCandidate | Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a minimal, structured router prompt payload."""

    normalized_candidates = [_as_candidate(candidate) for candidate in candidates]
    return {
        "surface": request.surface,
        "latest_user_turn": request.latest_user_turn,
        "objective": policy.objective,
        "mode": policy.mode,
        "candidate_count": len(normalized_candidates),
        "candidates": [
            {
                "provider": candidate.provider,
                "model": candidate.model,
                "tool_support": candidate.tool_support,
                "vision_support": candidate.vision_support,
                "json_mode_support": candidate.json_mode_support,
                "reasoning_support": candidate.reasoning_support,
                "context_window": candidate.context_window,
            }
            for candidate in normalized_candidates
        ],
    }


def validate_llm_router_choice(
    *,
    raw_choice: Mapping[str, Any] | None,
    candidates: Iterable[RoutingCandidate | Mapping[str, Any]],
) -> RoutingCandidate | None:
    """Accept router output only when it resolves to an existing candidate."""

    if not isinstance(raw_choice, Mapping):
        return None

    provider = str(raw_choice.get("provider") or "").strip().lower()
    model = str(raw_choice.get("model") or "").strip()
    if not provider or not model:
        return None

    for candidate in candidates:
        normalized = _as_candidate(candidate)
        if normalized.provider == provider and normalized.model == model:
            return normalized
    return None
