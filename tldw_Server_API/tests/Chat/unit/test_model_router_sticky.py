import pytest
from datetime import datetime, timedelta, timezone

from tldw_Server_API.app.core.LLM_Calls.routing.decision_store import (
    InMemoryRoutingDecisionStore,
    StoredRoutingDecision,
    maybe_reuse_sticky_decision,
)


@pytest.mark.unit
def test_sticky_decision_is_bypassed_when_tools_become_required():
    store = InMemoryRoutingDecisionStore()
    store.save(
        scope="conv-1",
        fingerprint="chat|no-tools",
        provider="openai",
        model="gpt-4.1-mini",
    )

    reused = maybe_reuse_sticky_decision(
        store=store,
        scope="conv-1",
        fingerprint="chat|tools-required",
    )

    assert reused is None


@pytest.mark.unit
def test_sticky_decision_is_reused_when_fingerprint_matches():
    store = InMemoryRoutingDecisionStore()
    store.save(
        scope="conv-1",
        fingerprint="chat|tools-unchanged",
        provider="openai",
        model="gpt-4.1-mini",
    )

    reused = maybe_reuse_sticky_decision(
        store=store,
        scope="conv-1",
        fingerprint="chat|tools-unchanged",
    )

    assert reused is not None
    assert reused.provider == "openai"
    assert reused.model == "gpt-4.1-mini"


@pytest.mark.unit
def test_stored_routing_decision_metadata_is_immutable():
    stored = StoredRoutingDecision(
        scope="conv-1",
        fingerprint="fp-1",
        provider="openai",
        model="gpt-4.1-mini",
        metadata={"decision_source": "rules_router"},
    )

    with pytest.raises(TypeError):
        stored.metadata["decision_source"] = "llm_router"


@pytest.mark.unit
def test_sticky_store_evicts_oldest_scope_when_capacity_is_exceeded():
    store = InMemoryRoutingDecisionStore(max_entries=2)
    store.save(scope="conv-1", fingerprint="fp-1", provider="openai", model="gpt-4.1-mini")
    store.save(scope="conv-2", fingerprint="fp-2", provider="openai", model="gpt-4.1")

    store.save(scope="conv-3", fingerprint="fp-3", provider="anthropic", model="claude-sonnet-4.5")

    assert store.load("conv-1") is None
    assert store.load("conv-2") is not None
    assert store.load("conv-3") is not None


@pytest.mark.unit
def test_sticky_store_drops_expired_decisions_on_load():
    store = InMemoryRoutingDecisionStore(ttl_seconds=60)
    expired = StoredRoutingDecision(
        scope="conv-expired",
        fingerprint="fp-expired",
        provider="openai",
        model="gpt-4.1-mini",
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    store._decisions["conv-expired"] = expired

    assert store.load("conv-expired") is None
