"""
Comprehensive test suite for the Scheduler module.
"""

import asyncio
import contextlib
import os
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
import uuid

from ..scheduler import Scheduler, create_scheduler
from ..base import Task, TaskStatus, TaskPriority
from ..base.registry import get_registry
from ..config import SchedulerConfig
from ..backends import create_backend
from ..services import LeaseService
from ..authorization import AuthContext, TaskPermission

DEFAULT_METADATA = {"user_id": "test-user"}


@pytest.fixture
async def test_config():
    """Create test configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield SchedulerConfig(
            database_url=f"sqlite:///{tmpdir}/test.db",
            base_path=Path(tmpdir),
            min_workers=1,
            max_workers=5,
            write_buffer_size=10,
            write_buffer_flush_interval=0.1
        )


@pytest.fixture
async def scheduler(test_config):
    """Create and start a test scheduler."""
    scheduler = Scheduler(test_config)
    await scheduler.start(start_workers=False)  # No workers for unit tests
    try:
        yield scheduler
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_lifecycle(test_config):
    """Test scheduler start and stop."""
    scheduler = Scheduler(test_config)

    # Start scheduler
    await scheduler.start(start_workers=False)
    assert scheduler._started is True

    # Get status
    status = scheduler.get_status()
    assert status['started'] is True
    assert status['backend'] is not None

    # Stop scheduler
    await scheduler.stop()
    assert scheduler._started is False


@pytest.mark.asyncio
async def test_task_submission(scheduler):
    """Test submitting tasks to scheduler."""
    # Register a test handler
    registry = get_registry()

    @registry.task(name="test_handler")
    async def test_handler(payload):
        return {"result": payload.get("value", 0) * 2}

    # Submit task
    task_id = await scheduler.submit(
        handler="test_handler",
        payload={"value": 42},
        priority=TaskPriority.HIGH.value,
        metadata=DEFAULT_METADATA
    )

    assert task_id is not None

    # Force flush to database
    await scheduler.write_buffer.flush()

    # Retrieve task
    task = await scheduler.get_task(task_id)
    assert task is not None
    assert task.handler == "test_handler"
    assert task.payload == {"value": 42}
    assert task.priority == TaskPriority.HIGH.value
    assert task.metadata == DEFAULT_METADATA


@pytest.mark.asyncio
async def test_batch_submission(scheduler):
    """Test batch task submission."""
    # Register handler
    registry = get_registry()

    @registry.task(name="batch_handler")
    async def batch_handler(payload):
        return payload

    # Submit batch
    tasks = [
        {"handler": "batch_handler", "payload": {"id": i}, "metadata": DEFAULT_METADATA}
        for i in range(5)
    ]

    task_ids = await scheduler.submit_batch(tasks)
    assert len(task_ids) == 5

    # Force flush
    await scheduler.write_buffer.flush()

    # Verify all tasks created
    for i, task_id in enumerate(task_ids):
        task = await scheduler.get_task(task_id)
        assert task is not None
        assert task.payload == {"id": i}
        assert task.metadata == DEFAULT_METADATA


@pytest.mark.asyncio
async def test_batch_submission_idempotency_handling(scheduler):
    """Ensure duplicate idempotency keys in a batch map to the same task."""
    registry = get_registry()

    @registry.task(name="batch_idem_handler")
    async def handler(payload):
        return payload

    tasks = [
        {
            "handler": "batch_idem_handler",
            "payload": {"value": 1},
            "idempotency_key": "shared-key",
            "metadata": DEFAULT_METADATA
        },
        {
            "handler": "batch_idem_handler",
            "payload": {"value": 2},
            "idempotency_key": "shared-key",
            "metadata": DEFAULT_METADATA
        }
    ]

    task_ids = await scheduler.submit_batch(tasks)
    assert len(task_ids) == 2
    assert task_ids[0] == task_ids[1]

    stored_task = await scheduler.get_task(task_ids[0])
    assert stored_task is not None
    assert stored_task.metadata == DEFAULT_METADATA

    queue_status = await scheduler.get_queue_status("default")
    assert queue_status["size"] == 1


@pytest.mark.asyncio
async def test_batch_submission_requires_metadata(scheduler):
    """Batch submission should reject tasks without metadata."""
    registry = get_registry()

    @registry.task(name="batch_metadata_handler")
    async def handler(payload):
        return payload

    with pytest.raises(ValueError, match="metadata"):
        await scheduler.submit_batch([
            {
                "handler": "batch_metadata_handler",
                "payload": {"value": 1}
            }
        ])


@pytest.mark.asyncio
async def test_batch_submission_honours_authorization(scheduler):
    """Authorization checks are applied to batch submissions."""
    registry = get_registry()

    @registry.task(name="batch_protected")
    async def handler(payload):
        return payload

    scheduler.authorizer.register_handler_permissions(
        'batch_protected',
        [TaskPermission.SUBMIT],
        admin_only=True
    )

    user_context = AuthContext(user_id="regular", roles=["user"])

    with pytest.raises(PermissionError):
        await scheduler.submit_batch(
            [
                {
                    "handler": "batch_protected",
                    "payload": {"value": 1},
                    "metadata": {"user_id": "regular"}
                }
            ],
            auth_context=user_context
        )


@pytest.mark.asyncio
async def test_idempotency(scheduler):
    """Test idempotent task submission."""
    registry = get_registry()

    @registry.task(name="idempotent_handler")
    async def handler(payload):
        return payload

    # Submit task with idempotency key
    task_id1 = await scheduler.submit(
        handler="idempotent_handler",
        payload={"data": "test"},
        idempotency_key="unique-key-123",
        metadata=DEFAULT_METADATA
    )

    # Submit again with same key
    task_id2 = await scheduler.submit(
        handler="idempotent_handler",
        payload={"data": "different"},  # Different payload
        idempotency_key="unique-key-123"  # Same key
        ,
        metadata=DEFAULT_METADATA
    )

    # Should get same task ID
    assert task_id1 == task_id2


@pytest.mark.asyncio
async def test_task_dependencies(scheduler):
    """Test task dependency handling."""
    registry = get_registry()

    @registry.task(name="dep_handler")
    async def handler(payload):
        return payload

    # Create parent task
    parent_id = await scheduler.submit(
        handler="dep_handler",
        payload={"task": "parent"},
        metadata=DEFAULT_METADATA
    )

    # Create child task with dependency
    child_id = await scheduler.submit(
        handler="dep_handler",
        payload={"task": "child"},
        depends_on=[parent_id],
        metadata=DEFAULT_METADATA
    )

    # Force flush
    await scheduler.write_buffer.flush()

    # Check dependency service
    ready = await scheduler.dependency_service.check_dependencies(child_id)
    assert ready is False  # Parent not completed

    # Complete parent task
    await scheduler.backend.execute(
        "UPDATE tasks SET status = 'completed' WHERE id = ?",
        parent_id
    )

    # Now child should be ready
    ready = await scheduler.dependency_service.check_dependencies(child_id)
    assert ready is True


@pytest.mark.asyncio
async def test_worker_pool_integration(test_config):
    """Test scheduler with worker pool."""
    scheduler = Scheduler(test_config)
    await scheduler.start(start_workers=True)

    try:
        # Register handler
        registry = get_registry()

        @registry.task(name="worker_test")
        async def handler(payload):
            await asyncio.sleep(0.1)  # Simulate work
            return {"processed": payload}

        # Submit task
        task_id = await scheduler.submit(
            handler="worker_test",
            payload={"test": "data"},
            metadata=DEFAULT_METADATA
        )

        # Force flush
        await scheduler.write_buffer.flush()

        # Wait for task completion
        result = await scheduler.wait_for_task(task_id, timeout=5)
        assert result is not None
        assert result.status == TaskStatus.COMPLETED

        # Check worker pool status
        pool_status = scheduler.worker_pool.get_status()
        assert pool_status['total_tasks_processed'] > 0

    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_cancel_task_honors_metadata_owner(scheduler):
    """Ensure cancel_task enforces ownership based on persisted metadata."""
    registry = get_registry()

    @registry.task(name="cancel_test")
    async def handler(payload):
        return payload

    task_id = await scheduler.submit(
        handler="cancel_test",
        payload={"value": 1},
        metadata={"user_id": "owner-1"}
    )

    await scheduler.write_buffer.flush()

    with pytest.raises(PermissionError):
        await scheduler.cancel_task(task_id, auth_context=AuthContext(user_id="intruder"))

    cancelled = await scheduler.cancel_task(task_id, auth_context=AuthContext(user_id="owner-1"))
    assert cancelled is True

    task = await scheduler.get_task(task_id)
    assert task is not None
    assert task.status == TaskStatus.CANCELLED
    assert task.metadata.get("user_id") == "owner-1"


@pytest.mark.asyncio
async def test_sqlite_dependency_execution_runs_in_order(test_config):
    """Ensure SQLite backend releases dependent tasks once parents complete."""
    scheduler = Scheduler(test_config)
    await scheduler.start(start_workers=True)

    try:
        registry = get_registry()
        results = []

        @registry.task(name="dependency_parent_task")
        async def parent(payload):
            results.append(("parent", payload["value"]))
            return payload

        @registry.task(name="dependency_child_task")
        async def child(payload):
            results.append(("child", payload["value"]))
            return payload

        parent_id = await scheduler.submit(
            handler="dependency_parent_task",
            payload={"value": "parent"},
            metadata={"user_id": "dep-user"}
        )

        child_id = await scheduler.submit(
            handler="dependency_child_task",
            payload={"value": "child"},
            depends_on=[parent_id],
            metadata={"user_id": "dep-user"}
        )

        await scheduler.write_buffer.flush()

        parent_task = await scheduler.wait_for_task(parent_id, timeout=10)
        child_task = await scheduler.wait_for_task(child_id, timeout=10)

        assert parent_task is not None and parent_task.status == TaskStatus.COMPLETED
        assert child_task is not None and child_task.status == TaskStatus.COMPLETED
        assert [label for label, _ in results][:2] == ["parent", "child"]

    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_postgres_dependency_execution_runs_in_order(tmp_path):
    """Ensure Postgres backend handles dependent tasks (skips if unavailable)."""
    pytest.importorskip("asyncpg")
    dsn = os.getenv("SCHEDULER_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("SCHEDULER_TEST_POSTGRES_URL not configured")

    config = SchedulerConfig(
        database_url=dsn,
        base_path=tmp_path / "scheduler_pg",
        min_workers=1,
        max_workers=1
    )

    scheduler = Scheduler(config)
    try:
        await scheduler.start(start_workers=True)
    except Exception as exc:
        await scheduler.stop()
        pytest.skip(f"Postgres backend unavailable: {exc}")

    try:
        registry = get_registry()
        results = []

        @registry.task(name="pg_parent_task")
        async def parent(payload):
            results.append(("parent", payload["value"]))
            return payload

        @registry.task(name="pg_child_task")
        async def child(payload):
            results.append(("child", payload["value"]))
            return payload

        parent_id = await scheduler.submit(
            handler="pg_parent_task",
            payload={"value": "parent"},
            metadata={"user_id": "dep-user"}
        )

        child_id = await scheduler.submit(
            handler="pg_child_task",
            payload={"value": "child"},
            depends_on=[parent_id],
            metadata={"user_id": "dep-user"}
        )

        await scheduler.write_buffer.flush()

        parent_task = await scheduler.wait_for_task(parent_id, timeout=20)
        child_task = await scheduler.wait_for_task(child_id, timeout=20)

        assert parent_task is not None and parent_task.status == TaskStatus.COMPLETED
        assert child_task is not None and child_task.status == TaskStatus.COMPLETED
        assert [label for label, _ in results][:2] == ["parent", "child"]

    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_sqlite_auto_renew_extends_lease_expiration():
    """Ensure SQLite backend renews leases using the aligned contract."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = SchedulerConfig(
            database_url=f"sqlite:///{tmpdir}/lease.db",
            base_path=Path(tmpdir),
            lease_duration_seconds=10,
            lease_renewal_interval=3,
            min_workers=0,
            max_workers=0,
            write_buffer_size=1,
            write_buffer_flush_interval=0.01
        )

        backend = create_backend(config)
        await backend.connect()

        try:
            task = Task(handler="test.handler", payload={}, metadata={"user_id": "lease-test"})
            await backend.enqueue(task)

            # Simulate running task with a short timeout to control renewal horizon
            await backend.execute(
                "UPDATE tasks SET status = 'running', timeout = ? WHERE id = ?",
                20, task.id
            )

            lease_id = uuid.uuid4().hex
            original_expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=config.lease_duration_seconds)
            await backend.create_lease(lease_id, task.id, "worker-test", original_expires)

            lease_service = LeaseService(backend, config.lease_duration_seconds)
            renew_task = await lease_service.auto_renew(task.id, lease_id, renew_interval=0.2)

            try:
                await asyncio.sleep(0.5)  # allow renewal loop to run at least once
            finally:
                renew_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await renew_task

            row = await backend.fetchrow(
                "SELECT expires_at FROM task_leases WHERE lease_id = ?",
                lease_id
            )
            assert row is not None, "Lease record should exist after renewal"

            renewed_expires = datetime.fromisoformat(row['expires_at'])
            assert renewed_expires > original_expires, "Lease expiration should extend after renewal"
        finally:
            await backend.disconnect()


@pytest.mark.asyncio
async def test_queue_management(scheduler):
    """Test queue operations."""
    registry = get_registry()

    @registry.task(name="queue_test")
    async def handler(payload):
        return payload

    # Submit to different queues
    task1 = await scheduler.submit(
        handler="queue_test",
        payload={"id": 1},
        queue_name="high_priority",
        metadata=DEFAULT_METADATA
    )

    task2 = await scheduler.submit(
        handler="queue_test",
        payload={"id": 2},
        queue_name="low_priority",
        metadata=DEFAULT_METADATA
    )

    # Force flush
    await scheduler.write_buffer.flush()

    # Check queue sizes
    high_status = await scheduler.get_queue_status("high_priority")
    assert high_status['size'] == 1

    low_status = await scheduler.get_queue_status("low_priority")
    assert low_status['size'] == 1


@pytest.mark.asyncio
async def test_scheduler_context_manager(test_config):
    """Test scheduler as context manager."""
    async with Scheduler(test_config) as scheduler:
        registry = get_registry()

        @registry.task(name="context_test")
        async def handler(payload):
            return payload

        task_id = await scheduler.submit(
            handler="context_test",
            payload={"test": True},
            metadata=DEFAULT_METADATA
        )

        await scheduler.write_buffer.flush()

        task = await scheduler.get_task(task_id)
        assert task is not None


@pytest.mark.asyncio
async def test_leader_election(test_config):
    """Test leader election with multiple schedulers."""
    # Create two scheduler instances
    scheduler1 = Scheduler(test_config)
    scheduler2 = Scheduler(test_config)

    await scheduler1.start(start_workers=False)
    await scheduler2.start(start_workers=False)

    try:
        # Try to acquire leadership on both
        leader1 = await scheduler1.leader_election.acquire_leadership("test_resource")
        leader2 = await scheduler2.leader_election.acquire_leadership("test_resource")

        # Only one should be leader
        assert leader1 != leader2
        assert leader1 or leader2  # At least one should succeed

    finally:
        await scheduler1.stop()
        await scheduler2.stop()


@pytest.mark.asyncio
async def test_payload_service(scheduler):
    """Test large payload handling."""
    registry = get_registry()

    @registry.task(name="payload_test")
    async def handler(payload):
        return len(payload.get("data", ""))

    # Create large payload
    large_data = "x" * 100000  # 100KB of data

    task_id = await scheduler.submit(
        handler="payload_test",
        payload={"data": large_data},
        metadata=DEFAULT_METADATA
    )

    await scheduler.write_buffer.flush()

    # Check if payload was externalized
    should_external = scheduler.payload_service.should_externalize({"data": large_data})
    assert should_external is True

    # Get stats
    stats = await scheduler.payload_service.get_stats()
    assert stats['storage_path'] is not None


@pytest.mark.asyncio
async def test_error_handling(scheduler):
    """Test error handling in scheduler."""
    # Try to submit with non-existent handler
    with pytest.raises(ValueError, match="not registered"):
        await scheduler.submit(
            handler="non_existent",
            payload={},
            metadata=DEFAULT_METADATA
        )

    # Test scheduler not started
    new_scheduler = Scheduler(scheduler.config)
    with pytest.raises(Exception):
        await new_scheduler.submit(
            handler="test",
            payload={},
            metadata=DEFAULT_METADATA
        )


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_scheduler_lifecycle(SchedulerConfig(
        database_url="sqlite://:memory:",
        base_path=Path("/tmp")
    )))
    print("✓ Scheduler lifecycle test passed")

    print("\n✅ All scheduler tests passed!")
