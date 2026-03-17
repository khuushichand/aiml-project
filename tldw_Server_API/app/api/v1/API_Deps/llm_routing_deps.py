"""Dependencies for model-routing integrations."""

from __future__ import annotations

from fastapi import Request

from tldw_Server_API.app.core.LLM_Calls.routing.decision_store import (
    InMemoryRoutingDecisionStore,
)

DEFAULT_ROUTING_DECISION_STORE_MAX_ENTRIES = 1024
DEFAULT_ROUTING_DECISION_STORE_TTL_SECONDS = 3600


def get_request_routing_decision_store(request: Request) -> InMemoryRoutingDecisionStore:
    """Return the app-scoped routing store, creating it lazily when needed."""

    store = getattr(request.app.state, "routing_decision_store", None)
    if isinstance(store, InMemoryRoutingDecisionStore):
        return store

    store = InMemoryRoutingDecisionStore(
        max_entries=DEFAULT_ROUTING_DECISION_STORE_MAX_ENTRIES,
        ttl_seconds=DEFAULT_ROUTING_DECISION_STORE_TTL_SECONDS,
    )
    request.app.state.routing_decision_store = store
    return store
