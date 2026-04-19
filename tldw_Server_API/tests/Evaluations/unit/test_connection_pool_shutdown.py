"""Focused tests for connection pool shutdown behavior."""

import time
import threading

import pytest

from tldw_Server_API.app.core.Evaluations.connection_pool import ConnectionPool


class _ShutdownAwareMaintenanceTask:
    """Test double that validates shutdown ordering."""

    def __init__(self, wakeup_event: threading.Event):
        self._wakeup_event = wakeup_event
        self.join_timeout = None

    def is_alive(self) -> bool:
        return True

    def join(self, timeout: float | None = None) -> None:
        if not self._wakeup_event.is_set():
            pytest.fail("shutdown must wake maintenance before joining")
        self.join_timeout = timeout


class _TimeoutRecordingMaintenanceTask:
    """Test double that records the shutdown join timeout."""

    def __init__(self):
        self.join_timeout = None

    def is_alive(self) -> bool:
        return True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeout = timeout


@pytest.mark.unit
class TestConnectionPoolShutdown:
    """Shutdown behavior should wake maintenance and avoid long joins."""

    def test_shutdown_sets_maintenance_wakeup_before_join(self, temp_db_path):
        pool = ConnectionPool(db_path=str(temp_db_path), enable_monitoring=False)
        wakeup_event = threading.Event()
        maintenance_task = _ShutdownAwareMaintenanceTask(wakeup_event)
        pool._maintenance_shutdown_event = wakeup_event
        pool._maintenance_task = maintenance_task

        pool.shutdown()

        if not wakeup_event.is_set():
            pytest.fail("maintenance wakeup event was not set during shutdown")
        if maintenance_task.join_timeout != 1.0:
            pytest.fail(f"expected join timeout 1.0, got {maintenance_task.join_timeout!r}")

    def test_shutdown_uses_short_join_timeout_for_maintenance(self, temp_db_path):
        pool = ConnectionPool(db_path=str(temp_db_path), enable_monitoring=False)
        maintenance_task = _TimeoutRecordingMaintenanceTask()
        pool._maintenance_task = maintenance_task

        pool.shutdown()

        if maintenance_task.join_timeout is None:
            pytest.fail("maintenance thread was not joined during shutdown")
        if not pytest.approx(1.0, abs=0.05) == maintenance_task.join_timeout:
            pytest.fail(f"expected join timeout around 1.0, got {maintenance_task.join_timeout!r}")

    def test_shutdown_interrupts_real_maintenance_wait_promptly(self, temp_db_path):
        pool = ConnectionPool(db_path=str(temp_db_path), enable_monitoring=False)
        maintenance_started = threading.Event()
        original_perform_maintenance = pool._perform_maintenance

        def _recording_perform_maintenance() -> None:
            maintenance_started.set()
            original_perform_maintenance()

        pool._perform_maintenance = _recording_perform_maintenance  # type: ignore[method-assign]
        pool._start_maintenance()

        if not maintenance_started.wait(timeout=2.0):
            pytest.fail("maintenance worker did not start")

        start = time.perf_counter()
        pool.shutdown()
        shutdown_duration = time.perf_counter() - start

        if pool._maintenance_task is None or pool._maintenance_task.is_alive():
            pytest.fail("maintenance worker did not stop during shutdown")
        if shutdown_duration >= 1.5:
            pytest.fail(f"shutdown did not interrupt maintenance wait promptly: {shutdown_duration:.3f}s")
