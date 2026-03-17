"""Sticky routing decision storage and reuse helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Mapping, Optional

from .models import RoutingDecision


@dataclass(frozen=True)
class StoredRoutingDecision:
    scope: str
    fingerprint: str
    provider: str
    model: str
    policy_fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryRoutingDecisionStore:
    """Simple in-memory sticky decision store for early routing integration."""

    def __init__(self) -> None:
        self._decisions: dict[str, StoredRoutingDecision] = {}

    def save(
        self,
        *,
        scope: str,
        fingerprint: str,
        provider: str,
        model: str,
        policy_fingerprint: str | None = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> StoredRoutingDecision:
        decision = StoredRoutingDecision(
            scope=scope,
            fingerprint=fingerprint,
            provider=provider,
            model=model,
            policy_fingerprint=policy_fingerprint,
            metadata=dict(metadata or {}),
        )
        self._decisions[scope] = decision
        return decision

    def load(self, scope: str) -> StoredRoutingDecision | None:
        return self._decisions.get(scope)

    def delete(self, scope: str) -> None:
        self._decisions.pop(scope, None)


@lru_cache(maxsize=1)
def get_process_routing_decision_store() -> InMemoryRoutingDecisionStore:
    """Return the process-local sticky routing store shared by endpoint integrations."""

    return InMemoryRoutingDecisionStore()


def compute_routing_fingerprint(
    *,
    surface: str,
    objective: str,
    boundary_mode: str,
    pinned_provider: str | None = None,
    hard_capabilities: Optional[Mapping[str, Any]] = None,
    modality_flags: Optional[Mapping[str, Any]] = None,
    sticky_scope: str | None = None,
) -> str:
    """Build a deterministic reuse fingerprint for sticky routing."""

    capability_items = ",".join(
        f"{key}={hard_capabilities[key]}"
        for key in sorted(hard_capabilities or {})
    )
    modality_items = ",".join(
        f"{key}={modality_flags[key]}"
        for key in sorted(modality_flags or {})
    )
    parts = [
        f"surface={surface}",
        f"objective={objective}",
        f"boundary_mode={boundary_mode}",
        f"pinned_provider={pinned_provider or ''}",
        f"hard_capabilities={capability_items}",
        f"modality_flags={modality_items}",
        f"sticky_scope={sticky_scope or ''}",
    ]
    return "|".join(parts)


def maybe_reuse_sticky_decision(
    *,
    store: InMemoryRoutingDecisionStore,
    scope: str,
    fingerprint: str,
) -> RoutingDecision | None:
    """Reuse a sticky decision only when the deterministic fingerprint still matches."""

    stored = store.load(scope)
    if stored is None or stored.fingerprint != fingerprint:
        return None

    return RoutingDecision(
        provider=stored.provider,
        model=stored.model,
        canonical=True,
        decision_source="sticky_reuse",
        metadata={"scope": scope},
    )
