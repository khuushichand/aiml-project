# conftest.py
# Pytest configuration for Prompt Studio tests

import os
import tempfile
from pathlib import Path
import uuid
from unittest.mock import patch
import importlib

import pytest
from fastapi.testclient import TestClient
from typing import Any

# Prompt Studio routes are not included in minimal test app mode.
os.environ["MINIMAL_TEST_APP"] = "0"
# Ensure test flags are set before loading the app module.
os.environ["TEST_MODE"] = "true"
os.environ["AUTH_MODE"] = "single_user"
os.environ["CSRF_ENABLED"] = "false"

import tldw_Server_API.app.main as main_mod

if getattr(main_mod, "_MINIMAL_TEST_APP", True):
    main_mod = importlib.reload(main_mod)
fastapi_app = main_mod.app
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import get_prompt_studio_db
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

# Environment variables already set before app import above.

# Postgres setup is unified via tests._plugins.postgres.

@pytest.fixture(autouse=True)
def enable_test_mode(monkeypatch):
    """Enable test mode for all tests"""
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("CSRF_ENABLED", "false")

@pytest.fixture
def mock_current_user():
    """Mock user for authentication"""
    return {
        "id": "test-user-123",
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True,
        "is_authenticated": True
    }

@pytest.fixture(autouse=True)
def mock_auth_dependency(mock_current_user):
    """Automatically mock authentication for all tests"""
    with patch('tldw_Server_API.app.api.v1.API_Deps.auth_deps.get_current_user') as mock_get_user:
        mock_get_user.return_value = mock_current_user
        with patch('tldw_Server_API.app.api.v1.API_Deps.auth_deps.get_current_active_user') as mock_active:
            mock_active.return_value = mock_current_user
            yield

@pytest.fixture(scope="session")
def test_db_path():
    """Session-scoped test database path"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_prompt_studio.db"
        yield str(db_path)

@pytest.fixture
def isolated_db(test_db_path):
    """Isolated database for each test"""
    import uuid

    unique_path = f"{test_db_path}_{uuid.uuid4()}.db"
    db = PromptStudioDatabase(unique_path, "test-client")

    yield db

    if hasattr(db, "close"):
        try:
            db.close()
        except Exception:
            pass

    if os.path.exists(unique_path):
        os.unlink(unique_path)

@pytest.fixture
def auth_headers():
    """Authentication headers for API tests"""
    return {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json"
    }


@pytest.fixture(params=["sqlite", "postgres"])
def prompt_studio_dual_backend_db(request, tmp_path):
    """Provide a PromptStudioDatabase instance configured for the requested backend."""

    label: str = request.param
    backend = None

    if label == "sqlite":
        db_path = tmp_path / f"prompt_studio_{label}.sqlite"
        db_instance = PromptStudioDatabase(str(db_path), f"dual-{label}")
    else:
        # Use unified pg temp database fixture (lazy to avoid resolving when running sqlite branch)
        config: DatabaseConfig = request.getfixturevalue("pg_database_config")
        backend = DatabaseBackendFactory.create_backend(config)
        db_instance = PromptStudioDatabase(
            db_path=str(tmp_path / "prompt_studio_pg_placeholder.sqlite"),
            client_id="dual-postgres",
            backend=backend,
        )

    try:
        yield label, db_instance
    finally:
        if hasattr(db_instance, "close"):
            try:
                db_instance.close()
            except Exception:
                pass
        elif hasattr(db_instance, "close_connection"):
            try:
                db_instance.close_connection()
            except Exception:
                pass

        if backend is not None:
            try:
                backend.get_pool().close_all()
            except Exception:
                pass
        # No explicit drop needed; pg_database_config fixture handles DB cleanup


@pytest.fixture
def prompt_studio_dual_backend_client(
    prompt_studio_dual_backend_db,
    mock_current_user,
    tmp_path,
    monkeypatch,
):
    """Yield a FastAPI TestClient wired to the selected Prompt Studio backend."""

    from tldw_Server_API.app.core.config import settings as app_settings
    # Patch prompt_studio_deps.get_current_active_user directly; dependency_overrides
    # on auth_deps does not affect this symbol.
    from tldw_Server_API.app.api.v1.API_Deps import prompt_studio_deps as ps_deps

    backend_label, db_instance = prompt_studio_dual_backend_db

    monkeypatch.setitem(app_settings, "USER_DB_BASE_DIR", tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")

    async def override_user():
        return User(
            id=mock_current_user.get("id", "test-user-123"),
            username=mock_current_user.get("username", "testuser"),
            email=mock_current_user.get("email", "test@example.com"),
            is_active=True,
        )

    async def override_db():
        return db_instance

    _app: Any = fastapi_app  # appease static analyzers about dynamic attributes
    _app.dependency_overrides[get_request_user] = override_user
    _app.dependency_overrides[get_prompt_studio_db] = override_db
    # get_prompt_studio_user calls ps_deps.get_current_active_user directly; patch it
    monkeypatch.setattr(ps_deps, "get_current_active_user", lambda: mock_current_user, raising=False)

    try:
        with TestClient(_app) as client:
            yield backend_label, client, db_instance
    finally:
        _app.dependency_overrides.clear()
        monkeypatch.delenv("TEST_MODE", raising=False)
