"""UserProfile test-local fixtures.

These tests open the full FastAPI lifespan repeatedly via ``TestClient``.
To avoid coupling to a mutable repository-level ``Databases/users.db`` file,
force AuthNZ to use an isolated temporary SQLite database path for this
subsuite on every test.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _run_async(coro):
    """Run async setup/teardown hooks from sync pytest fixtures."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return None
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@pytest.fixture(scope="session")
def _user_profile_authnz_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_dir = tmp_path_factory.mktemp("user_profile_authnz")
    return db_dir / "users.db"


@pytest.fixture(autouse=True)
def _isolate_user_profile_authnz_db(
    monkeypatch: pytest.MonkeyPatch,
    _user_profile_authnz_db_path: Path,
):
    """Pin AuthNZ settings to an isolated SQLite DB for UserProfile tests."""
    db_url = f"sqlite:///{_user_profile_authnz_db_path}"
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("DATABASE_URL", db_url)

    try:
        from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
        from tldw_Server_API.app.core.AuthNZ.initialize import ensure_authnz_schema_ready_once
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
        from tldw_Server_API.app.core.config import clear_config_cache

        _run_async(reset_db_pool())
        reset_settings()
        clear_config_cache()
        _run_async(ensure_authnz_schema_ready_once())
    except Exception:
        # Best-effort fixture; endpoint tests assert behavior directly.
        _ = None

    yield

    try:
        from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
        from tldw_Server_API.app.core.config import clear_config_cache

        _run_async(reset_db_pool())
        reset_settings()
        clear_config_cache()
    except Exception:
        _ = None
