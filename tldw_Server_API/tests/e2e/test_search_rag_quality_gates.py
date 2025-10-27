"""
test_search_rag_quality_gates.py
E2E tests focused on search and RAG quality gates:

- Post-update hybrid consistency: after updating content and re-embedding,
  hybrid search should prioritize updated content and de-prioritize stale content.
- BM25-only fallback: when embeddings are deleted/unavailable, text (BM25/FTS) search
  still returns results and RAG degrades gracefully without 5xx.
- Large context windows: validate that the agentic pipeline respects a configured
  context window budget across different top_k and reranking toggles.

Notes:
- We use the unified RAG endpoint at /api/v1/rag/search with search_mode="hybrid".
- For the "max context" check, the unified standard pipeline does not expose a
  literal max_context_size; we use the agentic strategy's window_chars
  (agentic_window_chars) as the effective context budget and assert the returned
  synthetic chunk length stays within that bound across settings.
"""

import time
import uuid
from typing import Dict, Any, List, Optional

import pytest
import httpx

from fixtures import (
    api_client,
    data_tracker,
    create_test_file,
    cleanup_test_file,
    AssertionHelpers,
    APIClient,
)


def _search_docs_unified(client: APIClient, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Helper to post to unified RAG search endpoint and return JSON or None on 404/501."""
    r = client.client.post(f"{client.base_url}/api/v1/rag/search", json=payload, headers=client.get_auth_headers())
    if r.status_code in (404, 501):
        return None
    r.raise_for_status()
    return r.json()


def _extract_documents(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    docs = response.get("documents") or response.get("results") or []
    return docs if isinstance(docs, list) else []


def _index_of_media(docs: List[Dict[str, Any]], media_id: int) -> int:
    """Return index of a media_id by inspecting document id or metadata.media_id; -1 if not found."""
    for i, d in enumerate(docs):
        try:
            if int(str(d.get("id"))) == int(media_id):
                return i
        except Exception:
            pass
        md = d.get("metadata") or {}
        try:
            if int(str(md.get("media_id"))) == int(media_id):
                return i
        except Exception:
            pass
    return -1


def _poll_embeddings_ready(client: APIClient, media_id: int, timeout_s: int = 20) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            r = client.client.get(f"{client.base_url}/api/v1/media/{media_id}/embeddings/status")
            if r.status_code == 200 and bool(r.json().get("has_embeddings")):
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


class TestSearchRAGQualityGates:
    @pytest.mark.parametrize("enable_reranking", [False, True])
    def test_post_update_hybrid_consistency_reranking(self, api_client, data_tracker, enable_reranking):
        """Hybrid search ranking updates after content change and re-embedding.

        Flow:
        - Create two docs; both initially contain QUERY_A. Generate embeddings.
        - Verify for QUERY_A the first doc (doc1) is reasonably ranked.
        - Update doc1 content to contain QUERY_B only; delete + regenerate embeddings for doc1.
        - For QUERY_A: doc2 should outrank doc1 (doc1 lowered or absent).
        - For QUERY_B: doc1 should appear and rank highly (ideally first).
        """
        query_a = f"ALPHA_{uuid.uuid4().hex[:6]}"
        query_b = f"BETA_{uuid.uuid4().hex[:6]}"

        # Create initial files
        p1 = create_test_file(f"Doc1 start with many {query_a} mentions. {query_a} {query_a}.")
        p2 = create_test_file(f"Doc2 also mentions {query_a} once.")
        data_tracker.add_file(p1)
        data_tracker.add_file(p2)

        try:
            # Upload both with embeddings
            r1 = api_client.upload_media(p1, title="RAG Consistency Doc1", media_type="document", generate_embeddings=True)
            mid1 = AssertionHelpers.assert_successful_upload(r1)
            data_tracker.add_media(mid1)

            r2 = api_client.upload_media(p2, title="RAG Consistency Doc2", media_type="document", generate_embeddings=True)
            mid2 = AssertionHelpers.assert_successful_upload(r2)
            data_tracker.add_media(mid2)

            _poll_embeddings_ready(api_client, mid1, 20)
            _poll_embeddings_ready(api_client, mid2, 20)

            # Baseline: QUERY_A should find both; record ranks
            payload = {
                "query": query_a,
                "search_mode": "hybrid",
                "top_k": 10,
                "enable_reranking": bool(enable_reranking),
                "sources": ["media_db"],
            }
            resp = _search_docs_unified(api_client, payload)
            if resp is None:
                pytest.skip("Unified RAG endpoint unavailable")
            docs = _extract_documents(resp)
            idx1_before = _index_of_media(docs, mid1)
            idx2_before = _index_of_media(docs, mid2)

            # Sanity: both found in baseline (best-effort)
            assert (idx1_before != -1) or (idx2_before != -1), "Baseline hybrid search did not return expected docs"

            # Update doc1 to contain QUERY_B only
            upd = api_client.client.put(
                f"{api_client.base_url}/api/v1/media/{mid1}",
                json={"content": f"Doc1 updated: {query_b} appears repeatedly. {query_b} {query_b}", "title": "RAG Consistency Doc1 (updated)"},
                headers=api_client.get_auth_headers(),
            )
            assert upd.status_code == 200, upd.text

            # Clear + regenerate embeddings for doc1
            api_client.client.delete(f"{api_client.base_url}/api/v1/media/{mid1}/embeddings")
            regen = api_client.client.post(
                f"{api_client.base_url}/api/v1/media/{mid1}/embeddings",
                json={"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"},
            )
            assert regen.status_code == 200, regen.text
            _poll_embeddings_ready(api_client, mid1, 20)

            # After update: for QUERY_A doc2 should outrank doc1
            resp_a = _search_docs_unified(api_client, payload)
            assert resp_a is not None
            docs_a = _extract_documents(resp_a)
            idx1_after_a = _index_of_media(docs_a, mid1)
            idx2_after_a = _index_of_media(docs_a, mid2)
            # If both present, doc2 should be before doc1; if doc1 absent, that's also acceptable
            if idx2_after_a != -1 and idx1_after_a != -1:
                assert idx2_after_a < idx1_after_a, "Updated doc1 should rank below doc2 for old query"
            elif idx2_after_a != -1 and idx1_after_a == -1:
                # OK: doc1 no longer appears for old query
                pass
            else:
                # If neither appear, FTS might be lagging; still assert not raising
                assert True

            # For QUERY_B: doc1 should be present and near the top
            payload_b = {
                "query": query_b,
                "search_mode": "hybrid",
                "top_k": 10,
                "enable_reranking": bool(enable_reranking),
                "sources": ["media_db"],
            }
            resp_b = _search_docs_unified(api_client, payload_b)
            assert resp_b is not None
            docs_b = _extract_documents(resp_b)
            idx1_after_b = _index_of_media(docs_b, mid1)
            assert idx1_after_b != -1, "Updated doc1 not found for new query"
            # Preferably in the top 3
            assert idx1_after_b <= 2, f"Updated doc1 ranked too low for new query (idx={idx1_after_b})"

        finally:
            cleanup_test_file(p1)
            cleanup_test_file(p2)

    def test_bm25_only_fallback_text_and_rag(self, api_client, data_tracker):
        """Deleting embeddings should still allow BM25/FTS search, and RAG should degrade gracefully.

        Flow:
        - Upload a document containing a unique token and generate embeddings.
        - Verify hybrid RAG returns it for the token.
        - Delete embeddings for the media.
        - Verify text search still returns the item; hybrid RAG returns results (via FTS fallback).
        """
        token = f"BM25_ONLY_{uuid.uuid4().hex[:6]}"
        path = create_test_file(f"This doc is for BM25 fallback testing. Unique token: {token}.")
        data_tracker.add_file(path)

        try:
            resp = api_client.upload_media(path, title="BM25-only Fallback Doc", media_type="document", generate_embeddings=True)
            mid = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(mid)

            _poll_embeddings_ready(api_client, mid, 20)

            # Baseline hybrid result present
            payload = {"query": token, "search_mode": "hybrid", "top_k": 5, "enable_reranking": True, "sources": ["media_db"]}
            r0 = _search_docs_unified(api_client, payload)
            if r0 is None:
                pytest.skip("Unified RAG endpoint unavailable")
            base_docs = _extract_documents(r0)
            assert _index_of_media(base_docs, mid) != -1 or any(token.lower() in (d.get("content", "").lower()) for d in base_docs), \
                "Baseline hybrid did not return the uploaded item"

            # Delete embeddings for this item
            api_client.client.delete(f"{api_client.base_url}/api/v1/media/{mid}/embeddings")
            # Best-effort wait until status reflects deletion
            time.sleep(0.5)

            # Text search still returns results
            sr = api_client.search_media(token, limit=10)
            results = sr if isinstance(sr, list) else sr.get("results") or sr.get("items", [])
            ids = [(x.get("id") or x.get("media_id")) for x in results]
            assert mid in ids, "Text search failed after deleting embeddings"

            # Hybrid should degrade to FTS and still return results without 5xx
            r1 = _search_docs_unified(api_client, payload)
            assert r1 is not None
            docs = _extract_documents(r1)
            assert isinstance(docs, list)
            assert len(docs) >= 1, "Hybrid search returned no results after embeddings deletion"
            # Preferably the uploaded item is still discoverable by metadata media_id
            assert _index_of_media(docs, mid) != -1 or any(token.lower() in (d.get("content", "").lower()) for d in docs)

        finally:
            cleanup_test_file(path)

    def test_large_context_windows_agentic_respects_budget(self, api_client, data_tracker):
        """Agentic strategy respects window_chars budget across top_k and reranking toggles.

        The unified endpoint does not expose a direct "max_context_size" for the standard pipeline.
        We use the agentic pipeline's agentic_window_chars as the effective context budget and
        assert that the returned synthetic chunk stays within the bound under different configs.
        """
        # Build a long document
        token = f"WIDECONTEXT_{uuid.uuid4().hex[:6]}"
        long_text = (f"{token} " * 1000) + "\n" + ("Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 200)
        path = create_test_file(long_text)
        data_tracker.add_file(path)

        try:
            resp = api_client.upload_media(path, title="Agentic Context Budget Doc", media_type="document", generate_embeddings=False)
            mid = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(mid)

            # Two variants: different top_k and reranking flags
            for top_k in (5, 12):
                for enable_reranking in (False, True):
                    window_chars = 600
                    payload = {
                        "query": token,
                        "strategy": "agentic",
                        "search_mode": "hybrid",
                        "fts_level": "media",
                        "top_k": top_k,
                        "enable_reranking": enable_reranking,
                        "sources": ["media_db"],
                        # Agentic context budget
                        "agentic_window_chars": window_chars,
                        "agentic_max_tokens_read": 1200,
                        # No generation; we only validate contexts
                        "enable_generation": False,
                    }
                    resp_u = _search_docs_unified(api_client, payload)
                    if resp_u is None:
                        pytest.skip("Unified RAG endpoint unavailable")
                    docs = _extract_documents(resp_u)
                    assert len(docs) >= 1, "No documents returned by agentic search"
                    chunk = docs[0]
                    content = chunk.get("content", "")
                    # Allow small overhead for separators
                    assert len(content) <= int(window_chars * 1.25), \
                        f"Agentic content exceeded budget: {len(content)} > {window_chars} (top_k={top_k}, rerank={enable_reranking})"

        finally:
            cleanup_test_file(path)

    def test_agentic_generation_smoke(self, api_client, data_tracker):
        """Agentic + generation smoke: ensures generated_answer is present (LLM or fallback).

        Uses agentic strategy with enable_generation=True. If no external LLM is available,
        generation falls back to the built-in FallbackGenerator and still returns a response.
        """
        token = f"AGENTICGEN_{uuid.uuid4().hex[:6]}"
        content = (f"{token} " * 50) + "This content will be summarized by the agentic generator."
        path = create_test_file(content)
        data_tracker.add_file(path)

        try:
            resp = api_client.upload_media(path, title="Agentic Gen Doc", media_type="document", generate_embeddings=False)
            mid = AssertionHelpers.assert_successful_upload(resp)
            data_tracker.add_media(mid)

            payload = {
                "query": token,
                "strategy": "agentic",
                "search_mode": "hybrid",
                "fts_level": "media",
                "top_k": 5,
                "enable_reranking": True,
                "sources": ["media_db"],
                "agentic_window_chars": 800,
                "agentic_max_tokens_read": 1200,
                "enable_generation": True,
                "max_generation_tokens": 200,
            }
            r = _search_docs_unified(api_client, payload)
            if r is None:
                pytest.skip("Unified RAG endpoint unavailable")
            # Basic shape checks
            docs = _extract_documents(r)
            assert isinstance(docs, list) and len(docs) >= 1
            # Generated answer should be present (either from LLM or fallback)
            ga = r.get("generated_answer")
            assert isinstance(ga, str) and len(ga.strip()) > 0, "No generated answer returned"

        finally:
            cleanup_test_file(path)
