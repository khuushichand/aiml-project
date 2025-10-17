"""Re-export AuthNZ test fixtures for Postgres-specific suite.

This ensures all tests in this folder use the shared Postgres
database setup, pool, and optional real audit service.
"""

import os
import pytest

# Mark all tests in this folder as postgres and skip when not configured
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set; skipping Postgres tests"),
]

from tldw_Server_API.tests.AuthNZ.conftest import (  # noqa: F401
    setup_test_database,
    reset_singletons,
    event_loop,
    clean_database,
    test_db_pool,
    real_audit_service,
)
