"""
Shared fixtures for Resource_Governance tests.

- Re-export AuthNZ Postgres fixtures (e.g., setup_test_database, test_db_pool)
- Ensure lease purge is enabled in Redis RG during tests to reduce flakiness
  by setting RG_TEST_PURGE_LEASES_BEFORE_RESERVE=1. This makes the Redis
  governor perform a best-effort purge of expired leases for the policy
  namespace before a reserve. It only affects the in-memory stub or when this
  env var is set, and is safe for unit tests.
"""

import os
import pytest

# Re-export AuthNZ Postgres fixtures so Resource_Governance tests that rely on
# database-backed policy/admin helpers can use the same infrastructure as the
# AuthNZ suites.
from tldw_Server_API.tests.AuthNZ.conftest import (  # noqa: F401
    setup_test_database,
    clean_database,
    test_db_pool,
    isolated_test_environment,
)


@pytest.fixture(autouse=True)
def rg_test_purge_env(monkeypatch):
    """Enable pre-reserve lease purge for all RG tests via env."""
    monkeypatch.setenv("RG_TEST_PURGE_LEASES_BEFORE_RESERVE", "1")
    if not os.getenv("REDIS_URL"):
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379")
    if not (os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")):
        host = os.getenv("TEST_DB_HOST", "localhost")
        port = os.getenv("TEST_DB_PORT", "5432")
        user = os.getenv("TEST_DB_USER") or os.getenv("POSTGRES_USER", "tldw_user")
        pwd = os.getenv("TEST_DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "TestPassword123!")
        db = os.getenv("TEST_DB_NAME") or os.getenv("POSTGRES_DB", "tldw_test")
        dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
        monkeypatch.setenv("TEST_DATABASE_URL", dsn)
