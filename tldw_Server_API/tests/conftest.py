"""
Global test configuration: environment toggles and robust session cleanup.

This file is loaded by pytest before any test modules. It sets environment
variables to prevent background services from starting during tests and ensures
that, regardless of failures or early termination, long‑lived background tasks
are shut down to avoid hanging the Python interpreter on exit.
"""

from __future__ import annotations

import os
import sys
import asyncio
import threading
from typing import Iterable

import pytest
from loguru import logger
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User


class _TestSafeStream:
    """Wrap a stream to swallow write/flush failures during pytest teardown."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, message: str):
        try:
            self._stream.write(message)
        except Exception:
            pass

    def flush(self):
        try:
            self._stream.flush()
        except Exception:
            pass

    def isatty(self):
        try:
            return bool(getattr(self._stream, "isatty", lambda: False)())
        except Exception:
            return False


if not getattr(logger, "_pytest_safe_add_installed", False):
    _orig_add = logger.add

    def _safe_add(sink, *args, **kwargs):
        try:
            if hasattr(sink, "write") and not isinstance(sink, _TestSafeStream):
                sink = _TestSafeStream(sink)
        except Exception:
            pass
        return _orig_add(sink, *args, **kwargs)

    logger.add = _safe_add  # type: ignore[assignment]
    setattr(logger, "_pytest_safe_add_installed", True)

try:
    logger.remove()
except Exception:
    pass
logger.add(
    _TestSafeStream(sys.stderr),
    level=os.getenv("LOGURU_LEVEL", "INFO"),
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
    enqueue=False,
)


@pytest.fixture
def admin_user():
    """Provide an authenticated admin context for tests that hit protected endpoints."""

    async def _admin():
        return User(
            id=42,
            username="admin",
            email="admin@example.com",
            is_active=True,
            is_admin=True,
        )

    app.dependency_overrides[get_request_user] = _admin
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_request_user, None)

# ----------------------------------------------------------------------------
# Environment toggles (set at import time so they apply before module imports)
# ----------------------------------------------------------------------------

# Enable general test mode
os.environ.setdefault("TEST_MODE", "1")

# Disable optional background services started by the app
os.environ.setdefault("WORKFLOWS_SCHEDULER_ENABLED", "false")
os.environ.setdefault("DISABLE_AUTHNZ_SCHEDULER", "1")
os.environ.setdefault("LLM_USAGE_AGGREGATOR_ENABLED", "false")
os.environ.setdefault("OUTPUTS_PURGE_ENABLED", "false")
os.environ.setdefault("DISABLE_PERSONALIZATION_CONSOLIDATION", "1")
os.environ.setdefault("RAG_QUALITY_EVAL_ENABLED", "false")


@pytest.fixture(scope="session", autouse=True)
def _session_env_and_cleanup():
    """Session-wide autouse fixture (sync to avoid event loop scope issues).

    - Ensures env toggles above are applied for the whole session.
    - On teardown, performs robust async cleanup of background services to
      prevent pytest from hanging at interpreter shutdown.
    """

    yield

    # Run async cleanup on a dedicated loop to prevent scope conflicts with
    # pytest-asyncio's function-scoped event loop runner.
    try:
        import asyncio as _asyncio
        try:
            _asyncio.run(_shutdown_all())
        except RuntimeError:
            # If an event loop is already running, use a fresh loop explicitly
            loop = _asyncio.new_event_loop()
            try:
                loop.run_until_complete(_shutdown_all())
            finally:
                loop.close()
    except Exception as _e:
        logger.debug(f"Session async cleanup encountered an error: {_e}")


async def _shutdown_all() -> None:
    """Stop background services and cancel lingering async tasks."""

    # Workflows scheduler (_noop task + APScheduler)
    try:
        from tldw_Server_API.app.services.workflows_scheduler import (
            stop_workflows_scheduler,
        )

        await stop_workflows_scheduler(None)
    except Exception as e:
        logger.debug(f"Workflows scheduler stop skipped: {e}")

    # AuthNZ session manager and scheduler
    try:
        from tldw_Server_API.app.core.AuthNZ.session_manager import (
            reset_session_manager,
        )

        await reset_session_manager()
    except Exception as e:
        logger.debug(f"SessionManager shutdown skipped: {e}")

    try:
        from tldw_Server_API.app.core.AuthNZ.scheduler import (
            stop_authnz_scheduler,
            reset_authnz_scheduler,
        )

        try:
            await stop_authnz_scheduler()
        finally:
            await reset_authnz_scheduler()
    except Exception as e:
        logger.debug(f"AuthNZ scheduler shutdown skipped: {e}")

    # Unified audit services (per-user background tasks)
    try:
        from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
            shutdown_all_audit_services,
        )

        await shutdown_all_audit_services()
    except Exception as e:
        logger.debug(f"Audit services shutdown skipped: {e}")

    # Registration service ThreadPoolExecutor
    try:
        from tldw_Server_API.app.services.registration_service import (
            reset_registration_service,
        )

        await reset_registration_service()
    except Exception as e:
        logger.debug(f"RegistrationService reset skipped: {e}")

    # Storage quota service executor (if instantiated)
    try:
        import tldw_Server_API.app.services.storage_quota_service as storage_mod

        svc = getattr(storage_mod, "_storage_service", None)
        if svc is not None:
            await svc.shutdown()
            storage_mod._storage_service = None
        quota = getattr(storage_mod, "_quota_service", None)
        if quota is not None:
            try:
                quota.executor.shutdown(wait=False)
            except Exception:
                pass
            storage_mod._quota_service = None
    except Exception as e:
        logger.debug(f"StorageQuotaService cleanup skipped: {e}")

    # Personalization consolidation loop (async task)
    try:
        import tldw_Server_API.app.services.personalization_consolidation as pc_mod

        svc = getattr(pc_mod, "_singleton", None)
        if svc is not None:
            await svc.stop()
            pc_mod._singleton = None
    except Exception as e:
        logger.debug(f"Personalization consolidation cleanup skipped: {e}")

    # Cancel any lingering async tasks on this loop
    await _cancel_pending_tasks()

    # Best-effort join for any non-daemon worker threads started during tests
    _join_non_daemon_threads()


# -----------------------------------------------------------------------------
# Guard against leaking Loguru sinks between tests
# -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_leaking_loguru_sinks():
    """
    Ensure tests don't leak extra Loguru sinks.

    Some tests add temporary sinks (including ones that forward Loguru -> stdlib).
    If a test forgets to remove them, it can cause recursion/noise with the
    stdlib→Loguru intercept configured by the app.

    We snapshot the current sink IDs before the test, and remove any new sinks
    added during the test at teardown.
    """
    try:
        # Private API access is acceptable in tests for cleanup purposes.
        from loguru import logger as _lg
        initial_sinks = set(getattr(_lg, "_core").handlers.keys())  # type: ignore[attr-defined]
    except Exception:
        initial_sinks = None

    yield

    if initial_sinks is None:
        return
    try:
        from loguru import logger as _lg
        current_sinks = set(getattr(_lg, "_core").handlers.keys())  # type: ignore[attr-defined]
        leaked = current_sinks - initial_sinks
        for sink_id in list(leaked):
            try:
                _lg.remove(sink_id)
            except Exception:
                pass
    except Exception:
        # Best-effort cleanup; never fail tests due to logger internals
        pass


async def _cancel_pending_tasks() -> None:
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    if not pending:
        return

    pending_names = ", ".join(sorted({t.get_name() for t in pending if t.get_name()}))
    logger.debug(f"Cancelling lingering async tasks: {pending_names or len(pending)}")

    for task in pending:
        task.cancel()

    for task, result in zip(pending, await asyncio.gather(*pending, return_exceptions=True)):
        if isinstance(result, asyncio.CancelledError):
            continue
        if isinstance(result, Exception):
            logger.debug(f"Task {task.get_name()!r} raised during cancel: {result}")


def _join_non_daemon_threads(timeout: float = 0.1) -> None:
    threads: Iterable[threading.Thread] = [
        t for t in threading.enumerate() if t is not threading.main_thread() and not t.daemon
    ]
    for t in threads:
        t.join(timeout=timeout)
    if threads:
        names = ", ".join(t.name for t in threads)
        logger.debug(f"Non-daemon threads joined during cleanup: {names}")
