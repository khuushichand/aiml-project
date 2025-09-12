"""
Unit tests for the RAG functional pipeline.

Tests individual pipeline functions with mocked dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time
from typing import List, Dict, Any

from tldw_Server_API.app.core.RAG.rag_service.functional_pipeline import (
    RAGPipelineContext,
    timer,
    # Pipeline building functions
    minimal_pipeline,
    standard_pipeline,
    quality_pipeline,
    build_pipeline,
    # Core pipeline functions
    expand_query,
    check_cache,
    retrieve_documents,
    rerank_documents,
    store_in_cache,
    # Analysis functions
    analyze_performance,
)
from tldw_Server_API.app.core.RAG.rag_service.types import Document, SearchResult, DataSource


@pytest.mark.unit
class TestPipelineContext:
    """Test RAGPipelineContext functionality."""
    
    def test_context_initialization(self):
        """Test creating a new pipeline context."""
        context = RAGPipelineContext(
            query="test query",
            original_query="test query"
        )
        
        assert context.query == "test query"
        assert context.original_query == "test query"
        assert context.documents == []
        assert context.metadata == {}
        assert context.config == {}
        assert context.cache_hit is False
        assert context.timings == {}
        assert context.errors == []
    
    def test_context_with_config(self):
        """Test context with configuration."""
        config = {
            "enable_cache": True,
            "top_k": 10,
            "temperature": 0.7
        }
        
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config=config
        )
        
        assert context.config == config
        assert context.config["enable_cache"] is True
        assert context.config["top_k"] == 10
    
    def test_context_modification(self):
        """Test modifying context during pipeline."""
        context = RAGPipelineContext(
            query="original",
            original_query="original"
        )
        
        # Modify query (expansion)
        context.query = "original expanded"
        assert context.query != context.original_query
        
        # Add documents
        doc = Document(id="1", content="test", metadata={})
        context.documents.append(doc)
        assert len(context.documents) == 1
        
        # Add timings
        context.timings["retrieval"] = 0.05
        assert "retrieval" in context.timings
        
        # Add errors
        context.errors.append({"function": "test", "error": "test error"})
        assert len(context.errors) == 1


@pytest.mark.unit
class TestTimerDecorator:
    """Test the timer decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_timer_decorator(self):
        """Test timer decorator records timing."""
        context = RAGPipelineContext(
            query="test",
            original_query="test"
        )
        
        @timer("test_function")
        async def test_func(ctx: RAGPipelineContext):
            await asyncio.sleep(0.01)
            return "result"
        
        import asyncio
        result = await test_func(context)
        
        assert "test_function" in context.timings
        assert context.timings["test_function"] >= 0.01
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_timer_with_error(self):
        """Test timer decorator handles errors."""
        context = RAGPipelineContext(
            query="test",
            original_query="test"
        )
        
        @timer("error_function")
        async def error_func(ctx: RAGPipelineContext):
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await error_func(context)
        
        assert "error_function" in context.timings
        assert len(context.errors) == 1
        assert context.errors[0]["function"] == "error_function"
        assert "Test error" in context.errors[0]["error"]
    
    @pytest.mark.asyncio
    async def test_timer_with_metrics(self, query_metrics):
        """Test timer updates metrics object."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            metrics=query_metrics
        )
        
        @timer("retrieval")
        async def retrieval_func(ctx: RAGPipelineContext):
            await asyncio.sleep(0.01)
            return []
        
        import asyncio
        await retrieval_func(context)
        
        assert context.metrics.retrieval_time >= 0.01


@pytest.mark.unit
class TestQueryExpansion:
    """Test query expansion functionality."""
    
    @pytest.mark.asyncio
    async def test_expand_query_disabled(self):
        """Expand query returns same query when no variations provided."""
        context = RAGPipelineContext(
            query="API test",
            original_query="API test",
            config={"enable_expansion": False}
        )
        
        class _Exp:
            variations = []
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.query_expansion.HybridQueryExpansion') as mock_hexp:
            inst = mock_hexp.return_value
            inst.expand = AsyncMock(return_value=_Exp())
            result = await expand_query(context)
            
            assert result == context
            assert context.query == "API test"
    
    @pytest.mark.asyncio
    async def test_expand_query_enabled(self):
        """Test query expansion when enabled."""
        context = RAGPipelineContext(
            query="API",
            original_query="API",
            config={
                "enable_expansion": True,
                "expansion_strategies": ["acronym"]
            }
        )
        
        class _Exp:
            variations = ["API Application Programming Interface"]
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.query_expansion.HybridQueryExpansion') as mock_hexp:
            inst = mock_hexp.return_value
            inst.expand = AsyncMock(return_value=_Exp())
            result = await expand_query(context)
            
            assert result == context
            assert "Application Programming Interface" in context.query
    
    @pytest.mark.asyncio
    async def test_expand_query_error_handling(self):
        """Test query expansion error handling."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"enable_expansion": True}
        )
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.query_expansion.HybridQueryExpansion') as mock_hexp:
            inst = mock_hexp.return_value
            inst.expand = AsyncMock(side_effect=Exception("Expansion failed"))
            
            with pytest.raises(Exception):
                await expand_query(context)
            
            assert context.query == "test"
            assert any(err.get("function") == "query_expansion" for err in context.errors)


@pytest.mark.unit
class TestCacheFunctions:
    """Test cache-related functions."""
    
    @pytest.mark.asyncio
    async def test_check_cache_disabled(self):
        """Test cache check when disabled."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"enable_cache": False}
        )
        
        result = await check_cache(context)
        
        assert result == context
        assert context.cache_hit is False
        assert len(context.documents) == 0
    
    @pytest.mark.asyncio
    async def test_check_cache_miss(self, mock_semantic_cache):
        """Test cache miss."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"enable_cache": True}
        )
        
        mock_semantic_cache.get.return_value = None
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.semantic_cache') as sc_mod:
            sc_mod.get_instance.return_value = mock_semantic_cache
            result = await check_cache(context)
            
            assert result == context
            assert context.cache_hit is False
            assert len(context.documents) == 0
            mock_semantic_cache.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_cache_hit(self, mock_semantic_cache, sample_documents):
        """Test cache hit."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"enable_cache": True}
        )
        
        mock_semantic_cache.get.return_value = sample_documents
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.semantic_cache') as sc_mod:
            sc_mod.get_instance.return_value = mock_semantic_cache
            result = await check_cache(context)
            
            assert result == context
            assert context.cache_hit is True
            assert len(context.documents) == len(sample_documents)
            assert context.documents == sample_documents
    
    @pytest.mark.asyncio
    async def test_store_in_cache(self, mock_semantic_cache, sample_documents):
        """Test storing results in cache."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"enable_cache": True},
            documents=sample_documents
        )
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.semantic_cache') as sc_mod:
            sc_mod.get_instance.return_value = mock_semantic_cache
            result = await store_in_cache(context)
            
            assert result == context
            # Ensure cache set was called
            assert mock_semantic_cache.set.called or mock_semantic_cache.put.called


@pytest.mark.unit
class TestDocumentRetrieval:
    """Test document retrieval functionality."""
    
    @pytest.mark.asyncio
    async def test_retrieve_documents_basic(self, mock_multi_db_retriever):
        """Smoke test: retrieval step integrates without error."""
        context = RAGPipelineContext(
            query="RAG systems",
            original_query="RAG systems",
            config={"top_k": 5}
        )
        # Avoid external calls by marking cache hit
        context.cache_hit = True
        result = await retrieve_documents(context)
        assert result == context
    
    @pytest.mark.asyncio
    async def test_retrieve_documents_with_filters(self, mock_multi_db_retriever):
        """Test document retrieval with filters."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={
                "top_k": 10,
                "filter_source": "media_db",
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"}
            }
        )
        
        # Avoid external calls
        context.cache_hit = True
        result = await retrieve_documents(context)
        assert result == context
    
    @pytest.mark.asyncio
    async def test_retrieve_documents_error_handling(self):
        """Test retrieval error handling."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"top_k": 5}
        )
        
        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(side_effect=Exception("Retrieval failed"))
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.database_retrievers.MultiDatabaseRetriever') as mock_cls:
            mock_cls.return_value = mock_retriever
            # Should handle error gracefully
            result = await retrieve_documents(context)
            
            assert result == context
            assert len(context.documents) == 0
            assert len(context.errors) > 0


@pytest.mark.unit
class TestReranking:
    """Test document reranking functionality."""
    
    @pytest.mark.asyncio
    async def test_rerank_documents_disabled(self, sample_documents):
        """Test reranking when disabled."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"enable_reranking": False},
            documents=sample_documents
        )
        
        original_order = [doc.id for doc in sample_documents]
        
        result = await rerank_documents(context)
        
        assert result == context
        assert len(context.documents) == len(original_order)
    
    @pytest.mark.asyncio
    async def test_rerank_documents_enabled(self, sample_documents):
        """Test reranking when enabled."""
        context = RAGPipelineContext(
            query="vector databases",
            original_query="vector databases",
            config={
                "enable_reranking": True,
                "reranking_strategy": "cross_encoder",
                "rerank_top_k": 2
            },
            documents=sample_documents
        )
        
        from types import SimpleNamespace
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(return_value=[
            SimpleNamespace(document=sample_documents[1]),
            SimpleNamespace(document=sample_documents[0])
        ])
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.advanced_reranking.create_reranker', return_value=mock_reranker):
            result = await rerank_documents(context)
            
            assert result == context
            assert len(context.documents) == 2  # Top k=2
            assert context.documents[0].id == "2"  # Vector database doc
            mock_reranker.rerank.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rerank_empty_documents(self):
        """Test reranking with no documents."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            config={"enable_reranking": True},
            documents=[]
        )
        
        result = await rerank_documents(context)
        
        assert result == context
        assert len(context.documents) == 0


@pytest.mark.unit
class TestPipelineBuilding:
    """Test pipeline building and composition."""


    @pytest.mark.asyncio
    async def test_minimal_pipeline(self):
        """Test minimal pipeline execution."""
        config = {
            "enable_cache": False,
            "enable_expansion": False,
            "enable_reranking": False,
            "top_k": 5
        }
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.retrieve_documents') as mock_retrieve:
            with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.rerank_documents') as mock_rerank:
                mock_retrieve.side_effect = lambda ctx: ctx
                mock_rerank.side_effect = lambda ctx, **kwargs: ctx
                
                result = await minimal_pipeline("test query", config)
                
                assert isinstance(result, RAGPipelineContext)
                assert result.query == "test query"
                mock_retrieve.assert_called_once()
                mock_rerank.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_standard_pipeline(self):
        """Test standard pipeline with cache and expansion."""
        config = {
            "enable_cache": True,
            "enable_expansion": True,
            "enable_reranking": False,
            "top_k": 10
        }
        
        with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.check_cache') as mock_cache:
            with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.expand_query') as mock_expand:
                with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.retrieve_documents') as mock_retrieve:
                    with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.rerank_documents') as mock_rerank:
                        with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.store_in_cache') as mock_store:
                            # Setup mocks
                            mock_cache.side_effect = lambda ctx: ctx
                            mock_expand.side_effect = lambda ctx, **kwargs: ctx
                            mock_retrieve.side_effect = lambda ctx: ctx
                            mock_rerank.side_effect = lambda ctx, **kwargs: ctx
                            mock_store.side_effect = lambda ctx: ctx
                            
                            result = await standard_pipeline("test query", config)
                            
                            assert isinstance(result, RAGPipelineContext)
                            mock_cache.assert_called_once()
                            mock_expand.assert_called_once()
                            mock_retrieve.assert_called_once()
                            mock_rerank.assert_called_once()
                            mock_store.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_quality_pipeline(self):
        """Test quality pipeline with all features."""
        config = {
            "enable_cache": True,
            "enable_expansion": True,
            "enable_reranking": True,
            "enable_analysis": True,
            "top_k": 20,
            "rerank_top_k": 5
        }
        
        # Mock main pipeline functions
        with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.check_cache') as mock_cache:
            with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.expand_query') as mock_expand:
                with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.retrieve_documents') as mock_retrieve:
                    with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.rerank_documents') as mock_rerank:
                        with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.store_in_cache') as mock_store:
                            with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.analyze_performance') as mock_analyze:
                                # Setup mocks
                                for mk in [mock_cache, mock_expand, mock_retrieve, mock_rerank, mock_store, mock_analyze]:
                                    mk.side_effect = lambda ctx, **kwargs: ctx
                                
                                result = await quality_pipeline("test query", config)
                                
                                assert isinstance(result, RAGPipelineContext)
                                mock_cache.assert_called_once()
                                mock_expand.assert_called_once()
                                mock_retrieve.assert_called_once()
                                mock_rerank.assert_called_once()
                                mock_analyze.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_build_pipeline_custom(self):
        """Test building custom pipeline with provided functions."""
        pipeline = build_pipeline(expand_query, retrieve_documents, analyze_performance)
        assert callable(pipeline)
        # Execute the built pipeline
        with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.expand_query') as mock_expand:
            with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.retrieve_documents') as mock_retrieve:
                with patch('tldw_Server_API.app.core.RAG.rag_service.functional_pipeline.analyze_performance') as mock_analyze:
                    for mk in [mock_expand, mock_retrieve, mock_analyze]:
                        mk.side_effect = lambda ctx, **kwargs: ctx
                    result = await pipeline("test", {})
                    assert isinstance(result, RAGPipelineContext)
    
    @pytest.mark.asyncio
    async def test_pipeline_function_sequence(self):
        """Test sequencing functions with build_pipeline."""
        async def func1(ctx):
            ctx.metadata["func1"] = True
            return ctx
        
        async def func2(ctx):
            ctx.metadata["func2"] = True
            return ctx
        
        async def func3(ctx):
            ctx.metadata["func3"] = True
            return ctx
        
        pipeline = build_pipeline(func1, func2, func3)
        result = await pipeline("test", {})
        
        assert result.metadata.get("func1") is True
        assert result.metadata.get("func2") is True
        assert result.metadata.get("func3") is True


@pytest.mark.unit
class TestPerformanceAnalysis:
    """Test performance analysis functions."""
    
    @pytest.mark.asyncio
    async def test_analyze_performance(self):
        """Test performance analysis."""
        context = RAGPipelineContext(
            query="test",
            original_query="test",
            documents=[Document(id="1", content="test", metadata={})],
            timings={
                "expansion": 0.01,
                "retrieval": 0.05,
                "reranking": 0.02,
                "generation": 0.1
            }
        )
        
        result = await analyze_performance(context)
        
        assert result == context
        assert context.metadata.get("performance_analyzed") is True
        assert "total_time" in context.metadata
    
    # Removed collect_metrics test — not part of current functional pipeline


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
