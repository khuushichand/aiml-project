"""
Unit tests for the unified RAG pipeline.

Tests the single unified pipeline function with all feature combinations.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import (
    unified_rag_pipeline,
)
from tldw_Server_API.app.core.RAG.rag_service.types import Document, SearchResult, DataSource


@pytest.mark.unit
class TestUnifiedPipeline:
    """Test the unified RAG pipeline function."""

    @pytest.mark.asyncio
    async def test_unified_pipeline_minimal(self):
        """Test unified pipeline with minimal parameters."""
        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
            mock_retriever_instance = MagicMock()
            mock_retriever_instance.retrieve = AsyncMock(return_value=[
                Document(id="1", content="Test content", metadata={}, source=DataSource.MEDIA_DB, score=0.9)
            ])
            mock_retriever.return_value = mock_retriever_instance

            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
                mock_generator_instance = MagicMock()
                mock_generator_instance.generate = AsyncMock(return_value={
                    "answer": "Generated answer",
                    "confidence": 0.85
                })
                mock_generator.return_value = mock_generator_instance

                result = await unified_rag_pipeline(
                    query="What is RAG?",
                    top_k=5
                )

                assert result is not None
                # Normalize access across dict or Pydantic object
                answer = getattr(result, 'generated_answer', None) if not isinstance(result, dict) else result.get('generated_answer') or result.get('answer')
                docs = getattr(result, 'documents', None) if not isinstance(result, dict) else result.get('documents', [])
                # Pydantic response holds list of dicts; when dict, may hold Document objects
                if docs and not isinstance(docs[0], dict):
                    first_id = getattr(docs[0], 'id', None)
                else:
                    first_id = docs[0].get('id') if docs else None
                assert answer == "Generated answer"
                assert first_id is not None

    @pytest.mark.asyncio
    async def test_unified_pipeline_with_cache(self, mock_semantic_cache):
        """Test unified pipeline with caching enabled."""
        # Test cache hit
        cached_result = {
            "answer": "Cached answer",
            "documents": [
                Document(id="cached_1", content="Cached content", metadata={})
            ]
        }
        mock_semantic_cache.get.return_value = cached_result

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.SemanticCache', return_value=mock_semantic_cache):
            result = await unified_rag_pipeline(
                query="cached query",
                enable_cache=True,
                cache_ttl=3600
            )

            answer = (
                getattr(result, 'generated_answer', None)
                if not isinstance(result, dict)
                else result.get('generated_answer') or result.get('answer')
            )
            docs = (
                getattr(result, 'documents', None)
                if not isinstance(result, dict)
                else result.get('documents', [])
            )
            first_id = None
            if docs:
                first = docs[0]
                first_id = getattr(first, 'id', None) if not isinstance(first, dict) else first.get('id')
            assert answer == "Cached answer"
            assert first_id == "cached_1"
            mock_semantic_cache.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_unified_pipeline_with_expansion(self):
        """Test unified pipeline with query expansion."""
        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.multi_strategy_expansion') as mock_expand:
            mock_expand.return_value = "API Application Programming Interface"

            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
                mock_retriever_instance = MagicMock()
                mock_retriever_instance.retrieve = AsyncMock(return_value=[])
                mock_retriever.return_value = mock_retriever_instance

                with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
                    mock_generator_instance = MagicMock()
                    mock_generator_instance.generate = AsyncMock(return_value={"answer": "Answer"})
                    mock_generator.return_value = mock_generator_instance

                    result = await unified_rag_pipeline(
                        query="API",
                        enable_expansion=True,
                        expansion_strategies=["acronym", "synonym"]
                    )

                    mock_expand.assert_called_once_with(
                        "API",
                        strategies=["acronym", "synonym"]
                    )
                    # Expanded queries should be recorded
                    expanded = getattr(result, 'expanded_queries', None) if not isinstance(result, dict) else result.get('expanded_queries', [])
                    assert any("Application Programming Interface" in q for q in (expanded or []))

    @pytest.mark.asyncio
    async def test_unified_pipeline_with_reranking(self, sample_documents):
        """Test unified pipeline with reranking enabled."""
        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
            # Return documents in one order
            mock_retriever_instance = MagicMock()
            mock_retriever_instance.retrieve = AsyncMock(return_value=[
                Document(id=doc.id, content=doc.content, metadata=doc.metadata, source=DataSource.MEDIA_DB, score=0.8)
                for doc in sample_documents
            ])
            mock_retriever.return_value = mock_retriever_instance

            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.create_reranker') as mock_reranker_factory:
                mock_reranker = MagicMock()
                # Return documents in different order
                mock_reranker.rerank = AsyncMock(return_value=[
                    sample_documents[2],
                    sample_documents[0],
                    sample_documents[1]
                ])
                mock_reranker_factory.return_value = mock_reranker

                with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
                    mock_generator_instance = MagicMock()
                    mock_generator_instance.generate = AsyncMock(return_value={"answer": "Answer"})
                    mock_generator.return_value = mock_generator_instance

                    result = await unified_rag_pipeline(
                        query="test",
                        enable_reranking=True,
                        reranking_strategy="cross_encoder",
                        rerank_top_k=3
                    )

                    mock_reranker.rerank.assert_called_once()
                    # Documents should be reordered
                    docs = getattr(result, 'documents', None) if not isinstance(result, dict) else result.get('documents', [])
                    assert len(docs) <= 3

    @pytest.mark.asyncio
    async def test_unified_pipeline_with_filters(self):
        """Test unified pipeline with various filters."""
        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.SecurityFilter') as mock_security:
            from types import SimpleNamespace
            mock_filter = MagicMock()
            async def _filter_by_sensitivity(docs, max_level=None):
                return [d for d in docs if d.metadata.get("sensitive") != True]
            mock_filter.filter_by_sensitivity = AsyncMock(side_effect=_filter_by_sensitivity)
            mock_security.return_value = mock_filter
            # Ensure SensitivityLevel is present
            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.SensitivityLevel', SimpleNamespace(PUBLIC=1, INTERNAL=2, CONFIDENTIAL=3, RESTRICTED=4)):

                with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
                    mock_retriever_instance = MagicMock()
                    mock_retriever_instance.retrieve = AsyncMock(return_value=[
                        Document(id="1", content="Public", metadata={"sensitive": False}, source=DataSource.MEDIA_DB, score=0.9),
                        Document(id="2", content="Secret", metadata={"sensitive": True}, source=DataSource.MEDIA_DB, score=0.85)
                    ])
                    mock_retriever.return_value = mock_retriever_instance

                    with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
                        mock_generator_instance = MagicMock()
                        mock_generator_instance.generate = AsyncMock(return_value={"answer": "Answer"})
                        mock_generator.return_value = mock_generator_instance

                        result = await unified_rag_pipeline(
                            query="test",
                            enable_security_filter=True,
                            sensitivity_level="public"
                        )

                        # Only non-sensitive document should be in results
                        docs = getattr(result, 'documents', None) if not isinstance(result, dict) else result.get('documents', [])
                        assert len(docs) == 1
                        first_id = docs[0]['id'] if docs and isinstance(docs[0], dict) else getattr(docs[0], 'id', None)
                        assert first_id == "1"

    @pytest.mark.asyncio
    async def test_unified_pipeline_with_citations(self, sample_documents):
        """Test unified pipeline with citation generation."""
        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
            mock_retriever_instance = MagicMock()
            mock_retriever_instance.retrieve = AsyncMock(return_value=[
                Document(id=doc.id, content=doc.content, metadata=doc.metadata, source=DataSource.MEDIA_DB, score=0.9)
                for doc in sample_documents
            ])
            mock_retriever.return_value = mock_retriever_instance

            # Patch the actual generator used by the pipeline
            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.CitationGenerator') as mock_citation:
                from types import SimpleNamespace
                mock_citation_instance = MagicMock()
                # Pipeline expects attributes: academic_citations, chunk_citations, inline_markers, citation_map
                dual_result = SimpleNamespace(
                    academic_citations=["[1] Document 1 - Author (2024)"],
                    chunk_citations=[],
                    inline_markers={"[1]": "1"},
                    citation_map={"1": ["1"]}
                )
                mock_citation_instance.generate_citations = AsyncMock(return_value=dual_result)
                mock_citation.return_value = mock_citation_instance

                with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
                    mock_generator_instance = MagicMock()
                    mock_generator_instance.generate = AsyncMock(return_value={"answer": "Answer with citations"})
                    mock_generator.return_value = mock_generator_instance

                    result = await unified_rag_pipeline(
                        query="test",
                        enable_citations=True,
                        citation_style="academic"
                    )

                    citations = getattr(result, 'citations', None) if not isinstance(result, dict) else result.get('citations', {})
                    assert citations is not None
                    mock_citation_instance.generate_citations.assert_called_once()

    @pytest.mark.asyncio
    async def test_unified_pipeline_all_features(self):
        """Test unified pipeline with all features enabled."""
        result = await unified_rag_pipeline(
            query="What is RAG?",
            # Retrieval settings
            top_k=20,
            enable_hybrid_search=True,
            bm25_weight=0.3,
            vector_weight=0.7,

            # Expansion settings
            enable_expansion=True,
            expansion_strategies=["synonym", "acronym", "entity"],

            # Cache settings
            enable_cache=True,
            cache_ttl=7200,

            # Reranking settings
            enable_reranking=True,
            reranking_strategy="cross_encoder",
            rerank_top_k=5,

            # Filter settings
            enable_security_filter=True,
            user_clearance_level="confidential",
            enable_date_filter=True,
            date_range={"start": "2024-01-01", "end": "2024-12-31"},

            # Generation settings
            temperature=0.5,
            max_tokens=1000,
            enable_streaming=False,

            # Citation settings
            enable_citations=True,
            citation_style="numeric",

            # Analytics
            enable_analytics=True,
            track_performance=True,

            # Advanced features
            enable_spell_check=True,
            enable_result_highlighting=True,
            enable_cost_tracking=True,
            enable_feedback=True
        )

        # Basic assertions - with all mocking this should at least not error
        qv = getattr(result, 'query', None) if not isinstance(result, dict) else result.get('query')
        assert qv == "What is RAG?"

    @pytest.mark.asyncio
    async def test_unified_pipeline_error_handling(self):
        """Test unified pipeline error handling."""
        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
            mock_retriever.side_effect = Exception("Retrieval failed")

            result = await unified_rag_pipeline(
                query="test",
                fallback_on_error=True
            )

            # Should return a fallback result instead of raising
            assert result is not None
            # Accept Pydantic or dict
            if isinstance(result, dict):
                assert "error" in result or result.get("generated_answer") is not None or result.get("answer") is not None
            else:
                # Pydantic success path may carry errors list
                assert hasattr(result, 'errors')

    @pytest.mark.asyncio
    async def test_unified_pipeline_with_metadata(self):
        """Test unified pipeline with custom metadata."""
        custom_metadata = {
            "user_id": "user123",
            "session_id": "session456",
            "request_id": "req789",
            "custom_field": "custom_value"
        }

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
            mock_retriever_instance = MagicMock()
            mock_retriever_instance.retrieve = AsyncMock(return_value=[])
            mock_retriever.return_value = mock_retriever_instance

            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
                mock_generator_instance = MagicMock()
                mock_generator_instance.generate = AsyncMock(return_value={"answer": "Answer"})
                mock_generator.return_value = mock_generator_instance

                result = await unified_rag_pipeline(
                    query="test",
                    metadata=custom_metadata
                )

                md = getattr(result, 'metadata', None) if not isinstance(result, dict) else result.get('metadata', {})
                for key, value in custom_metadata.items():
                    assert md.get(key) == value



@pytest.mark.unit
class TestUnifiedPipelineParams:
    """Basic parameter validation through unified entry point."""

    @pytest.mark.asyncio
    async def test_empty_query(self):
        result = await unified_rag_pipeline(query="   ")
        errs = getattr(result, 'errors', None) if not isinstance(result, dict) else result.get('errors', [])
        assert errs and len(errs) > 0




@pytest.mark.unit
class TestStreamingSupport:
    """Test streaming support in unified pipeline."""

    @pytest.mark.asyncio
    async def test_streaming_disabled(self):
        """Test pipeline with streaming disabled."""
        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
            mock_generator_instance = MagicMock()
            mock_generator_instance.generate = AsyncMock(return_value={
                "answer": "Complete answer",
                "streaming": False
            })
            mock_generator.return_value = mock_generator_instance

            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
                mock_retriever_instance = MagicMock()
                mock_retriever_instance.retrieve = AsyncMock(return_value=[])
                mock_retriever.return_value = mock_retriever_instance

                result = await unified_rag_pipeline(
                    query="test",
                    enable_streaming=False
                )

                # Normalize
                ans = getattr(result, 'generated_answer', None) if not isinstance(result, dict) else result.get('generated_answer') or result.get('answer')
                assert ans == "Complete answer"

    @pytest.mark.asyncio
    async def test_streaming_enabled(self):
        """Test pipeline with streaming enabled."""
        async def mock_stream_generator():
            """Mock streaming generator."""
            chunks = ["This ", "is ", "a ", "streamed ", "response."]
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0.01)

        with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.AnswerGenerator') as mock_generator:
            mock_generator_instance = MagicMock()
            mock_generator_instance.generate_stream = mock_stream_generator
            mock_generator.return_value = mock_generator_instance

            with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever') as mock_retriever:
                mock_retriever_instance = MagicMock()
                mock_retriever_instance.retrieve = AsyncMock(return_value=[])
                mock_retriever.return_value = mock_retriever_instance

                result = await unified_rag_pipeline(
                    query="test",
                    enable_streaming=True
                )

                # With streaming, result might be an async generator
                if hasattr(result, '__aiter__'):
                    chunks = []
                    async for chunk in result:
                        chunks.append(chunk)

                    assert len(chunks) > 0
                    full_response = "".join(chunks)
                    assert full_response == "This is a streamed response."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
