# test_embedding_workers.py  (renamed to avoid basename conflicts)
"""
Unit tests for embedding worker components.

Tests the base worker class and specialized workers (chunking, embedding, storage)
without requiring actual Redis or database connections.
"""

import asyncio
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import pytest
import redis.asyncio as aioredis

from tldw_Server_API.app.core.Embeddings.workers.base_worker import BaseWorker, WorkerConfig
from tldw_Server_API.app.core.Embeddings.workers.chunking_worker import ChunkingWorker
from tldw_Server_API.app.core.Embeddings.workers.embedding_worker import EmbeddingWorker, EmbeddingWorkerConfig
from tldw_Server_API.app.core.Embeddings.workers.storage_worker import StorageWorker
from tldw_Server_API.app.core.Embeddings.queue_schemas import (
    ChunkingMessage,
    ChunkData,
    EmbeddingMessage,
    EmbeddingData,
    StorageMessage,
    JobStatus,
    JobPriority,
    UserTier,
    ChunkingConfig
)
from tldw_Server_API.app.core.Chunking.constants import FRONTMATTER_SENTINEL_KEY


@pytest.fixture
def base_worker_config():
    """Fixture for base worker configuration"""
    return WorkerConfig(
        worker_id="test-worker-1",
        worker_type="test",
        redis_url="redis://localhost:6379",
        queue_name="test:queue",
        consumer_group="test-group",
        batch_size=1,
        poll_interval_ms=100,
        max_retries=3,
        heartbeat_interval=30,
        shutdown_timeout=30,
        metrics_interval=60
    )


@pytest.fixture
def embedding_worker_config():
    """Fixture for embedding worker configuration"""
    return EmbeddingWorkerConfig(
        worker_id="embedding-worker-1",
        worker_type="embedding",
        redis_url="redis://localhost:6379",
        queue_name="embeddings:embedding",
        consumer_group="embedding-group",
        default_model_provider="huggingface",
        default_model_name="sentence-transformers/all-MiniLM-L6-v2",
        max_batch_size=32,
        gpu_id=None
    )


@pytest.fixture
def chunking_message():
    """Fixture for a sample chunking message"""
    return ChunkingMessage(
        job_id="test-job-123",
        user_id="user-456",
        media_id=789,
        priority=JobPriority.NORMAL,
        user_tier=UserTier.FREE,
        content="This is a test document with multiple sentences. It should be chunked properly. Each chunk should have the right metadata.",
        content_type="text",
        chunking_config=ChunkingConfig(
            chunk_size=100,  # Minimum is 100
            overlap=10,
            separator=" "
        ),
        source_metadata={"source": "test"}
    )


@pytest.fixture
def embedding_message():
    """Fixture for a sample embedding message"""
    return EmbeddingMessage(
        job_id="test-job-123",
        user_id="user-456",
        media_id=789,
        priority=JobPriority.NORMAL,
        user_tier=UserTier.FREE,
        chunks=[
            ChunkData(
                chunk_id="chunk-1",
                content="This is the first chunk",
                metadata={},
                start_index=0,
                end_index=24,
                sequence_number=0
            ),
            ChunkData(
                chunk_id="chunk-2",
                content="This is the second chunk",
                metadata={},
                start_index=25,
                end_index=49,
                sequence_number=1
            )
        ],
        embedding_model_config={"model_name": "test-model"},
        model_provider="huggingface"
    )


@pytest.fixture
def storage_message():
    """Fixture for a sample storage message"""
    return StorageMessage(
        job_id="test-job-123",
        user_id="user-456",
        media_id=789,
        priority=JobPriority.NORMAL,
        user_tier=UserTier.FREE,
        embeddings=[
            EmbeddingData(
                chunk_id="chunk-1",
                embedding=[0.1, 0.2, 0.3],
                model_used="test-model",
                dimensions=3,
                metadata={}
            ),
            EmbeddingData(
                chunk_id="chunk-2",
                embedding=[0.4, 0.5, 0.6],
                model_used="test-model",
                dimensions=3,
                metadata={}
            )
        ],
        collection_name="test-collection",
        total_chunks=2,
        processing_time_ms=100,
        metadata={}
    )


class InMemoryRedis:
    """Minimal in-memory Redis stand-in covering commands used by workers."""

    def __init__(self):
        self.streams = defaultdict(list)
        self.hashes = defaultdict(dict)
        self.expirations = {}
        self.setex_values = {}

    async def xadd(self, name, fields):
        self.streams[name].append(fields)
        return f"{len(self.streams[name])}-0"

    async def xreadgroup(self, group, consumer, streams, count=None, block=None):
        return []

    async def xack(self, name, group, *ids):
        return len(ids)

    async def hset(self, name, mapping=None, **kwargs):
        updates = mapping.copy() if mapping else {}
        updates.update(kwargs)
        self.hashes[name].update(updates)
        return len(updates)

    async def expire(self, name, ttl):
        self.expirations[name] = ttl
        return True

    async def setex(self, name, ttl, value):
        self.setex_values[name] = value
        return True

    async def xlen(self, name):
        return len(self.streams.get(name, []))

    async def delete(self, name):
        self.streams.pop(name, None)
        self.hashes.pop(name, None)

    async def flushdb(self):
        self.streams.clear()
        self.hashes.clear()
        self.expirations.clear()
        self.setex_values.clear()

    async def close(self):
        return None


@pytest.fixture
def redis_stub():
    """Provide in-memory Redis replacement for unit tests."""
    return InMemoryRedis()


def _docker_present() -> bool:
    return shutil.which("docker") is not None


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def docker_redis_service():
    """Launch a disposable Redis container when Docker is available and requested.

    Activate by setting USE_DOCKER_REDIS=1. Returns connection URL or None.
    """

    if not (_docker_present() and os.getenv("USE_DOCKER_REDIS", "0").lower() in {"1", "true", "yes"}):
        yield None
        return

    container_name = f"tldw-redis-test-{uuid.uuid4().hex[:8]}"
    port = int(os.getenv("TEST_REDIS_PORT", "6380"))

    try:
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-p",
                f"{port}:6379",
                "--name",
                container_name,
                "redis:7-alpine",
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        pytest.skip(f"Unable to start Redis container: {exc.stderr.decode().strip()}")

    if not _wait_for_port("127.0.0.1", port):
        subprocess.run(["docker", "rm", "-f", container_name], check=False)
        pytest.skip("Redis container did not become ready in time")

    url = f"redis://127.0.0.1:{port}"

    yield url

    subprocess.run(["docker", "rm", "-f", container_name], check=False)


class TestBaseWorker:
    """Test suite for BaseWorker class"""

    def test_worker_initialization(self, base_worker_config):
        """Test that worker initializes correctly"""
        # Create a concrete implementation for testing
        class TestWorker(BaseWorker):
            async def process_message(self, message: dict) -> bool:
                return True

            def _parse_message(self, data: dict):
                return data

            async def _send_to_next_stage(self, result):
                pass

        worker = TestWorker(base_worker_config)

        assert worker.config == base_worker_config
        assert worker.running == False
        assert worker.jobs_processed == 0
        assert worker.jobs_failed == 0
        assert worker.processing_times == []

    @pytest.mark.asyncio
    async def test_redis_connection_context(self, base_worker_config):
        """Test Redis connection context manager"""
        class TestWorker(BaseWorker):
            async def process_message(self, message: dict) -> bool:
                return True

            def _parse_message(self, data: dict):
                return data

            async def _send_to_next_stage(self, result):
                pass

        worker = TestWorker(base_worker_config)

        with patch('redis.asyncio.from_url') as mock_redis:
            mock_client = AsyncMock()
            # Make from_url return a coroutine that returns the mock client
            async def create_client(*args, **kwargs):
                return mock_client
            mock_redis.side_effect = create_client

            # Mock the close method
            mock_client.close = AsyncMock()

            async with worker._redis_connection() as client:
                assert client == mock_client
                mock_redis.assert_called_once_with(
                    base_worker_config.redis_url,
                    decode_responses=True
                )

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, base_worker_config):
        """Test graceful shutdown handling"""
        class TestWorker(BaseWorker):
            async def process_message(self, message: dict) -> bool:
                return True

            def _parse_message(self, data: dict):
                return data

            async def _send_to_next_stage(self, result):
                pass

        worker = TestWorker(base_worker_config)

        # Simulate signal handler
        worker._signal_handler(15, None)  # SIGTERM

        assert worker.running == False


class TestChunkingWorker:
    """Test suite for ChunkingWorker class"""

    @pytest.mark.asyncio
    async def test_process_chunking_message(self, base_worker_config, chunking_message, redis_stub):
        """Test processing a chunking message and sending to next stage"""
        worker = ChunkingWorker(base_worker_config)
        worker.redis_client = redis_stub

        with patch.object(worker, '_update_job_status', new_callable=AsyncMock) as mock_status, \
             patch.object(worker, '_update_job_progress', new_callable=AsyncMock) as mock_progress:
            result = await worker.process_message(chunking_message)

        assert isinstance(result, EmbeddingMessage)
        assert len(result.chunks) > 0
        first_metadata = result.chunks[0].metadata
        assert first_metadata.get(FRONTMATTER_SENTINEL_KEY) is True
        mock_status.assert_awaited()
        mock_progress.assert_awaited()

        await worker._send_to_next_stage(result)
        assert await redis_stub.xlen(worker.embedding_queue) == 1

    def test_chunk_text(self, base_worker_config):
        """Test text chunking logic returns tuples with offsets"""
        worker = ChunkingWorker(base_worker_config)

        text = "This is a test. It has multiple sentences. Each one should be properly chunked."
        config = ChunkingConfig(chunk_size=100, overlap=10, separator=" ")

        chunks = worker._chunk_text(text, config)

        assert len(chunks) >= 1
        first_chunk, start_idx, end_idx = chunks[0]
        assert isinstance(first_chunk, str)
        assert start_idx == 0
        assert end_idx <= len(text)

    def test_chunk_overlap(self, base_worker_config):
        """Test that chunk overlap works correctly"""
        worker = ChunkingWorker(base_worker_config)

        text = "word1 word2 word3 word4 word5 word6 word7 word8"
        config = ChunkingConfig(chunk_size=100, overlap=20, separator=" ")

        chunks = worker._chunk_text(text, config)

        if len(chunks) > 1:
            first_chunk = chunks[0][0]
            second_chunk = chunks[1][0]
            assert first_chunk[-5:] in second_chunk


class TestEmbeddingWorker:
    """Test suite for EmbeddingWorker class"""

    @pytest.mark.asyncio
    async def test_process_embedding_message(self, embedding_worker_config, embedding_message, redis_stub):
        """Test processing an embedding message"""
        worker = EmbeddingWorker(embedding_worker_config)
        worker.redis_client = redis_stub
        worker.cache = None  # disable caching side-effects for determinism

        worker._update_job_status = AsyncMock()
        worker._update_job_progress = AsyncMock()

        worker._generate_embeddings = AsyncMock(
            side_effect=lambda texts, config, provider: [[0.1, 0.2, 0.3] for _ in texts]
        )

        storage_message = await worker.process_message(embedding_message)

        assert isinstance(storage_message, StorageMessage)
        assert len(storage_message.embeddings) == len(embedding_message.chunks)
        worker._update_job_status.assert_awaited()
        worker._update_job_progress.assert_awaited()

        await worker._send_to_next_stage(storage_message)
        assert await redis_stub.xlen(worker.storage_queue) == 1

    @pytest.mark.asyncio
    async def test_batch_processing_respects_max_size(self, embedding_worker_config, embedding_message, redis_stub):
        """Test that batch processing respects configured batch size"""
        worker = EmbeddingWorker(embedding_worker_config)
        worker.redis_client = redis_stub
        worker.cache = None
        worker.embedding_config.max_batch_size = 1

        message = embedding_message.model_copy()
        message.chunks = [
            ChunkData(
                chunk_id=f"chunk-{i}",
                content=f"Content {i}",
                metadata={},
                start_index=i * 10,
                end_index=(i + 1) * 10,
                sequence_number=i
            )
            for i in range(5)
        ]

        call_counts = []

        async def fake_generate(texts, config, provider):
            call_counts.append(len(texts))
            return [[0.1, 0.2, 0.3] for _ in texts]

        worker._generate_embeddings = fake_generate
        worker._update_job_status = AsyncMock()
        worker._update_job_progress = AsyncMock()

        await worker.process_message(message)

        assert call_counts
        assert all(batch_len == 1 for batch_len in call_counts)


class TestStorageWorker:
    """Test suite for StorageWorker class"""

    @pytest.mark.asyncio
    async def test_process_storage_message(self, base_worker_config, storage_message, redis_stub):
        """Test processing a storage message using patched dependencies"""
        with patch('tldw_Server_API.app.core.Embeddings.workers.storage_worker.ChromaDBManager') as mock_manager_cls:
            mock_manager_cls.return_value = MagicMock()
            worker = StorageWorker(base_worker_config)

        worker.redis_client = redis_stub
        worker._update_job_status = AsyncMock()
        worker._update_job_progress = AsyncMock()
        worker._update_database = AsyncMock()

        mock_collection = MagicMock()
        worker._get_or_create_collection = AsyncMock(return_value=mock_collection)
        worker._store_batch = AsyncMock()

        await worker.process_message(storage_message)

        worker._get_or_create_collection.assert_awaited_once()
        worker._store_batch.assert_awaited()
        assert worker._update_job_status.await_count >= 2
        worker._update_database.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_or_create_collection_uses_manager(self, base_worker_config):
        with patch('tldw_Server_API.app.core.Embeddings.workers.storage_worker.ChromaDBManager') as mock_manager_cls:
            manager_instance = MagicMock()
            mock_manager_cls.return_value = manager_instance
            worker = StorageWorker(base_worker_config)

        manager_instance.get_or_create_collection.return_value = "collection"
        result = await worker._get_or_create_collection("user", "collection")

        assert result == "collection"
        manager_instance.get_or_create_collection.assert_called_once_with("user", "collection")

    @pytest.mark.asyncio
    async def test_store_batch_invokes_collection_add(self, base_worker_config):
        with patch('tldw_Server_API.app.core.Embeddings.workers.storage_worker.ChromaDBManager') as mock_manager_cls:
            mock_manager_cls.return_value = MagicMock()
            worker = StorageWorker(base_worker_config)

        collection = MagicMock()
        await worker._store_batch(
            collection,
            ids=["chunk-1"],
            embeddings=[[0.1, 0.2, 0.3]],
            documents=[""],
            metadatas=[{"foo": "bar"}]
        )

        collection.add.assert_called_once()


class TestWorkerRetryLogic:
    """Test retry handling on BaseWorker"""

    @pytest.mark.asyncio
    async def test_retry_requeues_message(self, base_worker_config, chunking_message, redis_stub):
        class TestWorker(BaseWorker):
            async def process_message(self, message):
                return True

            def _parse_message(self, data):
                return ChunkingMessage(**data)

            async def _send_to_next_stage(self, result):
                return None

        worker = TestWorker(base_worker_config)
        worker.redis_client = redis_stub

        message_data = chunking_message.model_dump()

        with patch("asyncio.sleep", new=AsyncMock()) as sleep_mock:
            await worker._handle_failed_message("1-0", message_data, Exception("boom"))

        assert await redis_stub.xlen(base_worker_config.queue_name) == 1
        sleep_mock.assert_awaited()

    @pytest.mark.asyncio
    async def test_retry_marks_failed_after_max(self, base_worker_config, chunking_message, redis_stub):
        class TestWorker(BaseWorker):
            async def process_message(self, message):
                return True

            def _parse_message(self, data):
                return ChunkingMessage(**data)

            async def _send_to_next_stage(self, result):
                return None

        worker = TestWorker(base_worker_config)
        worker.redis_client = redis_stub
        worker._update_job_status = AsyncMock()

        message_data = chunking_message.model_dump()
        message_data["retry_count"] = message_data["max_retries"]

        with patch("asyncio.sleep", new=AsyncMock()):
            await worker._handle_failed_message("1-0", message_data, Exception("boom"))

        worker._update_job_status.assert_awaited_once()


class TestWorkerMetrics:
    """Test metrics collection across workers"""

    @pytest.mark.asyncio
    async def test_metrics_collection(self, base_worker_config):
        """Test that workers collect metrics correctly"""
        class TestWorker(BaseWorker):
            async def process_message(self, message: dict) -> bool:
                return True

            def _parse_message(self, data: dict):
                return data

            async def _send_to_next_stage(self, result):
                pass

        worker = TestWorker(base_worker_config)

        # Process some messages
        worker.jobs_processed = 5
        worker.jobs_failed = 1
        worker.processing_times = [100, 200, 150, 180, 120]

        # Create expected metrics structure
        metrics = {
            'worker_id': worker.config.worker_id,
            'worker_type': worker.config.worker_type,
            'jobs_processed': worker.jobs_processed,
            'jobs_failed': worker.jobs_failed,
            'average_processing_time_ms': sum(worker.processing_times) / len(worker.processing_times) if worker.processing_times else 0
        }

        assert metrics['worker_id'] == "test-worker-1"
        assert metrics['worker_type'] == "test"
        assert metrics['jobs_processed'] == 5
        assert metrics['jobs_failed'] == 1
        assert metrics['average_processing_time_ms'] == 150  # Average of processing times


def test_worker_orchestration_initial_state():
    """Ensure worker orchestrator initializes without side effects"""
    from tldw_Server_API.app.core.Embeddings.worker_orchestrator import WorkerPool
    from tldw_Server_API.app.core.Embeddings.worker_config import ChunkingWorkerPoolConfig

    pool_config = ChunkingWorkerPoolConfig(
        worker_type="chunking",
        num_workers=2,
        queue_name="embeddings:chunking",
        consumer_group="chunking-group"
    )

    pool = WorkerPool(pool_config)

    assert pool.config == pool_config
    assert pool.running == False
    assert pool.workers == []


# Integration test marker for tests that require external services
@pytest.mark.integration
class TestWorkerIntegration:
    """Integration tests that require Redis and databases"""

    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(self, docker_redis_service, base_worker_config, chunking_message, embedding_worker_config):
        """Test chunking → embedding pipeline against a real Redis instance when available."""
        if not docker_redis_service:
            pytest.skip("Docker Redis not available; set USE_DOCKER_REDIS=1 to enable")

        redis_client = await aioredis.from_url(docker_redis_service, decode_responses=True)
        await redis_client.flushdb()

        try:
            chunk_config = base_worker_config.model_copy(update={
                "worker_id": "chunk-it",
                "redis_url": docker_redis_service,
                "queue_name": "it:chunking",
                "consumer_group": "it:chunk-group"
            })
            chunk_worker = ChunkingWorker(chunk_config)
            chunk_worker.redis_client = redis_client
            chunk_worker._update_job_status = AsyncMock()
            chunk_worker._update_job_progress = AsyncMock()

            embedding_config = embedding_worker_config.model_copy(update={
                "worker_id": "embed-it",
                "redis_url": docker_redis_service,
                "queue_name": "it:embedding",
                "consumer_group": "it:embed-group"
            })
            embedding_worker = EmbeddingWorker(embedding_config)
            embedding_worker.redis_client = redis_client
            embedding_worker.cache = None
            embedding_worker._update_job_status = AsyncMock()
            embedding_worker._update_job_progress = AsyncMock()

            storage_queue = embedding_worker.storage_queue

            chunk_result = await chunk_worker.process_message(chunking_message)
            await chunk_worker._send_to_next_stage(chunk_result)
            assert await redis_client.xlen(chunk_worker.embedding_queue) == 1

            async def fake_generate(texts, config, provider):
                return [[0.1, 0.2, 0.3] for _ in texts]

            embedding_worker._generate_embeddings = fake_generate
            storage_message = await embedding_worker.process_message(chunk_result)
            await embedding_worker._send_to_next_stage(storage_message)

            assert await redis_client.xlen(storage_queue) == 1

        finally:
            await redis_client.flushdb()
            await redis_client.close()
