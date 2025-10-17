"""PostgreSQL concurrency tests for per-run event_seq monotonicity.

Skips if Postgres driver/env isn't available. Spawns concurrent writers
to append events to a single run_id and asserts strictly increasing
sequences with no gaps/dupes.
"""

from __future__ import annotations

import asyncio
import os
from typing import List

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory
from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase


def _pg_env_available() -> bool:
    required = (
        "POSTGRES_TEST_HOST",
        "POSTGRES_TEST_PORT",
        "POSTGRES_TEST_DB",
        "POSTGRES_TEST_USER",
        "POSTGRES_TEST_PASSWORD",
    )
    return all(os.getenv(k) for k in required)


pytestmark = pytest.mark.skipif(not _pg_env_available(), reason="Postgres test env not configured")


def _pg_backend():
    cfg = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
        pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
        pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
        pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
        pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
    )
    return DatabaseBackendFactory.create_backend(cfg)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_seq_monotonic_under_contention():
    backend = _pg_backend()
    db = WorkflowsDatabase(db_path=":memory:", backend=backend)

    # Create a run
    run_id = "concurrent-run"
    db.create_run(run_id=run_id, tenant_id="default", user_id="1", inputs={}, workflow_id=None, definition_version=1, definition_snapshot={})

    # Concurrently append events
    async def _append_many(n: int, label: str) -> List[int]:
        seqs: List[int] = []
        loop = asyncio.get_running_loop()
        for i in range(n):
            # Offload to threadpool to exercise backend pool concurrency
            seq = await loop.run_in_executor(None, db.append_event, "default", run_id, f"evt_{label}", {"i": i})
            seqs.append(int(seq))
        return seqs

    # Spawn multiple writers
    tasks = [asyncio.create_task(_append_many(50, f"w{j}")) for j in range(4)]
    results = await asyncio.gather(*tasks)
    all_seqs = sorted(x for sub in results for x in sub)

    # Expect contiguous 1..N
    assert all_seqs[0] == 1
    assert all_seqs[-1] == len(all_seqs)
    # No duplicates
    assert len(all_seqs) == len(set(all_seqs))

    # Verify DB order is strictly ascending
    events = db.get_events(run_id)
    seqs_db = [int(e["event_seq"]) for e in events]
    assert seqs_db == sorted(seqs_db)
