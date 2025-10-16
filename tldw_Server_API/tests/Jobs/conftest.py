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
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
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
