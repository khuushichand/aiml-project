"""
Conflict resolution helpers for shared-dependent guardian policies.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

ACTION_ORDER = {"notify": 1, "warn": 2, "redact": 3, "block": 4}
SEVERITY_ORDER = {"info": 1, "warning": 2, "critical": 3}


def _value(policy: Any, key: str) -> Any:
    if isinstance(policy, Mapping):
        return policy.get(key)
    return getattr(policy, key, None)


def resolve_conflicts(policies: Sequence[Any]) -> Any | None:
    """Return a deterministic winner using strictest-wins policy ordering."""
    if not policies:
        return None

    def score(policy: Any) -> tuple[int, int, str]:
        action = ACTION_ORDER.get(str(_value(policy, "action")), 0)
        severity = SEVERITY_ORDER.get(str(_value(policy, "severity")), 0)
        policy_id = str(_value(policy, "id") or "")
        return (action, severity, policy_id)

    return max(policies, key=score)
