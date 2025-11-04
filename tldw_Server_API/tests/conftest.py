"""
Pytest configuration for the main test suite.

Registers shared test plugins and provides common fixtures.
"""

# Shared Chat/AuthNZ fixtures used across multiple test packages
pytest_plugins = (
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.authnz_fixtures",
    # Expose isolated Chat fixtures (unit_test_client, isolated_db, etc.) globally
    "tldw_Server_API.tests.Chat.integration.conftest_isolated",
    # Unified Postgres fixtures (temp DBs, reachability, DatabaseConfig)
    "tldw_Server_API.tests._plugins.postgres",
    # Optional pgvector fixtures for tests that need live PG
    "tldw_Server_API.tests.helpers.pgvector",
)

import os
import logging
# Ensure problematic optional routers don't import during test collection
# and enable test-friendly behaviors before importing the app.
_log = logging.getLogger(__name__)
try:
    # Disable heavy 'research' router to avoid importing Web_Scraping during collection
    existing_disable = os.getenv("ROUTES_DISABLE", "")
    if "research" not in existing_disable:
        os.environ["ROUTES_DISABLE"] = (existing_disable + ",research").strip(",")
    # Enable deterministic test behaviors across subsystems
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    # Ensure Postgres tests use a proper DSN instead of falling back to a SQLite DATABASE_URL.
    # If a dedicated DSN is provided via TEST_DATABASE_URL or POSTGRES_TEST_DSN, prefer it.
    # Otherwise, if POSTGRES_TEST_HOST/USER/DB are present, synthesize a DSN.
    try:
        _pg_dsn = os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_DSN")
        if not _pg_dsn:
            _pg_host = os.getenv("POSTGRES_TEST_HOST")
            _pg_port = os.getenv("POSTGRES_TEST_PORT", "5432")
            _pg_user = os.getenv("POSTGRES_TEST_USER")
            _pg_pass = os.getenv("POSTGRES_TEST_PASSWORD", "")
            _pg_db = os.getenv("POSTGRES_TEST_DATABASE") or os.getenv("POSTGRES_TEST_DB")
            if _pg_host and _pg_user and _pg_db:
                # Compose a DSN and set TEST_DATABASE_URL so PG helpers don't pick SQLite DATABASE_URL
                _auth = f"{_pg_user}:{_pg_pass}" if _pg_pass else _pg_user
                _pg_dsn = f"postgresql://{_auth}@{_pg_host}:{int(_pg_port)}/{_pg_db}"
        if _pg_dsn and _pg_dsn.lower().startswith("postgres"):
            os.environ["TEST_DATABASE_URL"] = _pg_dsn
    except Exception:
        pass
except Exception as e:
    # Surface environment setup failures in test output
    _log.exception("Failed to apply test environment setup in conftest.py")
import pytest
from fastapi.testclient import TestClient


# Skip Jobs-marked tests by default unless explicitly enabled via RUN_JOBS.
# This ensures general CI workflows never run Jobs tests; the dedicated
# jobs-suite workflow sets RUN_JOBS=1 to include them.
import pytest as _pytest_jobs_gate

@_pytest_jobs_gate.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):  # pragma: no cover - collection-time behavior
    try:
        run_jobs = str(os.getenv("RUN_JOBS", "")).lower() in {"1", "true", "yes", "y", "on"}
    except Exception:
        run_jobs = False
    if run_jobs:
        return
    skip_jobs = _pytest_jobs_gate.mark.skip(reason="Jobs tests run only in the jobs-suite CI workflow")
    jobs_markers = {"jobs", "pg_jobs", "pg_jobs_stress"}
    for item in items:
        try:
            if any(m.name in jobs_markers for m in item.iter_markers()):
                item.add_marker(skip_jobs)
        except Exception:
            # Never break collection on marker inspection
            pass


# Bump file-descriptor limit for macOS/Linux test runs to avoid spurious
# 'Too many open files' and SQLite 'unable to open database file' errors
# caused by module-level TestClient instances in some test modules.
@pytest.fixture(scope="session", autouse=True)
def _raise_fd_limit():  # pragma: no cover - platform-dependent behavior
    try:
        import resource  # POSIX only
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        # Aim for at least 4096 if permitted by the hard limit
        target = 4096
        new_soft = min(max(soft, target), hard if hard > 0 else target)
        if new_soft > soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
    except Exception:
        # On platforms without 'resource' (e.g., Windows) or when permissions
        # disallow raising limits, silently continue.
        pass

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

    # Import the FastAPI app and dependencies lazily to avoid heavy imports during test collection
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
    from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger

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


# Unified Postgres fixtures are provided by tldw_Server_API.tests._plugins.postgres
