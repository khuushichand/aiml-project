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
            pass
