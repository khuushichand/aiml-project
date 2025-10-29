import os
import pytest

# Load shared Postgres helpers via top-level tests/conftest.py (pytest_plugins)

# Mark every test in this directory as part of the 'jobs' suite
pytestmark = pytest.mark.jobs


@pytest.fixture(autouse=True)
def _reset_settings_and_env(monkeypatch):
    """Ensure deterministic single-user auth for Jobs tests.

    - Force TEST_MODE and single_user auth
    - Remove any pre-set SINGLE_USER_API_KEY so tests use the deterministic
      test key from get_settings() (e.g., "test-api-key-12345").
    - Reset settings singleton so changes take effect before app import.
    """
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    # Disable AuthNZ scheduler in tests to prevent background APScheduler threads
    monkeypatch.setenv("AUTHNZ_SCHEDULER_DISABLED", "1")
    # Minimize app startup and disable background workers/services that can
    # interfere with Jobs tests or cause memory/thread leaks during the suite.
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("CHATBOOKS_CORE_WORKER_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_GAUGES_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_RECONCILE_ENABLE", "false")
    monkeypatch.setenv("AUDIO_JOBS_WORKER_ENABLED", "false")
    monkeypatch.setenv("EMBEDDINGS_REEMBED_WORKER_ENABLED", "false")
    monkeypatch.setenv("JOBS_WEBHOOKS_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_WEBHOOK_DLQ_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_ARTIFACT_GC_ENABLED", "false")
    monkeypatch.setenv("WORKFLOWS_DB_MAINTENANCE_ENABLED", "false")
    # Skip privilege catalog validation to avoid external file dependency
    monkeypatch.setenv("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "0")
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    # Default Jobs tests to compatibility mode unless individual cases opt in.
    monkeypatch.setenv("JOBS_DISABLE_LEASE_ENFORCEMENT", "1")
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
        reset_settings()
    except Exception:
        # Some tests may import before settings module exists; that's fine
        pass
    # Ensure Jobs acquire gate is open for test isolation (some tests import app,
    # whose shutdown sets the gate to True; reset here to avoid bleed)
    try:
        from tldw_Server_API.app.core.Jobs.manager import JobManager
        JobManager.set_acquire_gate(False)
    except Exception:
        pass
    yield


def pytest_collection_modifyitems(session, config, items):
    """Automatically apply the shared PG schema/setup fixture to any test
    items marked with `pg_jobs` so individual files don't need to repeat
    autouse module fixtures.

    This keeps SQLite-only tests unaffected.
    """
    try:
        import pytest  # local import to avoid hard dependency in collection time
    except Exception:
        return
    for item in items:
        try:
            if any(m.name == "pg_jobs" for m in item.iter_markers()):
                item.add_marker(pytest.mark.usefixtures("pg_schema_and_cleanup"))
        except Exception:
            # Best effort; do not break collection on errors
            pass
