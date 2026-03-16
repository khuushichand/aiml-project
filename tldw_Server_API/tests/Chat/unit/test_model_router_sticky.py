import pytest

from tldw_Server_API.app.core.LLM_Calls.routing.decision_store import (
    InMemoryRoutingDecisionStore,
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
