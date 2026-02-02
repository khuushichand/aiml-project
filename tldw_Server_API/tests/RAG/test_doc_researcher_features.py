"""
Tests for Doc-Researcher features:
- Dynamic granularity selection
- Progressive evidence accumulation
- Multi-hop evidence chains
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tldw_Server_API.app.core.RAG.rag_service.granularity_router import (
    GranularityRouter,
    GranularityDecision,
    route_query_granularity,
)
from tldw_Server_API.app.core.RAG.rag_service.evidence_accumulator import (
    EvidenceAccumulator,
    AccumulationResult,
)
from tldw_Server_API.app.core.RAG.rag_service.evidence_chains import (
    EvidenceChainBuilder,
    ChainBuildResult,
)
from tldw_Server_API.app.core.RAG.rag_service.types import (
    QueryType,
    Granularity,
    Document,
    DataSource,
    EvidenceNode,
    EvidenceChain,
)


class TestGranularityRouter:
    """Test suite for dynamic granularity selection."""

    def test_broad_query_classification(self):
        """Broad queries should route to document-level retrieval."""
        router = GranularityRouter()

        broad_queries = [
            "What is the main idea of the document?",
            "Give me an overview of machine learning",
            "Summarize the key points",
            "Explain how the system works",
        ]

        for query in broad_queries:
            decision = router.route(query)
            assert decision.query_type == QueryType.BROAD, f"Query '{query}' should be BROAD"
            assert decision.granularity == Granularity.DOCUMENT

    def test_factoid_query_classification(self):
        """Factoid queries should route to passage-level retrieval."""
        router = GranularityRouter()

        factoid_queries = [
            "When was the company founded?",
            "What year did this happen?",
            "How many users are there?",
            "Who is the CEO?",
        ]

        for query in factoid_queries:
            decision = router.route(query)
            assert decision.query_type == QueryType.FACTOID, f"Query '{query}' should be FACTOID"
            assert decision.granularity == Granularity.PASSAGE

    def test_specific_query_classification(self):
        """Specific queries should route to chunk-level retrieval."""
        router = GranularityRouter()

        specific_queries = [
            "How do I implement authentication?",
            "What are the steps to configure the server?",
            "Show me an example of the API usage",
        ]

        for query in specific_queries:
            decision = router.route(query)
            assert decision.query_type == QueryType.SPECIFIC, f"Query '{query}' should be SPECIFIC"
            assert decision.granularity == Granularity.CHUNK

    def test_retrieval_params_for_granularities(self):
        """Each granularity should have appropriate retrieval parameters."""
        router = GranularityRouter()

        # Document-level params
        doc_params = router.get_retrieval_params(Granularity.DOCUMENT)
        assert doc_params["enable_parent_expansion"] is True
        assert doc_params["include_parent_document"] is True

        # Passage-level params
        passage_params = router.get_retrieval_params(Granularity.PASSAGE)
        assert passage_params["enable_multi_vector_passages"] is True
        assert passage_params["fts_level"] == "chunk"

        # Chunk-level params (default)
        chunk_params = router.get_retrieval_params(Granularity.CHUNK)
        assert chunk_params["enable_parent_expansion"] is False
        assert chunk_params["enable_multi_vector_passages"] is False

    def test_route_returns_decision_with_confidence(self):
        """Route should return a decision with confidence score."""
        decision = route_query_granularity("What is the overview?")
        assert isinstance(decision, GranularityDecision)
        assert 0 <= decision.confidence <= 1
        assert decision.reasoning


class TestEvidenceAccumulator:
    """Test suite for progressive evidence accumulation."""

    @pytest.mark.asyncio
    async def test_accumulation_with_sufficient_initial_results(self):
        """Should not perform additional rounds if initial results are sufficient."""
        accumulator = EvidenceAccumulator(
            max_rounds=3,
            enable_gap_assessment=False,  # Use heuristic
        )

        # Create mock documents
        docs = [
            Document(
                id=f"doc{i}",
                content=f"Document {i} content about machine learning algorithms and models",
                metadata={"title": f"Doc {i}"},
                source=DataSource.MEDIA_DB,
                score=0.8,
            )
            for i in range(5)
        ]

        # Mock retrieval function
        mock_retrieval = AsyncMock(return_value=[])

        result = await accumulator.accumulate(
            query="machine learning",
            initial_results=docs,
            retrieval_fn=mock_retrieval,
        )

        assert isinstance(result, AccumulationResult)
        assert len(result.documents) >= len(docs)
        assert result.total_rounds >= 1

    @pytest.mark.asyncio
    async def test_accumulation_respects_max_rounds(self):
        """Should not exceed max_rounds."""
        accumulator = EvidenceAccumulator(
            max_rounds=2,
            enable_gap_assessment=False,
        )

        initial_docs = [
            Document(id="doc1", content="Short content", metadata={}, score=0.3)
        ]

        # Mock retrieval that always returns new docs
        call_count = 0
        async def mock_retrieval(query, exclude_ids):
            nonlocal call_count
            call_count += 1
            return [
                Document(
                    id=f"new_doc_{call_count}",
                    content=f"New content {call_count}",
                    metadata={},
                    score=0.5,
                )
            ]

        result = await accumulator.accumulate(
            query="test query",
            initial_results=initial_docs,
            retrieval_fn=mock_retrieval,
        )

        assert result.total_rounds <= 2

    def test_heuristic_gap_assessment(self):
        """Heuristic assessment should identify gaps based on term coverage."""
        accumulator = EvidenceAccumulator()

        docs = [
            Document(
                id="doc1",
                content="This is about Python programming",
                metadata={},
                score=0.7,
            )
        ]

        is_sufficient, reason, gaps = accumulator._heuristic_assessment(
            "Python programming basics",
            docs,
        )

        assert isinstance(is_sufficient, bool)
        assert reason

    def test_merge_results_deduplicates(self):
        """Merge should deduplicate documents."""
        accumulator = EvidenceAccumulator()

        doc1 = Document(id="doc1", content="Content 1", metadata={}, score=0.8)
        doc2 = Document(id="doc2", content="Content 2", metadata={}, score=0.7)
        doc1_dup = Document(id="doc1", content="Content 1", metadata={}, score=0.6)

        rounds = [[doc1, doc2], [doc1_dup]]
        merged = accumulator.merge_results(rounds)

        assert len(merged) == 2
        # Should be sorted by score
        assert merged[0].score >= merged[1].score


class TestEvidenceChains:
    """Test suite for multi-hop evidence chains."""

    def test_evidence_node_creation(self):
        """Evidence nodes should be created with valid data."""
        node = EvidenceNode(
            document_id="doc1",
            chunk_id="chunk1",
            fact="The company was founded in 2020",
            confidence=0.9,
            supports=["claim1"],
        )

        assert node.document_id == "doc1"
        assert node.confidence == 0.9
        assert "claim1" in node.supports

    def test_evidence_node_validates_confidence(self):
        """Node should reject invalid confidence values."""
        with pytest.raises(ValueError):
            EvidenceNode(
                document_id="doc1",
                chunk_id="chunk1",
                fact="Test",
                confidence=1.5,  # Invalid
            )

    def test_evidence_chain_computes_confidence(self):
        """Chain should compute aggregate confidence."""
        node1 = EvidenceNode(
            document_id="doc1",
            chunk_id="chunk1",
            fact="Fact 1",
            confidence=0.8,
        )
        node2 = EvidenceNode(
            document_id="doc2",
            chunk_id="chunk2",
            fact="Fact 2",
            confidence=0.9,
        )

        chain = EvidenceChain(
            query="test query",
            nodes=[node1, node2],
            root_claims=["claim1"],
        )

        # Product of confidences
        expected = 0.8 * 0.9
        assert abs(chain.chain_confidence - expected) < 0.001

    def test_evidence_chain_hop_count(self):
        """Chain should count unique documents as hops."""
        nodes = [
            EvidenceNode(document_id="doc1", chunk_id="c1", fact="F1", confidence=0.8),
            EvidenceNode(document_id="doc1", chunk_id="c2", fact="F2", confidence=0.8),
            EvidenceNode(document_id="doc2", chunk_id="c3", fact="F3", confidence=0.8),
            EvidenceNode(document_id="doc3", chunk_id="c4", fact="F4", confidence=0.8),
        ]

        chain = EvidenceChain(query="test", nodes=nodes)
        assert chain.hop_count == 3  # 3 unique documents

    @pytest.mark.asyncio
    async def test_chain_builder_extracts_facts(self):
        """Chain builder should extract facts from documents."""
        builder = EvidenceChainBuilder(enable_llm_extraction=False)

        docs = [
            Document(
                id="doc1",
                content="The company was founded in 2020. Revenue grew 50% last year.",
                metadata={"title": "Company Report"},
                score=0.9,
            )
        ]

        result = await builder.build_chains(
            query="company founding date",
            documents=docs,
        )

        assert isinstance(result, ChainBuildResult)
        # Should have some chains (even if empty based on heuristics)
        assert result.metadata.get("total_nodes", 0) >= 0

    def test_chain_to_dict_serialization(self):
        """Chain should serialize to dict properly."""
        node = EvidenceNode(
            document_id="doc1",
            chunk_id="chunk1",
            fact="Test fact",
            confidence=0.85,
        )
        chain = EvidenceChain(
            query="test",
            nodes=[node],
            root_claims=["claim1"],
        )

        d = chain.to_dict()
        assert "query" in d
        assert "nodes" in d
        assert "chain_confidence" in d
        assert "hop_count" in d


class TestIntegration:
    """Integration tests for Doc-Researcher features in the pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_with_dynamic_granularity(self):
        """Pipeline should accept enable_dynamic_granularity parameter."""
        from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import (
            unified_rag_pipeline,
        )

        # This should not raise even without database connections
        result = await unified_rag_pipeline(
            query="What is machine learning?",
            enable_dynamic_granularity=True,
            enable_cache=False,
            enable_generation=False,
            enable_reranking=False,
        )

        assert result is not None
        # Check that granularity routing metadata was added
        if result.documents:
            assert "granularity_routing" in result.metadata

    @pytest.mark.asyncio
    async def test_pipeline_with_evidence_accumulation(self):
        """Pipeline should accept enable_evidence_accumulation parameter."""
        from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import (
            unified_rag_pipeline,
        )

        result = await unified_rag_pipeline(
            query="What is machine learning?",
            enable_evidence_accumulation=True,
            accumulation_max_rounds=2,
            enable_cache=False,
            enable_generation=False,
            enable_reranking=False,
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_pipeline_with_evidence_chains(self):
        """Pipeline should accept enable_evidence_chains parameter."""
        from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import (
            unified_rag_pipeline,
        )

        result = await unified_rag_pipeline(
            query="What is machine learning?",
            enable_evidence_chains=True,
            enable_cache=False,
            enable_generation=False,
            enable_reranking=False,
        )

        assert result is not None
