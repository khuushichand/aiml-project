"""Sticky routing decision storage and reuse helpers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    """Simple bounded in-memory sticky decision store."""

    def __init__(
        self,
        *,
        max_entries: int = 1024,
        ttl_seconds: int = 3600,
    ) -> None:
        self._max_entries = max(1, int(max_entries))
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._decisions: OrderedDict[str, StoredRoutingDecision] = OrderedDict()

    def _is_expired(
        self,
        decision: StoredRoutingDecision,
        *,
        now: datetime | None = None,
    ) -> bool:
        reference_time = now or datetime.now(timezone.utc)
        age_seconds = (reference_time - decision.updated_at).total_seconds()
        return age_seconds > self._ttl_seconds

    def _prune_expired(self, *, now: datetime | None = None) -> None:
        reference_time = now or datetime.now(timezone.utc)
        expired_scopes = [
            scope
            for scope, decision in self._decisions.items()
            if self._is_expired(decision, now=reference_time)
        ]
        for scope in expired_scopes:
            self._decisions.pop(scope, None)

    def _evict_if_needed(self) -> None:
        while len(self._decisions) > self._max_entries:
            self._decisions.popitem(last=False)

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
        now = datetime.now(timezone.utc)
        self._prune_expired(now=now)
        decision = StoredRoutingDecision(
            scope=scope,
            fingerprint=fingerprint,
            provider=provider,
            model=model,
            policy_fingerprint=policy_fingerprint,
            metadata=dict(metadata or {}),
            updated_at=now,
        )
        self._decisions.pop(scope, None)
        self._decisions[scope] = decision
        self._evict_if_needed()
        return decision

    def load(self, scope: str) -> StoredRoutingDecision | None:
        now = datetime.now(timezone.utc)
        self._prune_expired(now=now)
        decision = self._decisions.get(scope)
        if decision is None:
            return None
        self._decisions.move_to_end(scope)
        return decision

    def delete(self, scope: str) -> None:
        self._decisions.pop(scope, None)


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
