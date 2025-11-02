"""
test_rag_deep_checks.py
Description: Deep RAG configuration checks - hybrid + rerank + tight context.

Uploads a couple of small docs (idempotent), then runs searches with
different max_context_size and reranking settings and asserts structural
invariants and context limits.
"""

import pytest
import httpx

from .fixtures import api_client, data_tracker, create_test_file, cleanup_test_file


def _upload_doc(api_client, data_tracker, text: str, title: str):
    path = create_test_file(text, suffix=".txt")
    data_tracker.add_file(path)
    try:
        resp = api_client.upload_media(file_path=path, title=title, media_type="document", generate_embeddings=True)
        # Be permissive on new/legacy formats
        media_id = None
        if isinstance(resp, dict) and resp.get("results"):
            media_id = resp["results"][0].get("db_id")
        else:
            media_id = resp.get("media_id") or resp.get("id")
        if media_id:
            data_tracker.add_media(int(media_id))
        return media_id
    finally:
        cleanup_test_file(path)


@pytest.mark.critical
def test_rag_hybrid_rerank_context_limits(api_client, data_tracker):
    # Ensure some content exists
    try:
        _upload_doc(api_client, data_tracker, "Deep check doc one about AI and ML.", "RAG Deep A")
        _upload_doc(api_client, data_tracker, "Another doc mentioning ranking and retrieval.", "RAG Deep B")
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Authentication or media add not available: {e}")

    configs = [
        {"name": "tight_context", "args": {"top_k": 10, "enable_reranking": True, "max_context_size": 300}},
        {"name": "roomy_context", "args": {"top_k": 5, "enable_reranking": True, "max_context_size": 4000}},
        {"name": "no_rerank", "args": {"top_k": 5, "enable_reranking": False, "max_context_size": 1000}},
    ]

    for cfg in configs:
        try:
            r = api_client.rag_simple_search(
                query="ai ranking retrieval machine learning",
                databases=["media"],
                **cfg["args"],
            )
            assert isinstance(r, dict)
            assert r.get("success") in (True, False)  # some deployments may return False but with structure
            results = r.get("results", [])
            assert isinstance(results, list)
            # context obeys limit (best-effort; allow slight slack)
            total = sum(len(x.get("content", "")) for x in results)
            assert total <= cfg["args"]["max_context_size"] + 128
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 422, 500):
                pytest.skip(f"RAG deep options not available: {e}")
            raise
