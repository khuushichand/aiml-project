"""
E2E smoke test exercising new Generation & Grounding payload fields.

This test is intentionally light: it verifies the endpoint accepts the new
flags and, when the pipeline produces generation, that relevant metadata
blocks are present. It does not assert on specific model outputs.
"""

import pytest
from fixtures import api_client


@pytest.mark.requires_rag
def test_rag_generation_grounding_smoke(api_client):
    # Numeric query to trigger numeric/table-aware boost code path
    payload = {
        "query": "What was Acme Corp revenue in 2024 and growth %?",
        "sources": ["media_db"],
        "search_mode": "hybrid",
        "top_k": 5,
        # Routing & advanced retrieval knobs
        "enable_intent_routing": True,
        "enable_multi_vector_passages": True,  # may no-op if embeddings not available
        "enable_numeric_table_boost": True,
        # Reranking/generation
        "enable_reranking": True,
        "reranking_strategy": "two_tier",
        "enable_generation": True,
        # Abstention & synthesis
        "enable_abstention": True,
        "abstention_behavior": "ask",
        "enable_multi_turn_synthesis": True,
        "synthesis_time_budget_sec": 3.0,
        "synthesis_draft_tokens": 128,
        "synthesis_refine_tokens": 256,
    }

    r = api_client.client.post(
        f"{api_client.base_url}/api/v1/rag/search",
        json=payload,
        headers=api_client.get_auth_headers(),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict)
    assert "documents" in data
    assert "metadata" in data

    md = data.get("metadata") or {}

    # Intent routing should populate a routing block
    ir = md.get("intent_routing")
    assert isinstance(ir, dict), "intent_routing metadata missing"
    assert "hybrid_alpha" in ir and "top_k" in ir

    # Numeric/table boost should record summary for numeric queries
    ntb = md.get("numeric_table_boost")
    assert isinstance(ntb, dict) and ntb.get("enabled") is True

    # If generation occurred, synthesis metadata should be present (or gated)
    if data.get("generated_answer"):
        syn = md.get("synthesis")
        gate = md.get("generation_gate")
        assert isinstance(syn, dict) or isinstance(gate, dict)
