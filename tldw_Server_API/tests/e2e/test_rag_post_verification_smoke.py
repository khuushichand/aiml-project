"""
E2E smoke test for RAG endpoint with post-verification enabled.

Ensures the endpoint accepts the new flags and returns a valid response.
If generation is available, verifies metadata.post_verification is present.
"""

import pytest
from fixtures import api_client


@pytest.mark.requires_rag
def test_rag_search_with_post_verification_smoke(api_client):
    payload = {
        "query": "What is RAG?",
        "sources": ["media_db"],
        "search_mode": "hybrid",
        "top_k": 5,
        # Enable generation + post-verification. If generation is unavailable,
        # this is still a smoke test - we assert basic shape of response.
        "enable_generation": True,
        "enable_post_verification": True,
        "adaptive_max_retries": 1,
        "adaptive_unsupported_threshold": 0.2,
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

    # If the service generated an answer, post_verification metadata should be attached.
    if data.get("generated_answer"):
        pv = (data.get("metadata") or {}).get("post_verification")
        assert isinstance(pv, dict), "post_verification block missing when generation is present"
        assert "unsupported_ratio" in pv
        assert "total_claims" in pv
        assert "unsupported_count" in pv
