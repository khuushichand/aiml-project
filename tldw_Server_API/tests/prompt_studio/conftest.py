# conftest.py
# Pytest configuration for Prompt Studio tests

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import get_prompt_studio_db
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

# Set test environment variables
os.environ["TEST_MODE"] = "true"
os.environ["AUTH_MODE"] = "single_user"
os.environ["CSRF_ENABLED"] = "false"

try:  # Postgres optional dependency for dual-backend runs
    import psycopg2  # type: ignore
except ImportError:  # pragma: no cover - handled by skip marker
    psycopg2 = None

_POSTGRES_ENV_VARS = (
    "POSTGRES_TEST_HOST",
    "POSTGRES_TEST_PORT",
    "POSTGRES_TEST_DB",
    "POSTGRES_TEST_USER",
    "POSTGRES_TEST_PASSWORD",
)

_HAS_POSTGRES = psycopg2 is not None and all(env in os.environ for env in _POSTGRES_ENV_VARS)


def _build_postgres_config() -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.environ["POSTGRES_TEST_HOST"],
        pg_port=int(os.environ["POSTGRES_TEST_PORT"]),
        pg_database=os.environ["POSTGRES_TEST_DB"],
        pg_user=os.environ["POSTGRES_TEST_USER"],
        pg_password=os.environ["POSTGRES_TEST_PASSWORD"],
    )


def _reset_postgres_database(config: DatabaseConfig) -> None:
    if psycopg2 is None:  # pragma: no cover - guarded by skip
        raise RuntimeError("psycopg2 is required for Postgres-backed tests")

    conn = psycopg2.connect(
        host=config.pg_host,
        port=config.pg_port,
        database=config.pg_database,
        user=config.pg_user,
        password=config.pg_password,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        conn.close()

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


@pytest.fixture(params=[
    "sqlite",
    pytest.param("postgres", marks=pytest.mark.skipif(not _HAS_POSTGRES, reason="Postgres fixtures unavailable")),
])
def prompt_studio_dual_backend_db(request, tmp_path):
    """Provide a PromptStudioDatabase instance configured for the requested backend."""

    label: str = request.param
    backend = None

    if label == "sqlite":
        db_path = tmp_path / f"prompt_studio_{label}.sqlite"
        db_instance = PromptStudioDatabase(str(db_path), f"dual-{label}")
    else:
        config = _build_postgres_config()
        _reset_postgres_database(config)
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


@pytest.fixture
def prompt_studio_dual_backend_client(
    prompt_studio_dual_backend_db,
    mock_current_user,
    tmp_path,
    monkeypatch,
):
    """Yield a FastAPI TestClient wired to the selected Prompt Studio backend."""

    from tldw_Server_API.app.core import config as cfg

    backend_label, db_instance = prompt_studio_dual_backend_db

    monkeypatch.setitem(cfg.settings, "USER_DB_BASE_DIR", tmp_path)
    monkeypatch.setenv("TEST_MODE", "true")

    async def override_user():
        return User(
            id=mock_current_user.get("id", "test-user-123"),
            username=mock_current_user.get("username", "testuser"),
            email=mock_current_user.get("email", "test@example.com"),
            is_active=True,
            is_admin=True,
        )

    async def override_db():
        return db_instance

    app.dependency_overrides[get_request_user] = override_user
    app.dependency_overrides[get_current_active_user] = lambda: mock_current_user
    app.dependency_overrides[get_prompt_studio_db] = override_db

    try:
        with TestClient(app) as client:
            yield backend_label, client, db_instance
    finally:
        app.dependency_overrides.clear()
        monkeypatch.delenv("TEST_MODE", raising=False)
