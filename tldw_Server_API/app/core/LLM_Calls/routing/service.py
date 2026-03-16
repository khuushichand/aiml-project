"""Shared model router service orchestration."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping, Optional

from .candidate_pool import RoutingCandidate, _as_candidate
from .decision_store import (
    InMemoryRoutingDecisionStore,
    compute_routing_fingerprint,
    maybe_reuse_sticky_decision,
)
from .llm_router import build_router_prompt, validate_llm_router_choice
from .models import RouterRequest, RoutingDecision, RoutingPolicy
from .rules_router import route_with_rules


RouterRunner = Callable[[dict[str, Any]], Mapping[str, Any] | None]


def route_model(
    *,
    request: RouterRequest,
    policy: RoutingPolicy,
    candidates: Iterable[RoutingCandidate | Mapping[str, Any]],
    sticky_store: InMemoryRoutingDecisionStore | None = None,
    router_runner: RouterRunner | None = None,
    llm_router_choice: Mapping[str, Any] | None = None,
    provider_order: Optional[Mapping[str, list[str]]] = None,
) -> RoutingDecision | None:
    """Resolve `model="auto"` to a canonical provider/model pair."""

    normalized_candidates = [_as_candidate(candidate) for candidate in candidates]
    if not normalized_candidates:
        return None

    sticky_fingerprint: str | None = None
    if sticky_store is not None and policy.mode == "sticky_session" and request.scope:
        sticky_fingerprint = compute_routing_fingerprint(
            surface=request.surface,
            objective=policy.objective,
            boundary_mode=policy.boundary_mode,
            pinned_provider=policy.pinned_provider,
            hard_capabilities=request.requested_capabilities,
            modality_flags=request.routing_context,
            sticky_scope=request.scope,
        )
        reused = maybe_reuse_sticky_decision(
            store=sticky_store,
            scope=request.scope,
            fingerprint=sticky_fingerprint,
        )
        if reused is not None:
            return reused

    if len(normalized_candidates) == 1:
        selected = normalized_candidates[0]
        decision = RoutingDecision(
            provider=selected.provider,
            model=selected.model,
            canonical=True,
            decision_source="single_candidate",
            metadata={"objective": policy.objective},
        )
    else:
        router_choice = llm_router_choice
        if router_choice is None and router_runner is not None:
            router_choice = router_runner(
                build_router_prompt(
                    request=request,
                    policy=policy,
                    candidates=normalized_candidates,
                )
            )

        validated_choice = validate_llm_router_choice(
            raw_choice=router_choice,
            candidates=normalized_candidates,
        )

        if validated_choice is not None:
            decision = RoutingDecision(
                provider=validated_choice.provider,
                model=validated_choice.model,
                canonical=True,
                decision_source="llm_router",
                metadata={"objective": policy.objective},
            )
        else:
            decision = route_with_rules(
                objective=policy.objective,
                candidates=normalized_candidates,
                provider_order=provider_order,
            )

    if (
        decision is not None
        and sticky_store is not None
        and policy.mode == "sticky_session"
        and request.scope
        and sticky_fingerprint is not None
    ):
        sticky_store.save(
            scope=request.scope,
            fingerprint=sticky_fingerprint,
            provider=decision.provider,
            model=decision.model,
            metadata={"decision_source": decision.decision_source},
        )

    return decision
