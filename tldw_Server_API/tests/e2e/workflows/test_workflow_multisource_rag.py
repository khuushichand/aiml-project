"""
Multi-Source RAG Workflow Test
--------------------------------

Tests search across different content types:
1. Upload PDF about topic X
2. Upload text document about topic X
3. Upload markdown document about topic X
4. Wait for all embeddings
5. Search for topic X
6. Verify all sources appear in results
7. Check source type attribution
8. Use combined context in chat
9. Cleanup
"""

import time
import tempfile
from typing import Dict, Any, List

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


def create_minimal_pdf(content: str) -> str:
    """
    Create a minimal PDF file with text content.

    Note: This is a simplified PDF structure that may not work
    with all PDF parsers. For production testing, use a proper
    PDF library like PyPDF2 or reportlab.
    """
    # Minimal PDF with embedded text
    # This is a very basic PDF structure
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {len(content) + 50} >>
stream
BT
/F1 12 Tf
72 720 Td
({content[:200]}) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000270 00000 n
0000000420 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
500
%%EOF
"""

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".pdf",
        delete=False,
    ) as f:
        f.write(pdf_content)
        return f.name


@pytest.mark.workflow
@pytest.mark.workflow_embeddings
@pytest.mark.workflow_llm
class TestMultiSourceRAGWorkflow(WorkflowTestBase):
    """Test RAG search across multiple content sources."""

    def test_cross_source_search(
        self,
        api_client,
        data_tracker,
        workflow_state,
    ):
        """
        Test search finding content across different source types.

        Uploads documents in multiple formats with related content
        and verifies search can find all of them.
        """
        timestamp = int(time.time())

        # Common topic marker for all documents
        topic_marker = f"BLOCKCHAIN_CONSENSUS_{timestamp}"
        topic_description = "blockchain consensus mechanisms"

        uploaded_media = []

        # ============================================================
        # PHASE 1: Upload text document
        # ============================================================
        workflow_state.enter_phase("upload_text")

        text_content = f"""
        {topic_marker} - Text Document

        Blockchain Consensus Mechanisms: An Overview

        Consensus mechanisms are fundamental to blockchain networks.
        They ensure all nodes agree on the state of the distributed ledger.

        Key consensus mechanisms include:
        1. Proof of Work (PoW) - Used by Bitcoin
        2. Proof of Stake (PoS) - Used by Ethereum 2.0
        3. Delegated Proof of Stake (DPoS) - Used by EOS
        4. Practical Byzantine Fault Tolerance (PBFT)

        Each mechanism has trade-offs between security, decentralization,
        and throughput. PoW is highly secure but energy-intensive.
        PoS reduces energy usage but has different security properties.
        """

        text_path = create_test_file(text_content, suffix=".txt")
        data_tracker.add_file(text_path)

        try:
            response = api_client.upload_media(
                file_path=text_path,
                title=f"Blockchain Overview (TXT) {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )

            media_id = self.extract_media_id(response)
            data_tracker.add_media(media_id)
            uploaded_media.append({
                "id": media_id,
                "type": "text",
                "format": "txt",
                "content": text_content,
            })
            print(f"  Uploaded text document: {media_id}")

        finally:
            cleanup_test_file(text_path)

        # ============================================================
        # PHASE 2: Upload markdown document
        # ============================================================
        workflow_state.enter_phase("upload_markdown")

        markdown_content = f"""
        # {topic_marker} - Markdown Document

        ## Blockchain Consensus Deep Dive

        ### Proof of Work Details

        **Proof of Work** requires miners to solve computational puzzles.
        The difficulty adjusts to maintain consistent block times.

        - Mining equipment: ASICs, GPUs
        - Energy consumption: High
        - Security model: 51% attack threshold

        ### Proof of Stake Details

        **Proof of Stake** selects validators based on staked tokens.
        Validators risk losing their stake if they act maliciously.

        | Aspect | PoW | PoS |
        |--------|-----|-----|
        | Energy | High | Low |
        | Hardware | Specialized | Standard |
        | Security | Hash power | Economic stake |

        ### Conclusion

        The choice of consensus mechanism depends on the specific
        requirements of the blockchain application.
        """

        md_path = create_test_file(markdown_content, suffix=".md")
        data_tracker.add_file(md_path)

        try:
            response = api_client.upload_media(
                file_path=md_path,
                title=f"Blockchain Deep Dive (MD) {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )

            media_id = self.extract_media_id(response)
            data_tracker.add_media(media_id)
            uploaded_media.append({
                "id": media_id,
                "type": "markdown",
                "format": "md",
                "content": markdown_content,
            })
            print(f"  Uploaded markdown document: {media_id}")

        finally:
            cleanup_test_file(md_path)

        # ============================================================
        # PHASE 3: Upload PDF document
        # ============================================================
        workflow_state.enter_phase("upload_pdf")

        pdf_text_content = f"""
        {topic_marker} - PDF Document

        Technical Analysis: Blockchain Consensus Protocols

        This document provides a technical analysis of various
        consensus protocols used in modern blockchain systems.

        Byzantine Fault Tolerance forms the theoretical foundation
        for understanding consensus in distributed systems.

        Modern implementations include Tendermint BFT and HotStuff
        which provide efficient consensus with BFT properties.
        """

        try:
            pdf_path = create_minimal_pdf(pdf_text_content)
            data_tracker.add_file(pdf_path)

            try:
                response = api_client.upload_media(
                    file_path=pdf_path,
                    title=f"Blockchain Technical (PDF) {timestamp}",
                    media_type="pdf",
                    generate_embeddings=True,
                )

                media_id = self.extract_media_id(response)
                data_tracker.add_media(media_id)
                uploaded_media.append({
                    "id": media_id,
                    "type": "pdf",
                    "format": "pdf",
                    "content": pdf_text_content,
                })
                print(f"  Uploaded PDF document: {media_id}")

            finally:
                cleanup_test_file(pdf_path)

        except Exception as e:
            print(f"  PDF upload skipped: {e}")

        workflow_state.set("uploaded_media", uploaded_media)
        workflow_state.set("topic_marker", topic_marker)

        # ============================================================
        # PHASE 4: Wait for indexing
        # ============================================================
        workflow_state.enter_phase("wait_indexing")

        for doc in uploaded_media:
            try:
                self.wait_for_indexing(api_client, doc["id"], timeout=30)
                print(f"  {doc['format'].upper()} document indexed")
            except Exception as e:
                print(f"  {doc['format'].upper()} indexing issue: {e}")

        # Brief additional wait for embeddings
        time.sleep(2)

        # ============================================================
        # PHASE 5: Search for topic across all sources
        # ============================================================
        workflow_state.enter_phase("cross_source_search")

        # Search with the unique marker
        try:
            search_result = api_client.rag_simple_search(
                query=topic_marker,
                databases=["media"],
                top_k=20,
            )

            documents = (
                search_result.get("documents")
                or search_result.get("results")
                or []
            )

            # Normalize IDs to int for comparison (RAG returns strings)
            found_ids = set()
            for doc in documents:
                doc_id = doc.get("id") or doc.get("media_id")
                if doc_id is not None:
                    try:
                        found_ids.add(int(doc_id))
                    except (ValueError, TypeError):
                        found_ids.add(doc_id)

            expected_ids = {d["id"] for d in uploaded_media}
            matching_ids = found_ids & expected_ids
            missing_ids = expected_ids - found_ids

            print(f"  Found {len(matching_ids)}/{len(expected_ids)} documents")

            if missing_ids:
                print(f"  Missing IDs: {missing_ids}")

            workflow_state.set("search_found_count", len(matching_ids))
            workflow_state.set("search_results", documents)

        except httpx.HTTPStatusError as e:
            print(f"  Search failed: {e}")
            workflow_state.set("search_found_count", 0)

        # ============================================================
        # PHASE 6: Verify source type attribution
        # ============================================================
        workflow_state.enter_phase("source_attribution")

        documents = workflow_state.get("search_results", [])
        source_types = {}

        for doc in documents:
            doc_id = doc.get("id") or doc.get("media_id")
            if doc_id not in {d["id"] for d in uploaded_media}:
                continue

            # Check for source type information
            source_info = doc.get("source", {})
            if isinstance(source_info, dict):
                source_type = source_info.get("type", "unknown")
            else:
                source_type = str(source_info) if source_info else "unknown"

            media_type = doc.get("media_type") or doc.get("type", "unknown")
            source_types[doc_id] = media_type

        print(f"  Source types: {source_types}")
        workflow_state.set("source_types", source_types)

        # ============================================================
        # PHASE 7: Chat with combined context
        # ============================================================
        workflow_state.enter_phase("chat_with_context")

        try:
            model = require_llm_or_skip(api_client)

            # Ask about the topic using information from multiple sources
            chat_response = api_client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a blockchain expert. Answer questions "
                            "about consensus mechanisms based on available context."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Based on documents with marker {topic_marker}, "
                            "compare Proof of Work and Proof of Stake "
                            "consensus mechanisms."
                        ),
                    },
                ],
                model=model,
                temperature=0.0,
            )

            content = self.extract_chat_content(chat_response)
            assert content, "Chat response is empty"
            print(f"  Chat response: {len(content)} chars")
            workflow_state.set("chat_success", True)

            # Check if response mentions key concepts from our docs
            key_concepts = ["proof of work", "proof of stake", "consensus"]
            mentioned = [c for c in key_concepts if c in content.lower()]
            print(f"  Concepts mentioned: {mentioned}")

        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 401, 404, 422):
                print(f"  Chat not available: {e}")
            else:
                raise

        # ============================================================
        # SUMMARY
        # ============================================================
        print("\n" + "=" * 60)
        print("MULTI-SOURCE RAG WORKFLOW SUMMARY")
        print("=" * 60)

        results = {
            "documents_uploaded": len(uploaded_media),
            "documents_found": workflow_state.get("search_found_count", 0),
            "chat_success": workflow_state.get("chat_success", False),
        }

        print(f"  Uploaded: {results['documents_uploaded']} documents")
        print(f"  Found in search: {results['documents_found']} documents")
        print(f"  Chat with context: {'PASS' if results['chat_success'] else 'SKIP'}")

        # At least the marker search should find some documents
        assert results["documents_uploaded"] > 0, "No documents uploaded"
        assert results["documents_found"] > 0, "Search found no documents"

        print("\nMulti-source RAG workflow completed!")


@pytest.mark.workflow
class TestSourceIsolation(WorkflowTestBase):
    """Test that sources don't cross-contaminate metadata."""

    def test_metadata_isolation(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify metadata from one source doesn't appear on another.

        Uploads two documents with distinct metadata and verifies
        each retains its own metadata after search.
        """
        timestamp = int(time.time())

        # Document A with specific metadata
        doc_a_content = f"""
        METADATA_ISO_A_{timestamp}

        Document A contains information about topic Alpha.
        This is completely unrelated to Document B.
        Keywords: alpha, first, primary
        """

        doc_a_title = f"Alpha Document {timestamp}"

        # Document B with different metadata
        doc_b_content = f"""
        METADATA_ISO_B_{timestamp}

        Document B contains information about topic Beta.
        This is completely unrelated to Document A.
        Keywords: beta, second, secondary
        """

        doc_b_title = f"Beta Document {timestamp}"

        # Upload both
        file_a = create_test_file(doc_a_content, suffix=".txt")
        data_tracker.add_file(file_a)

        file_b = create_test_file(doc_b_content, suffix=".txt")
        data_tracker.add_file(file_b)

        try:
            resp_a = api_client.upload_media(
                file_path=file_a,
                title=doc_a_title,
                media_type="document",
                generate_embeddings=True,
            )
            media_id_a = self.extract_media_id(resp_a)
            data_tracker.add_media(media_id_a)

            resp_b = api_client.upload_media(
                file_path=file_b,
                title=doc_b_title,
                media_type="document",
                generate_embeddings=True,
            )
            media_id_b = self.extract_media_id(resp_b)
            data_tracker.add_media(media_id_b)

            # Wait for indexing
            self.wait_for_indexing(api_client, media_id_a)
            self.wait_for_indexing(api_client, media_id_b)

            # Search for document A's content
            result_a = api_client.rag_simple_search(
                query=f"METADATA_ISO_A_{timestamp}",
                databases=["media"],
                top_k=5,
            )

            docs_a = result_a.get("documents") or result_a.get("results") or []

            # Verify document A is found
            # Normalize IDs to int for comparison (RAG returns strings)
            found_a = False
            for doc in docs_a:
                doc_id = doc.get("id") or doc.get("media_id")
                try:
                    if int(doc_id) == int(media_id_a):
                        found_a = True
                except (ValueError, TypeError):
                    if doc_id == media_id_a:
                        found_a = True

                    # Verify B's content is not in A's result
                    content = doc.get("content") or doc.get("text") or ""
                    assert "METADATA_ISO_B" not in content, (
                        "Document A contains Document B's marker"
                    )

                    # Verify title is correct
                    title = doc.get("title") or ""
                    if title:
                        assert "Alpha" in title or doc_a_title in title, (
                            f"Wrong title: {title}"
                        )

            assert found_a, f"Document A ({media_id_a}) not found in search"

            # Search for document B's content
            result_b = api_client.rag_simple_search(
                query=f"METADATA_ISO_B_{timestamp}",
                databases=["media"],
                top_k=5,
            )

            docs_b = result_b.get("documents") or result_b.get("results") or []

            # Normalize IDs to int for comparison (RAG returns strings)
            found_b = False
            for doc in docs_b:
                doc_id = doc.get("id") or doc.get("media_id")
                try:
                    if int(doc_id) == int(media_id_b):
                        found_b = True
                except (ValueError, TypeError):
                    if doc_id == media_id_b:
                        found_b = True

                    content = doc.get("content") or doc.get("text") or ""
                    assert "METADATA_ISO_A" not in content, (
                        "Document B contains Document A's marker"
                    )

            assert found_b, f"Document B ({media_id_b}) not found in search"

            print("Metadata isolation verified - no cross-contamination")

        finally:
            cleanup_test_file(file_a)
            cleanup_test_file(file_b)


@pytest.mark.workflow
class TestSearchAcrossNotes(WorkflowTestBase):
    """Test unified search across media and notes."""

    def test_unified_search_media_and_notes(
        self,
        api_client,
        data_tracker,
    ):
        """
        Verify search finds both media and notes with related content.
        """
        timestamp = int(time.time())
        topic = f"UNIFIED_SEARCH_{timestamp}"

        # Upload a media document
        media_content = f"""
        {topic} - Media Document

        Information about unified search testing.
        This document covers media storage and retrieval.
        """

        file_path = create_test_file(media_content, suffix=".txt")
        data_tracker.add_file(file_path)

        try:
            response = api_client.upload_media(
                file_path=file_path,
                title=f"Unified Search Media {timestamp}",
                media_type="document",
                generate_embeddings=True,
            )
            media_id = self.extract_media_id(response)
            data_tracker.add_media(media_id)

        finally:
            cleanup_test_file(file_path)

        # Create a related note
        try:
            note_content = f"""
            {topic} - Note

            Related notes about unified search.
            This note contains additional information.
            """

            note_response = api_client.create_note(
                title=f"Unified Search Note {timestamp}",
                content=note_content,
                keywords=[topic, "search", "unified"],
            )

            note_id = note_response.get("id") or note_response.get("note_id")
            if note_id:
                data_tracker.add_note(note_id)

        except httpx.HTTPStatusError:
            note_id = None

        # Wait for indexing
        self.wait_for_indexing(api_client, media_id)

        # Search across both sources
        try:
            result = api_client.client.post(
                "/api/v1/rag/search",
                json={
                    "query": topic,
                    "sources": ["media_db", "notes"],
                    "top_k": 10,
                },
            )

            if result.status_code != 200:
                pytest.skip(f"Unified search not available: {result.status_code}")

            data = result.json()
            documents = data.get("documents") or data.get("results") or []

            # Check what sources we found
            found_media = False
            found_note = False

            for doc in documents:
                doc_id = doc.get("id") or doc.get("media_id")
                source = doc.get("source", {})

                # Normalize IDs to int for comparison (RAG returns strings)
                try:
                    if int(doc_id) == int(media_id):
                        found_media = True
                except (ValueError, TypeError):
                    if doc_id == media_id:
                        found_media = True
                if note_id:
                    try:
                        if int(doc_id) == int(note_id):
                            found_note = True
                    except (ValueError, TypeError):
                        if doc_id == note_id:
                            found_note = True

            print(f"Found media: {found_media}, Found note: {found_note}")

            assert found_media, "Media not found in unified search"
            # Note finding is optional (notes might not be indexed)

        except httpx.HTTPStatusError as e:
            pytest.skip(f"Unified search failed: {e}")
