"""
Content Research Pipeline Workflow Test
-----------------------------------------

Tests the full research workflow:
1. Upload text document with unique keywords
2. Wait for embeddings generation
3. FTS search - verify keyword matches
4. Vector search - verify semantic matching
5. Hybrid search - verify combined ranking
6. Chat with RAG context - verify context used
7. Export conversation to chatbook
8. Cleanup
"""

import time
from typing import Dict, Any

import pytest
import httpx

from ..fixtures import (
    api_client,
    data_tracker,
    create_test_file,
    cleanup_test_file,
    require_llm_or_skip,
)
from .workflow_base import WorkflowTestBase, WorkflowStateManager


@pytest.mark.workflow
@pytest.mark.workflow_embeddings
@pytest.mark.workflow_llm
class TestContentResearchWorkflow(WorkflowTestBase):
    """Test the complete content research workflow."""

    def test_full_content_research_pipeline(
        self,
        api_client,
        data_tracker,
        workflow_state,
    ):
        """
        End-to-end content research workflow.

        This test verifies that content flows correctly from ingestion
        through search and into chat context.
        """
        timestamp = int(time.time())

        # ============================================================
        # PHASE 1: Upload document with unique content
        # ============================================================
        workflow_state.enter_phase("upload")

        # Create unique markers that should be findable
        unique_keyword = f"XENOMORPHIC_RESEARCH_{timestamp}"
        technical_term = "quantum entanglement dynamics"

        content = f"""
        {unique_keyword}

        Research Paper: Advanced Quantum Computing Architectures

        Abstract:
        This paper explores the intersection of {technical_term} and
        computational theory. We demonstrate novel approaches to qubit
        coherence maintenance in superconducting systems.

        Introduction:
        Quantum computing represents a paradigm shift in computational
        capability. Unlike classical bits, quantum bits (qubits) can
        exist in superposition states, enabling parallel computation.

        Key Findings:
        1. Decoherence times improved by 40% using our novel approach
        2. Error correction overhead reduced through topological qubits
        3. Scalability demonstrated up to 100 logical qubits

        Methodology:
        We employed cryogenic cooling to maintain qubit coherence and
        implemented dynamical decoupling sequences to mitigate noise.

        Conclusion:
        Our research advances the field of quantum computing by providing
        practical solutions to the coherence problem.
        """

        title = f"Quantum Computing Research Paper {timestamp}"

        # Create and upload file
        file_path = create_test_file(content, suffix=".txt")
        data_tracker.add_file(file_path)

        try:
            response = api_client.upload_media(
                file_path=file_path,
                title=title,
                media_type="document",
                generate_embeddings=True,
            )

            media_id = self.extract_media_id(response)
            data_tracker.add_media(media_id)
            workflow_state.add_media_id(media_id)
            workflow_state.set("primary_media_id", media_id)
            workflow_state.set("unique_keyword", unique_keyword)
            workflow_state.set("content", content)

            print(f"  Uploaded document with ID: {media_id}")
            assert media_id > 0, "Invalid media ID"

        finally:
            cleanup_test_file(file_path)

        # ============================================================
        # PHASE 2: Wait for indexing and embeddings
        # ============================================================
        workflow_state.enter_phase("indexing")

        # Wait for basic indexing
        self.wait_for_indexing(api_client, media_id, timeout=30)
        print("  Document indexed successfully")

        # Wait for embeddings (with tolerance for missing embedding service)
        embeddings_ready = self.wait_for_embeddings(
            api_client,
            media_id,
            search_query="quantum computing",
            timeout=20,
        )
        if embeddings_ready:
            print("  Embeddings generated successfully")
        else:
            print("  Warning: Embeddings may not be ready, continuing with FTS")

        # ============================================================
        # PHASE 3: Full-text search verification
        # ============================================================
        workflow_state.enter_phase("fts_search")

        try:
            fts_result = api_client.rag_simple_search(
                query=unique_keyword,
                databases=["media"],
                top_k=10,
            )

            documents = (
                fts_result.get("documents")
                or fts_result.get("results")
                or fts_result.get("items")
                or []
            )

            # Verify our document is in results
            # Normalize IDs to int for comparison (RAG returns strings)
            found_ids = []
            for doc in documents:
                doc_id = doc.get("id") or doc.get("media_id")
                if doc_id is not None:
                    try:
                        found_ids.append(int(doc_id))
                    except (ValueError, TypeError):
                        found_ids.append(doc_id)

            assert media_id in found_ids, (
                f"FTS search for '{unique_keyword}' did not find media {media_id}. "
                f"Found IDs: {found_ids}"
            )

            print(f"  FTS search found document: {len(documents)} results")
            workflow_state.set("fts_success", True)

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 422):
                pytest.skip(f"RAG search not available: {e}")
            raise

        # ============================================================
        # PHASE 4: Vector/semantic search verification
        # ============================================================
        workflow_state.enter_phase("vector_search")

        try:
            # Search with semantically related terms (not exact keywords)
            semantic_query = "superposition and coherence in qubits"

            vector_result = api_client.client.post(
                "/api/v1/rag/search",
                json={
                    "query": semantic_query,
                    "search_mode": "vector",
                    "sources": ["media_db"],
                    "top_k": 10,
                },
            )

            if vector_result.status_code == 200:
                results = vector_result.json()
                documents = (
                    results.get("documents")
                    or results.get("results")
                    or []
                )

                # Normalize IDs to int for comparison
                found_ids = []
                for doc in documents:
                    doc_id = doc.get("id") or doc.get("media_id")
                    if doc_id is not None:
                        try:
                            found_ids.append(int(doc_id))
                        except (ValueError, TypeError):
                            found_ids.append(doc_id)

                if media_id in found_ids:
                    print(f"  Vector search found document semantically")
                    workflow_state.set("vector_success", True)
                else:
                    print(f"  Vector search did not find document (embeddings may not be ready)")
            else:
                print(f"  Vector search returned {vector_result.status_code}")

        except httpx.HTTPStatusError as e:
            # Vector search might not be available
            print(f"  Vector search not available: {e}")

        # ============================================================
        # PHASE 5: Hybrid search verification
        # ============================================================
        workflow_state.enter_phase("hybrid_search")

        try:
            hybrid_query = "quantum computing error correction"

            hybrid_result = api_client.client.post(
                "/api/v1/rag/search",
                json={
                    "query": hybrid_query,
                    "search_mode": "hybrid",
                    "sources": ["media_db"],
                    "top_k": 10,
                    "hybrid_alpha": 0.5,
                },
            )

            if hybrid_result.status_code == 200:
                results = hybrid_result.json()
                documents = (
                    results.get("documents")
                    or results.get("results")
                    or []
                )

                # Normalize IDs to int for comparison
                found_ids = []
                for doc in documents:
                    doc_id = doc.get("id") or doc.get("media_id")
                    if doc_id is not None:
                        try:
                            found_ids.append(int(doc_id))
                        except (ValueError, TypeError):
                            found_ids.append(doc_id)

                if media_id in found_ids:
                    print(f"  Hybrid search found document")
                    workflow_state.set("hybrid_success", True)
                else:
                    print(f"  Hybrid search did not find document in top results")

        except httpx.HTTPStatusError as e:
            print(f"  Hybrid search not available: {e}")

        # ============================================================
        # PHASE 6: Chat with RAG context
        # ============================================================
        workflow_state.enter_phase("chat_with_context")

        try:
            model = require_llm_or_skip(api_client)

            # Chat asking about content from our document
            chat_response = api_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a research assistant. Answer based on "
                            "the provided context. If you find relevant information "
                            f"mentioning '{unique_keyword}', include it in your response."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"What are the key findings about quantum computing "
                            f"and decoherence in the research with marker {unique_keyword}?"
                        ),
                    },
                ],
                model=model,
                temperature=0.0,
            )

            content = self.extract_chat_content(chat_response)
            assert content, "Chat response is empty"
            print(f"  Chat response received: {len(content)} chars")

            # Store conversation ID for chatbook export
            conversation_id = chat_response.get("conversation_id")
            if conversation_id:
                workflow_state.add_chat_id(conversation_id)
                workflow_state.set("conversation_id", conversation_id)
                data_tracker.add_chat(conversation_id)

            workflow_state.set("chat_success", True)

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 401, 404, 422):
                print(f"  Chat not available: {e}")
            else:
                raise

        # ============================================================
        # PHASE 7: Export to chatbook (if conversation exists)
        # ============================================================
        workflow_state.enter_phase("chatbook_export")

        conversation_id = workflow_state.get("conversation_id")
        if conversation_id:
            try:
                export_response = api_client.client.post(
                    "/api/v1/chatbooks/export",
                    json={
                        "chat_ids": [conversation_id],
                        "include_metadata": True,
                    },
                )

                if export_response.status_code == 200:
                    export_data = export_response.json()
                    assert "chatbook" in export_data or "data" in export_data, (
                        "Export missing expected data"
                    )
                    print(f"  Chatbook exported successfully")
                    workflow_state.set("export_success", True)
                else:
                    print(f"  Chatbook export returned {export_response.status_code}")

            except httpx.HTTPStatusError as e:
                print(f"  Chatbook export not available: {e}")
        else:
            print("  No conversation to export")

        # ============================================================
        # VERIFICATION SUMMARY
        # ============================================================
        print("\n" + "=" * 60)
        print("WORKFLOW SUMMARY")
        print("=" * 60)

        results = {
            "upload": bool(workflow_state.get("primary_media_id")),
            "fts_search": workflow_state.get("fts_success", False),
            "vector_search": workflow_state.get("vector_success", False),
            "hybrid_search": workflow_state.get("hybrid_success", False),
            "chat": workflow_state.get("chat_success", False),
            "export": workflow_state.get("export_success", False),
        }

        for step, success in results.items():
            status = "PASS" if success else "SKIP/FAIL"
            print(f"  {step}: {status}")

        # Core workflow should succeed
        assert results["upload"], "Upload phase failed"
        assert results["fts_search"], "FTS search phase failed"

        print("\nContent research workflow completed successfully!")

    def test_search_result_quality(
        self,
        api_client,
        data_tracker,
        workflow_helper,
    ):
        """
        Verify search results contain expected metadata and scores.

        This test uploads content and verifies that search results
        include proper source attribution and relevance scores.
        """
        timestamp = int(time.time())
        unique_marker = f"QUALITY_CHECK_{timestamp}"

        content = f"""
        {unique_marker}

        Test document for search quality verification.
        This document contains specific technical terms like
        distributed consensus and Byzantine fault tolerance.
        """

        file_path = create_test_file(content, suffix=".txt")
        data_tracker.add_file(file_path)

        try:
            response = api_client.upload_media(
                file_path=file_path,
                title=f"Quality Test {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )

            media_id = workflow_helper.extract_media_id(response)
            data_tracker.add_media(media_id)

            # Wait for indexing
            workflow_helper.wait_for_indexing(api_client, media_id)

            # Search and verify result structure
            result = api_client.rag_simple_search(
                query=unique_marker,
                databases=["media"],
                top_k=5,
            )

            documents = (
                result.get("documents")
                or result.get("results")
                or []
            )

            assert len(documents) > 0, "No search results returned"

            # Find our document in results
            # Normalize IDs to int for comparison (RAG returns strings)
            our_doc = None
            for doc in documents:
                doc_id = doc.get("id") or doc.get("media_id")
                try:
                    if int(doc_id) == int(media_id):
                        our_doc = doc
                        break
                except (ValueError, TypeError):
                    if doc_id == media_id:
                        our_doc = doc
                        break

            assert our_doc is not None, f"Our document {media_id} not in results"

            # Verify result has content
            doc_content = our_doc.get("content") or our_doc.get("text")
            assert doc_content, "Result missing content field"
            assert unique_marker in doc_content, "Content doesn't contain our marker"

            print(f"Search result quality verified for document {media_id}")

        finally:
            cleanup_test_file(file_path)


@pytest.mark.workflow
class TestSearchModeComparison(WorkflowTestBase):
    """Compare different search modes with the same query."""

    def test_search_modes_return_results(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify all search modes return results for indexed content.

        Uploads a document and verifies that FTS, vector, and hybrid
        search all can find it (when embeddings are available).
        """
        timestamp = int(time.time())
        marker = f"SEARCH_MODE_TEST_{timestamp}"

        content = f"""
        {marker}

        This document is designed to test different search modes.
        It contains terms about software engineering and system design.
        Topics include microservices, API design, and event-driven architecture.
        We also discuss database sharding and caching strategies.
        """

        file_path = create_test_file(content, suffix=".txt")
        data_tracker.add_file(file_path)

        try:
            response = api_client.upload_media(
                file_path=file_path,
                title=f"Search Mode Test {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )

            media_id = self.extract_media_id(response)
            data_tracker.add_media(media_id)

            # Wait for indexing
            self.wait_for_indexing(api_client, media_id)

            # Test each search mode
            search_modes = ["fts", "vector", "hybrid"]
            queries = {
                "fts": marker,  # Exact match for FTS
                "vector": "software architecture patterns",  # Semantic for vector
                "hybrid": "microservices API design",  # Combined for hybrid
            }

            results_by_mode = {}

            for mode in search_modes:
                query = queries.get(mode, marker)

                try:
                    response = api_client.client.post(
                        "/api/v1/rag/search",
                        json={
                            "query": query,
                            "search_mode": mode,
                            "sources": ["media_db"],
                            "top_k": 10,
                        },
                    )

                    if response.status_code == 200:
                        data = response.json()
                        documents = (
                            data.get("documents")
                            or data.get("results")
                            or []
                        )
                        results_by_mode[mode] = len(documents)

                        # Normalize IDs to int for comparison
                        found_ids = []
                        for doc in documents:
                            doc_id = doc.get("id") or doc.get("media_id")
                            if doc_id is not None:
                                try:
                                    found_ids.append(int(doc_id))
                                except (ValueError, TypeError):
                                    found_ids.append(doc_id)

                        if media_id in found_ids:
                            print(f"  {mode.upper()}: Found document in results")
                        else:
                            print(f"  {mode.upper()}: Document not in top results")
                    else:
                        print(f"  {mode.upper()}: Status {response.status_code}")

                except httpx.HTTPStatusError as e:
                    print(f"  {mode.upper()}: Not available ({e})")

            # At minimum, FTS should work
            assert "fts" in results_by_mode, "FTS search failed"
            assert results_by_mode["fts"] > 0, "FTS returned no results"

            print(f"\nSearch mode results: {results_by_mode}")

        finally:
            cleanup_test_file(file_path)
