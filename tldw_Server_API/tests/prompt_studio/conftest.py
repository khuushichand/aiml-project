# conftest.py
# Pytest configuration for Prompt Studio tests

import os
import tempfile
from pathlib import Path
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from typing import Any

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.api.v1.API_Deps.prompt_studio_deps import get_prompt_studio_db
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

# Set test environment variables
os.environ["TEST_MODE"] = "true"
os.environ["AUTH_MODE"] = "single_user"
os.environ["CSRF_ENABLED"] = "false"

try:  # Postgres optional dependency for dual-backend runs (prefer psycopg v3)
    import psycopg as _psycopg_v3  # type: ignore
    _PG_DRIVER = "psycopg"
except ImportError:  # pragma: no cover - handled by skip marker
    try:
        import psycopg2 as _psycopg2  # type: ignore
        _PG_DRIVER = "psycopg2"
    except Exception:
        _PG_DRIVER = None

_POSTGRES_ENV_VARS = (
    "POSTGRES_TEST_HOST",
    "POSTGRES_TEST_PORT",
    "POSTGRES_TEST_DB",
    "POSTGRES_TEST_USER",
    "POSTGRES_TEST_PASSWORD",
)

_HAS_POSTGRES = (_PG_DRIVER is not None)


def _build_postgres_config() -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.environ["POSTGRES_TEST_HOST"],
        pg_port=int(os.environ["POSTGRES_TEST_PORT"]),
        pg_database=os.environ["POSTGRES_TEST_DB"],
        pg_user=os.environ["POSTGRES_TEST_USER"],
        pg_password=os.environ["POSTGRES_TEST_PASSWORD"],
    )


def _probe_postgres(config: DatabaseConfig, timeout: int = 2) -> bool:
    """Quickly check if Postgres is reachable with a short timeout.

    Attempts a lightweight connection to the default 'postgres' DB using
    provided host/port/user/password. Returns False on any exception.
    """
    if _PG_DRIVER is None:
        return False

    try:
        if _PG_DRIVER == "psycopg":
            conn = _psycopg_v3.connect(
                host=config.pg_host,
                port=config.pg_port,
                dbname="postgres",
                user=config.pg_user,
                password=config.pg_password,
                connect_timeout=timeout,
            )
        else:
            conn = _psycopg2.connect(
                host=config.pg_host,
                port=config.pg_port,
                database="postgres",
                user=config.pg_user,
                password=config.pg_password,
                connect_timeout=timeout,
            )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        return True
    except Exception:
        return False


def _create_temp_postgres_database(config: DatabaseConfig) -> DatabaseConfig:
    if _PG_DRIVER is None:  # pragma: no cover - guarded by skip
        raise RuntimeError("psycopg (or psycopg2) is required for Postgres-backed tests")

    db_name = f"tldw_test_{uuid.uuid4().hex[:8]}"
    if _PG_DRIVER == "psycopg":
        admin = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    else:
        admin = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(f"CREATE DATABASE {db_name} OWNER {config.pg_user};")
    finally:
        admin.close()

    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=config.pg_host,
        pg_port=config.pg_port,
        pg_database=db_name,
        pg_user=config.pg_user,
        pg_password=config.pg_password,
    )


def _drop_postgres_database(config: DatabaseConfig) -> None:
    if _PG_DRIVER is None:  # pragma: no cover
        return
    if _PG_DRIVER == "psycopg":
        admin = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    else:
        admin = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
            connect_timeout=2,
        )
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                (config.pg_database,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {config.pg_database};")
    finally:
        admin.close()

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
        # Skip quickly if Postgres driver is missing
        if not _HAS_POSTGRES:
            pytest.skip("psycopg not available; skipping Postgres backend")

        base_config = DatabaseConfig(
            backend_type=BackendType.POSTGRESQL,
            pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
            pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
            pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
            pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
            pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
        )
        # Fast availability probe with 2s timeout
        if not _probe_postgres(base_config, timeout=2):
            # Allow CI to require Postgres explicitly so we fail fast instead of silently skipping
            if os.getenv("TLDW_TEST_POSTGRES_REQUIRED", "0").lower() in {"1", "true", "yes", "on"}:
                pytest.fail("Postgres required for tests but not reachable")
            pytest.skip("Postgres not reachable; skipping Postgres backend")
        config = _create_temp_postgres_database(base_config)
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
        if label == "postgres":
            try:
                _drop_postgres_database(config)  # type: ignore[name-defined]
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
