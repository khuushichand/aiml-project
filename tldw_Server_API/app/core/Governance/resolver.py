"""Deterministic governance action resolver."""

from __future__ import annotations

from .types import CandidateAction, EffectiveAction

# Higher value means more restrictive / higher precedence.
_ACTION_PRECEDENCE: dict[str, int] = {
    "allow": 0,
    "warn": 1,
    "require_approval": 2,
    "deny": 3,
}


def _sort_key(candidate: CandidateAction) -> tuple[int, int, int, float]:
    """
    Sort candidates deterministically.

    Ordering:
    1) action severity (deny > require_approval > warn > allow)
    2) scope level (higher scope level wins)
    3) priority (higher wins)
    4) updated_at (newer wins)
    """
    return (
        int(_ACTION_PRECEDENCE.get(candidate.action, 0)),
        int(candidate.scope_level),
        int(candidate.priority),
        float(candidate.updated_at.timestamp()),
    )


def resolve_effective_action(candidates: list[CandidateAction]) -> EffectiveAction:
    """Resolve one effective action from matched candidates."""
    if not candidates:
        raise ValueError("resolve_effective_action requires at least one candidate")

    ordered = tuple(sorted(candidates, key=_sort_key, reverse=True))
    winner = ordered[0]
    return EffectiveAction(
        action=winner.action,
        winning_candidate=winner,
        ordered_candidates=ordered,
    )

