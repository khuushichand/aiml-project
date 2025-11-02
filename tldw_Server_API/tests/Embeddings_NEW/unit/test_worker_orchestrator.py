"""
Unit tests for parts of the new Worker Orchestrator API.

These tests validate construction and basic pool lifecycle without
requiring external services (Redis, Prometheus, etc.).
"""

import pytest
import asyncio
from unittest.mock import patch

from tldw_Server_API.app.core.Embeddings.worker_orchestrator import WorkerOrchestrator, WorkerPool
from tldw_Server_API.app.core.Embeddings.worker_config import (
    OrchestrationConfig,
    ChunkingWorkerPoolConfig,
)


@pytest.mark.unit
def test_orchestrator_constructs_with_default_config():
    """Orchestrator should accept a full OrchestrationConfig and expose it."""
    cfg = OrchestrationConfig.default_config()
    orch = WorkerOrchestrator(cfg)
    assert orch.config is cfg
    assert isinstance(orch.config.worker_pools["chunking"], ChunkingWorkerPoolConfig)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_pool_lifecycle():
    """WorkerPool starts, scales, and stops with patched workers."""
    pool_cfg = ChunkingWorkerPoolConfig(num_workers=2)
    pool = WorkerPool(pool_cfg)

    async def fake_create_worker(worker_id: str, redis_url: str):
        class _W:
            async def start(self):
                return None
        return _W()

    with patch.object(WorkerPool, "_create_worker", side_effect=fake_create_worker):
        await pool.start("redis://localhost:6379")
        assert len(pool.workers) == 2
        await pool.scale(3, "redis://localhost:6379")
        assert len(pool.workers) == 3
        await pool.stop()
        assert len(pool.workers) == 0
