"""Shared AuthNZ fixtures used by tests outside the AuthNZ suite.

This module avoids importing the AuthNZ test suite's conftest directly to
prevent duplicate plugin registration in pytest >= 8. Only the minimal
fixtures needed elsewhere are provided here.
"""

import os
import pytest_asyncio


@pytest_asyncio.fixture
async def real_audit_service(tmp_path):
    """Enable real UnifiedAuditService for this test and isolate per-user DBs.

    - Sets USER_DB_BASE_DIR to a per-test tmp directory
    - Resets settings so config picks up new base dir
    - Ensures audit services are shut down after the test
    """
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings as _reset_settings
    from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
        shutdown_all_audit_services as _shutdown_all,
    )

    os.environ['USER_DB_BASE_DIR'] = str((tmp_path / 'user_databases').resolve())
    _reset_settings()
    try:
        yield
    finally:
        try:
            await _shutdown_all()
        except Exception:
            _ = None


@pytest_asyncio.fixture
async def authnz_schema_ready():
    """Ensure AuthNZ schema is present for the configured per-test DB.

    Usage:
    - First set DATABASE_URL (and AUTH_MODE if needed) for this test via monkeypatch.
    - Then depend on this fixture to ensure the AuthNZ SQLite schema is initialized once.
      For Postgres backends, this is a no-op.
    """
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings as _reset_settings
        from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool as _reset_db_pool
        await _reset_db_pool()
        _reset_settings()
    except Exception:
        # Proceed best-effort even if reset hooks are unavailable
        _ = None
    try:
        from tldw_Server_API.app.core.AuthNZ.initialize import ensure_authnz_schema_ready_once as _ensure_once
        await _ensure_once()
    except Exception as _e:
        from loguru import logger as _logger
        _logger.debug(f"authnz_schema_ready fixture skipped ensure: {_e}")
    return None


def _run_async(coro):


    import asyncio as _asyncio
    try:
        loop = _asyncio.get_event_loop()
        if loop.is_running():
            # In a running loop context (rare for sync tests), schedule and wait
            return _asyncio.get_event_loop().run_until_complete(coro)  # type: ignore[misc]
    except RuntimeError:
        _ = None
    return _asyncio.run(coro)


import pytest

@pytest.fixture
def authnz_schema_ready_sync():
    """Sync-friendly variant to ensure AuthNZ schema for SQLite tests.

    Use in synchronous tests that set DATABASE_URL and need AuthNZ tables.
    """
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings as _reset_settings
        from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool as _reset_db_pool
        _run_async(_reset_db_pool())
        _reset_settings()
    except Exception:
        _ = None
    try:
        from tldw_Server_API.app.core.AuthNZ.initialize import ensure_authnz_schema_ready_once as _ensure_once
        _run_async(_ensure_once())
    except Exception:
        _ = None
    return None
