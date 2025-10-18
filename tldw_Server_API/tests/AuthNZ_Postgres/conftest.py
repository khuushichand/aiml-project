"""Postgres-specific AuthNZ test configuration.

Ensures a PostgreSQL DSN is always defined for this suite. We do not skip
based on environment; instead we provide sane defaults. The shared
AuthNZ fixtures will attempt to connect and may auto-start a local dockerized
Postgres if reachable and allowed by environment settings.
"""

import os
import pytest

# Always mark as Postgres tests
pytestmark = [pytest.mark.postgres]

# Ensure a Postgres DSN is defined for this suite (defaults if unset)
if not (os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")):
    host = os.getenv("TEST_DB_HOST", "localhost")
    port = os.getenv("TEST_DB_PORT", "5432")
    user = os.getenv("TEST_DB_USER", "tldw_user")
    pwd = os.getenv("TEST_DB_PASSWORD", "TestPassword123!")
    db = os.getenv("TEST_DB_NAME", "tldw_test")
    dsn = f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
    os.environ["TEST_DATABASE_URL"] = dsn
    # Don't force DATABASE_URL here; per-test fixtures set it precisely

# Do not force global behavior here; the shared fixtures handle availability
# (optionally attempting docker) and may skip if PG is not required.

from tldw_Server_API.tests.AuthNZ.conftest import (  # noqa: F401
    setup_test_database,
    reset_singletons,
    event_loop,
    clean_database,
    test_db_pool,
    real_audit_service,
)
