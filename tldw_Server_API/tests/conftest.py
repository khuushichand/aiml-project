import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger

class _TestUsageLogger:
    def __init__(self):
        self.events = []

    def log_event(self, name, resource_id=None, tags=None, metadata=None):
        self.events.append((name, resource_id, tags, metadata))


@pytest.fixture()
def client_with_single_user(monkeypatch):
    """Provide a TestClient for the full FastAPI app with a single-user auth override.

    Returns a tuple of (client, usage_logger) for tests that also need to inspect usage events.
    """
    # Ensure tests run in non-production behavior
    os.environ.setdefault("TESTING", "true")

    usage_logger = _TestUsageLogger()

    async def _override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def _override_logger():
        return usage_logger

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_usage_event_logger] = _override_logger

    with TestClient(fastapi_app) as client:
        yield client, usage_logger

    fastapi_app.dependency_overrides.pop(get_request_user, None)
    fastapi_app.dependency_overrides.pop(get_usage_event_logger, None)


@pytest.fixture()
def client_user_only(client_with_single_user):
    """Shorthand fixture that returns only the TestClient from client_with_single_user."""
    client, _ = client_with_single_user
    return client


# Global session teardown to prevent test-run hangs from lingering executors/threads
@pytest.fixture(scope="session", autouse=True)
def _shutdown_executors_and_evaluations_pool():
    """Ensure global executors and the Evaluations connection pool are shut down at session end.

    Prevents pytest from hanging due to non-daemon worker threads started by
    CPU-bound helpers and background maintenance in the Evaluations module when
    app lifespan teardown is not exercised during tests.
    """
    yield
    # Best-effort shutdown of registered executors (thread/process pools)
    try:
        from tldw_Server_API.app.core.Utils.executor_registry import (
            shutdown_all_registered_executors_sync,
        )
        shutdown_all_registered_executors_sync(wait=True, cancel_futures=True)
    except Exception:
        pass
    # Explicit CPU pools cleanup (idempotent)
    try:
        from tldw_Server_API.app.core.Utils.cpu_bound_handler import cleanup_pools
        cleanup_pools()
    except Exception:
        pass
    # Stop Evaluations connection pool maintenance thread and close connections
    try:
        from tldw_Server_API.app.core.Evaluations.connection_pool import connection_manager
        connection_manager.shutdown()
    except Exception:
        pass
