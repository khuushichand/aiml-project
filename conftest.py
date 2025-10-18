from __future__ import annotations

import os
import pytest_asyncio


@pytest_asyncio.fixture
async def real_audit_service(tmp_path):
    """Re-export of the AuthNZ real_audit_service fixture for sibling test trees.

    Sets USER_DB_BASE_DIR to a per-test tmp directory and resets settings so
    audit DBs are isolated. Shuts down audit services after the test.
    """
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings as _reset_settings
    from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import (
        shutdown_all_audit_services as _shutdown_all,
    )

    os.environ["USER_DB_BASE_DIR"] = str((tmp_path / "user_databases").resolve())
    _reset_settings()
    try:
        yield
    finally:
        try:
            await _shutdown_all()
        except Exception:
            pass

