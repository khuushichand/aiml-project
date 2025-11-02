"""
Unit tests for the Embedding Worker.

Tests the embedding generation worker with minimal mocking - only external
services like HuggingFace or OpenAI APIs are mocked.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import numpy as np
import asyncio
from typing import List, Dict, Any

from tldw_Server_API.app.core.Embeddings.workers.embedding_worker import (
    EmbeddingWorker,
    EmbeddingWorkerConfig,
)
from tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create import (
    HFModelCfg,
    OpenAIModelCfg,
)
from tldw_Server_API.app.core.Embeddings.queue_schemas import (
    JobRequest,
    JobStatus,
    JobResult,
    JobType
)

# ========================================================================
# Worker Initialization Tests
# ========================================================================

class TestEmbeddingWorkerInitialization:
    """Test embedding worker initialization and configuration."""

    @pytest.mark.unit
    def test_worker_initialization_default_model(self):
        """Test worker initialization with default model."""
        cfg = EmbeddingWorkerConfig(
            worker_id="w1",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        assert worker is not None
        # Defaults come from EmbeddingWorkerConfig
        assert worker.embedding_config.default_model_name in (
            "dunzhang/stella_en_400M_v5",
            "sentence-transformers/all-MiniLM-L6-v2",
        )

    @pytest.mark.unit
    def test_worker_initialization_custom_model(self):
        """Test worker initialization with custom model."""
        cfg = EmbeddingWorkerConfig(
            worker_id="w2",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            default_model_name="BAAI/bge-small-en-v1.5",
            max_batch_size=64,
        )
        worker = EmbeddingWorker(cfg)
        assert worker.embedding_config.default_model_name == "BAAI/bge-small-en-v1.5"
        assert worker.embedding_config.max_batch_size == 64

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    def test_model_loading(self, mock_create):
        """Test embedding generation pipeline calls create_embeddings_batch."""
        mock_create.side_effect = lambda *args, **kwargs: [np.random.randn(384).tolist()]
        cfg = EmbeddingWorkerConfig(
            worker_id="w3",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            default_model_name="sentence-transformers/all-MiniLM-L6-v2",
        )
        worker = EmbeddingWorker(cfg)
        # Call private generation with HF config
        embeddings = asyncio.run(
            worker._generate_embeddings(["hello"], HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        )
        assert len(embeddings) == 1
        mock_create.assert_called_once()

    @pytest.mark.unit
    def test_worker_configuration_validation(self):
        """Test worker configuration validation."""
        cfg = EmbeddingWorkerConfig(
            worker_id="w4",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            batch_size=0,
        )
        worker = EmbeddingWorker(cfg)
        assert worker.embedding_config.batch_size == 0

# ========================================================================
# Embedding Generation Tests
# ========================================================================

class TestEmbeddingGeneration:
    """Test embedding generation functionality."""

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    async def test_single_text_embedding(self, mock_create):
        """Test embedding generation for single text."""
        mock_create.side_effect = lambda *args, **kwargs: [np.random.randn(384).tolist()]
        cfg = EmbeddingWorkerConfig(
            worker_id="w5",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        text = "This is a test sentence for embedding."
        res = await worker._generate_embeddings([text], HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        embedding = res[0]

        assert isinstance(embedding, list)
        assert len(embedding) == 384

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    async def test_batch_text_embedding(self, mock_create):
        """Test batch embedding generation."""
        batch_size = 5
        mock_create.side_effect = lambda *args, **kwargs: np.random.randn(batch_size, 384).tolist()
        cfg = EmbeddingWorkerConfig(
            worker_id="w6",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        texts = [f"Sentence {i}" for i in range(batch_size)]
        embeddings = await worker._generate_embeddings(texts, HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")

        assert isinstance(embeddings, list)
        assert len(embeddings) == batch_size
        assert all(len(emb) == 384 for emb in embeddings)

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    async def test_empty_text_handling(self, mock_create):
        """Test handling of empty text input."""
        mock_create.side_effect = lambda *args, **kwargs: [np.random.randn(384).tolist()]
        cfg = EmbeddingWorkerConfig(
            worker_id="w7",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        res = await worker._generate_embeddings([""], HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        embedding = res[0]
        assert embedding is not None

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    async def test_long_text_truncation(self, mock_create):
        """Test handling of text exceeding max tokens."""
        mock_create.side_effect = lambda *args, **kwargs: [np.random.randn(384).tolist()]
        cfg = EmbeddingWorkerConfig(
            worker_id="w8",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)

        # Create text that would exceed token limit
        long_text = " ".join(["word"] * 1000)
        res = await worker._generate_embeddings([long_text], HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        embedding = res[0]

        assert isinstance(embedding, list)
        assert len(embedding) == 384
        # Text should be truncated internally

# ========================================================================
# Job Processing Tests
# ========================================================================

class TestJobProcessing:
    """Test job processing functionality."""

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    async def test_process_embedding_job(self, mock_create):
        """Test processing a single embedding job."""
        mock_create.side_effect = lambda *args, **kwargs: [np.random.randn(384).tolist()]
        cfg = EmbeddingWorkerConfig(
            worker_id="w9",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        from tldw_Server_API.app.core.Embeddings.queue_schemas import ChunkData, EmbeddingMessage
        chunk = ChunkData(
            chunk_id="c1",
            content="Process this text",
            metadata={},
            start_index=0,
            end_index=1,
            sequence_number=0,
        )
        message = EmbeddingMessage(
            job_id="job1",
            user_id="1",
            media_id=1,
            priority=50,
            user_tier="free",
            chunks=[chunk],
            embedding_model_config={"model_name_or_path": cfg.default_model_name},
            model_provider="huggingface",
            batch_size=1,
        )
        storage_msg = await worker.process_message(message)
        assert storage_msg is not None
        assert storage_msg.total_chunks == 1

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    async def test_process_batch_job(self, mock_create):
        """Test processing multiple jobs in batch."""
        mock_create.side_effect = lambda *args, **kwargs: np.random.randn(5, 384).tolist()
        cfg = EmbeddingWorkerConfig(
            worker_id="w10",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        from tldw_Server_API.app.core.Embeddings.queue_schemas import ChunkData, EmbeddingMessage
        chunks = [
            ChunkData(chunk_id=f"c{i}", content=f"text {i}", metadata={}, start_index=0, end_index=1, sequence_number=i)
            for i in range(5)
        ]
        message = EmbeddingMessage(
            job_id="jobbatch",
            user_id="1",
            media_id=1,
            priority=50,
            user_tier="free",
            chunks=chunks,
            embedding_model_config={"model_name_or_path": cfg.default_model_name},
            model_provider="huggingface",
            batch_size=5,
        )
        storage_msg = await worker.process_message(message)
        assert storage_msg is not None
        assert storage_msg.total_chunks == 5

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.workers.embedding_worker.create_embeddings_batch')
    async def test_job_error_handling(self, mock_create):
        """Test error handling during job processing."""
        mock_create.side_effect = Exception("Model error")
        cfg = EmbeddingWorkerConfig(
            worker_id="w11",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        from tldw_Server_API.app.core.Embeddings.queue_schemas import ChunkData, EmbeddingMessage
        chunk = ChunkData(chunk_id="c1", content="text", metadata={}, start_index=0, end_index=1, sequence_number=0)
        message = EmbeddingMessage(
            job_id="joberr",
            user_id="1",
            media_id=1,
            priority=50,
            user_tier="free",
            chunks=[chunk],
            embedding_model_config={"model_name_or_path": cfg.default_model_name},
            model_provider="huggingface",
            batch_size=1,
        )
        with pytest.raises(Exception):
            await worker.process_message(message)

# ========================================================================
# Performance and Optimization Tests
# ========================================================================

class TestPerformanceOptimization:
    """Test performance optimizations in the worker."""

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    async def test_batch_size_optimization(self, mock_create):
        """Test dynamic batch size optimization."""
        mock_create.side_effect = lambda *args, **kwargs: np.random.randn(32, 384).tolist()
        cfg = EmbeddingWorkerConfig(
            worker_id="w12",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            max_batch_size=32,
        )
        worker = EmbeddingWorker(cfg)

        # Test with various input sizes
        small_batch = ["text"] * 5
        medium_batch = ["text"] * 32
        large_batch = ["text"] * 100

        # Worker should handle different sizes efficiently
        await worker._generate_embeddings(small_batch, HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        await worker._generate_embeddings(medium_batch, HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        await worker._generate_embeddings(large_batch, HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        # We can't assert internal chunking without reaching into implementation; ensure calls occurred
        assert mock_create.called

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    async def test_memory_efficient_processing(self, mock_create, large_text_corpus):
        """Test memory-efficient processing of large corpus."""
        def mock_encode(texts, *args, **kwargs):
            # Simulate memory-efficient encoding
            batch_size = len(texts) if isinstance(texts, list) else 1
            out = np.random.randn(batch_size, 384).tolist() if batch_size > 1 else [np.random.randn(384).tolist()]
            return out
        mock_create.side_effect = mock_encode
        cfg = EmbeddingWorkerConfig(
            worker_id="w13",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            max_batch_size=32,
        )
        worker = EmbeddingWorker(cfg)

        # Process large corpus
        embeddings = []
        for i in range(0, len(large_text_corpus), worker.batch_size):
            batch = large_text_corpus[i:i + worker.batch_size]
            batch_embeddings = await worker._generate_embeddings(batch, HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
            embeddings.extend(batch_embeddings)

        assert len(embeddings) == len(large_text_corpus)
        assert all(len(emb) == 384 for emb in embeddings)

    @pytest.mark.unit
    async def test_concurrent_job_processing(self):
        """Test concurrent processing of multiple jobs."""
        with patch('sentence_transformers.SentenceTransformer') as mock_transformer:
            mock_model = MagicMock()
            mock_model.encode.return_value = np.random.randn(384)
            mock_transformer.return_value = mock_model

            cfg = EmbeddingWorkerConfig(
                worker_id="w14",
                worker_type="embedding",
                queue_name="embeddings:embedding",
                consumer_group="embedding-workers",
            )
            worker = EmbeddingWorker(cfg)

            # Create multiple concurrent tasks
            tasks = []
            for i in range(10):
                text = f"Concurrent text {i}"
                task = asyncio.create_task(worker._generate_embeddings([text], HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface"))
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            assert len(results) == 10
            assert all(len(r[0]) == 384 for r in results)

# ========================================================================
# Model-Specific Tests
# ========================================================================

class TestModelSpecificBehavior:
    """Test model-specific behaviors and configurations."""

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    def test_minilm_model_configuration(self, mock_create):
        """Test MiniLM model specific configuration."""
        mock_create.return_value = [np.random.randn(384).tolist()]
        cfg = EmbeddingWorkerConfig(
            worker_id="w15",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            default_model_name="sentence-transformers/all-MiniLM-L6-v2",
        )
        worker = EmbeddingWorker(cfg)
        # Implicitly uses dimension=384 via model config expectations
        assert worker.embedding_config.default_model_name == "sentence-transformers/all-MiniLM-L6-v2"

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    def test_mpnet_model_configuration(self, mock_create):
        """Test MPNet model specific configuration."""
        cfg = EmbeddingWorkerConfig(
            worker_id="w16",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            default_model_name="sentence-transformers/all-mpnet-base-v2",
        )
        worker = EmbeddingWorker(cfg)
        assert worker.embedding_config.default_model_name == "sentence-transformers/all-mpnet-base-v2"

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    async def test_openai_embedding_fallback(self, mock_create):
        """Test fallback to OpenAI embeddings."""
        mock_create.return_value = [np.random.randn(1536).tolist()]
        cfg = EmbeddingWorkerConfig(
            worker_id="w17",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        res = await worker._generate_embeddings(["Test text"], OpenAIModelCfg(model_name_or_path="text-embedding-3-small"), "openai")
        assert len(res[0]) == 1536

# ========================================================================
# Error Recovery Tests
# ========================================================================

class TestErrorRecovery:
    """Test error recovery mechanisms."""

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    async def test_retry_on_transient_error(self, mock_create):
        """Test retry logic for transient errors."""
        call_count = 0

        def mock_encode(texts, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Transient error")
            return [np.random.randn(384).tolist()]
        mock_create.side_effect = mock_encode
        cfg = EmbeddingWorkerConfig(
            worker_id="w18",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
        )
        worker = EmbeddingWorker(cfg)
        res = await worker._generate_embeddings(["Test text"], HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")
        assert res is not None
        assert call_count == 3

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    async def test_fallback_on_model_failure(self, mock_create):
        """Test fallback to alternative model on failure."""
        # Primary fails twice then fallback
        def side_effect(texts, model_name, provider, api_url, api_key):
            if model_name == "primary-model":
                raise Exception("Primary model failed")
            return [np.random.randn(384).tolist()]
        mock_create.side_effect = side_effect
        cfg = EmbeddingWorkerConfig(
            worker_id="w19",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            default_model_name="primary-model",
            fallback_model_name="fallback-model",
        )
        worker = EmbeddingWorker(cfg)
        res = await worker._generate_embeddings(["Test text"], HFModelCfg(model_name_or_path="primary-model", trust_remote_code=False), "huggingface")
        assert res is not None and len(res[0]) == 384

    @pytest.mark.unit
    @patch('tldw_Server_API.app.core.Embeddings.Embeddings_Server.Embeddings_Create.create_embeddings_batch')
    async def test_graceful_degradation(self, mock_create):
        """Test graceful degradation when resources are limited."""
        def mock_encode(texts, *args, **kwargs):
            # Simulate resource constraints
            if len(texts) > 16:
                raise MemoryError("Batch too large")
            return np.random.randn(len(texts), 384).tolist()
        mock_create.side_effect = mock_encode
        cfg = EmbeddingWorkerConfig(
            worker_id="w20",
            worker_type="embedding",
            queue_name="embeddings:embedding",
            consumer_group="embedding-workers",
            max_batch_size=32,
        )
        worker = EmbeddingWorker(cfg)

        # Should automatically reduce batch size
        texts = ["text"] * 32
        embeddings = await worker._generate_embeddings(texts, HFModelCfg(model_name_or_path=cfg.default_model_name, trust_remote_code=False), "huggingface")

        assert len(embeddings) == 32
        # Should have processed in smaller batches
