"""
Shared fixtures and configuration for AuthNZ tests.
Provides PostgreSQL test database isolation with transaction rollback.
"""

import os
import shutil
import subprocess
import pytest
import pytest_asyncio
import asyncio
import uuid
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, AsyncGenerator, Optional
from unittest.mock import Mock, AsyncMock, MagicMock

import asyncpg
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import Settings
from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
from tldw_Server_API.app.services.registration_service import RegistrationService
from tldw_Server_API.app.core.Audit.unified_audit_service import UnifiedAuditService
from tldw_Server_API.app.services.storage_quota_service import StorageQuotaService
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.AuthNZ.scheduler import reset_authnz_scheduler
from tldw_Server_API.app.core.AuthNZ.token_blacklist import reset_token_blacklist
from tldw_Server_API.app.core.AuthNZ.alerting import reset_security_alert_dispatcher

# Test database configuration
# Allow a full Postgres DSN to configure tests easily
_TEST_DSN = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
_TEST_DSN = _TEST_DSN.strip()

def _parse_pg_dsn(dsn: str):
    try:
        from urllib.parse import urlparse
        parsed = urlparse(dsn)
        if not parsed.scheme.startswith("postgres"):
            return None
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 5432)
        user = parsed.username or "tldw_user"
        password = parsed.password or "TestPassword123!"
        db = (parsed.path or "/tldw_test").lstrip("/") or "tldw_test"
        return {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "db": db,
        }
    except Exception:
        return None

_parsed = _parse_pg_dsn(_TEST_DSN) if _TEST_DSN else None

TEST_DB_NAME = (_parsed or {}).get("db") or os.getenv("TEST_DB_NAME", "tldw_test")
TEST_DB_HOST = (_parsed or {}).get("host") or os.getenv("TEST_DB_HOST", "localhost")
TEST_DB_PORT = int(((_parsed or {}).get("port")) or int(os.getenv("TEST_DB_PORT", "5432")))
TEST_DB_USER = (_parsed or {}).get("user") or os.getenv("TEST_DB_USER", "tldw_user")
TEST_DB_PASSWORD = (_parsed or {}).get("password") or os.getenv("TEST_DB_PASSWORD", "TestPassword123!")

# Import TestClient for isolated environment
from fastapi.testclient import TestClient



class _StubAuditService:
    """No-op audit service used in TEST_MODE to avoid background tasks."""
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def initialize(self) -> None:
        return None

    async def log_event(self, *args, **kwargs) -> None:
        return None

    async def log_login(self, *args, **kwargs) -> None:
        return None

    async def shutdown(self) -> None:
        return None


class _StubPersonalizationDB:
    """No-op personalization DB used to avoid filesystem writes in tests."""

    def insert_usage_event(self, *args, **kwargs):
        return None

    def __getattr__(self, item):
        # Allow any other method calls without side effects
        def _noop(*_args, **_kwargs):
            return None
        return _noop


async def _can_connect_postgres(host: str, port: int, user: str, password: str, database: str = "postgres") -> bool:
    try:
        conn = await asyncpg.connect(host=host, port=port, user=user, password=password, database=database)
        await conn.close()
        return True
    except Exception as e:
        logger.debug(f"Postgres connectivity check failed: {e}")
        return False


async def _ensure_postgres_available(host: str, port: int, user: str, password: str, *, require_pg: bool, default_db: str = "postgres") -> bool:
    """Try to connect; if not available and local, attempt to start docker, then retry.

    Returns True if Postgres becomes reachable; otherwise False (caller may skip tests).
    """
    if await _can_connect_postgres(host, port, user, password, default_db):
        return True

    # Only attempt Docker on local hostnames
    if str(host) not in {"localhost", "127.0.0.1", "::1"}:
        return False

    if os.getenv("TLDW_TEST_NO_DOCKER", "").lower() in ("1", "true", "yes"):
        return False

    docker_bin = shutil.which("docker")
    if not docker_bin:
        logger.info("Docker not found in PATH; cannot auto-start Postgres for tests")
        return False

    image = os.getenv("TLDW_TEST_PG_IMAGE", "postgres:18")
    container = os.getenv("TLDW_TEST_PG_CONTAINER_NAME", "tldw_postgres_test")

    # Stop and remove an existing container with same name (best-effort)
    try:
        await asyncio.to_thread(subprocess.run, [docker_bin, "rm", "-f", container], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    envs = [
        "-e", f"POSTGRES_USER={user}",
        "-e", f"POSTGRES_PASSWORD={password}",
        # Create a default DB; per-test DBs will be created later as needed
        "-e", f"POSTGRES_DB={default_db}",
    ]
    ports = ["-p", f"{port}:5432"]

    run_cmd = [docker_bin, "run", "-d", "--name", container, *envs, *ports, image]
    logger.info(f"Attempting to start Postgres test container: {' '.join(run_cmd)}")
    try:
        res = await asyncio.to_thread(subprocess.run, run_cmd, check=False, capture_output=True, text=True)
        if res.returncode != 0:
            logger.warning(f"Docker run failed (code {res.returncode}): {res.stderr.strip()}")
            # If container already running under same name, try to reuse without starting
    except Exception as e:
        logger.warning(f"Failed to start Docker Postgres: {e}")
        return False

    # Wait up to ~30 seconds for readiness, trying to connect
    for _ in range(30):
        if await _can_connect_postgres(host, port, user, password, default_db):
            logger.info("Postgres became reachable after docker start")
            return True
        await asyncio.sleep(1)

    logger.warning("Postgres did not become reachable after docker start attempts")
    return False


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def reset_singletons(request):
    """Auto-reset all singletons before and after each test for clean state."""
    # No session-wide default DB. Tests must use isolated DB fixtures or mocks.
    # Reset before test
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.services.registration_service import reset_registration_service
    from tldw_Server_API.app.core.Audit.unified_audit_service import shutdown_audit_service
    from tldw_Server_API.app.core.AuthNZ.jwt_service import reset_jwt_service
    from tldw_Server_API.app.core.AuthNZ.api_key_manager import reset_api_key_manager
    from tldw_Server_API.app.core.DB_Management.Users_DB import reset_users_db
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import close_all_chacha_db_instances

    # Disable CSRF protection for tests
    original_csrf_setting = settings.get('CSRF_ENABLED')
    settings['CSRF_ENABLED'] = False

    close_all_chacha_db_instances()

    await reset_db_pool()
    await reset_session_manager()
    await reset_token_blacklist()
    await reset_security_alert_dispatcher()
    await reset_authnz_scheduler()
    reset_settings()
    reset_jwt_service()
    await reset_registration_service()
    await shutdown_audit_service()
    await reset_api_key_manager()
    await reset_users_db()

    # Clear any FastAPI dependency overrides and stub audit unless real audit requested
    try:
        from tldw_Server_API.app.main import app as _app
        _app.dependency_overrides.clear()
        # In TEST_MODE, stub audit service to avoid background task group errors
        try:
            from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
            from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import (
                get_personalization_db_for_user,
                get_usage_event_logger,
                UsageEventLogger,
            )

            async def _override_audit_dep(current_user=None):
                return _StubAuditService()

            def _override_personalization_db(current_user=None):
                return None

            def _override_usage_logger(request=None, user=None, db=None):
                return UsageEventLogger(user_id=str(getattr(user, "id", "test")), db=_StubPersonalizationDB())

            if not request.node.get_closest_marker("real_audit"):
                _app.dependency_overrides[get_audit_service_for_user] = _override_audit_dep
                _app.dependency_overrides[get_personalization_db_for_user] = _override_personalization_db
                _app.dependency_overrides[get_usage_event_logger] = _override_usage_logger
        except Exception:
            # If import fails here, tests that don't hit audit won't care
            pass

        # Also, in TEST_MODE, strip non-essential middlewares that may perform
        # background DB work after response (to avoid TaskGroup noise in full runs)
        try:
            from tldw_Server_API.app.core.Metrics.http_middleware import HTTPMetricsMiddleware as _HTTPMM
            from tldw_Server_API.app.core.Security.middleware import SecurityHeadersMiddleware as _SHM
            from tldw_Server_API.app.core.Security.request_id_middleware import RequestIDMiddleware as _RID
            kept = []
            for m in getattr(_app, 'user_middleware', []):
                if getattr(m, 'cls', None) in (_HTTPMM, _SHM, _RID):
                    continue
                kept.append(m)
            if len(kept) != len(getattr(_app, 'user_middleware', [])):
                _app.user_middleware = kept
                # Rebuild the Starlette middleware stack
                _app.middleware_stack = _app.build_middleware_stack()
        except Exception:
            pass
    except Exception:
        pass

    yield

    # Reset after test
    await reset_db_pool()
    await reset_session_manager()
    await reset_token_blacklist()
    await reset_security_alert_dispatcher()
    await reset_authnz_scheduler()
    reset_settings()
    reset_jwt_service()
    await reset_registration_service()
    await shutdown_audit_service()
    await reset_api_key_manager()
    await reset_users_db()
    try:
        close_all_chacha_db_instances()
    except Exception:
        pass
    try:
        from tldw_Server_API.app.main import app as _app
        _app.dependency_overrides.clear()
    except Exception:
        pass

    # Restore original CSRF setting
    if original_csrf_setting is not None:
        settings['CSRF_ENABLED'] = original_csrf_setting
    else:
        settings.pop('CSRF_ENABLED', None)


@pytest_asyncio.fixture
async def real_audit_service(tmp_path):
    """Enable real UnifiedAuditService for this test and isolate per-user DBs.

    - Sets USER_DB_BASE_DIR to a per-test tmp directory
    - Resets settings so config picks up new base dir
    - Ensures audit services are shut down after the test
    """
    import os as _os
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings as _reset_settings
    from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import shutdown_all_audit_services as _shutdown_all

    _os.environ['USER_DB_BASE_DIR'] = str((tmp_path / 'user_databases').resolve())
    _reset_settings()
    try:
        yield
    finally:
        try:
            await _shutdown_all()
        except Exception:
            pass


@pytest_asyncio.fixture
async def isolated_test_environment(monkeypatch):
    """Create isolated DB and app instance for each test - TRUE ONE DB PER TEST."""
    import uuid as uuid_lib

    # Disable CSRF protection for tests
    settings['CSRF_ENABLED'] = False

    # 1. Generate unique DB name for this test
    db_name = f"tldw_test_{uuid_lib.uuid4().hex[:8]}"
    logger.info(f"Creating isolated test database: {db_name}")

    # 2. Create the unique database (skip gracefully if Postgres is unavailable and not required)
    require_pg = os.getenv("TLDW_TEST_POSTGRES_REQUIRED", "").lower() in ("1", "true", "yes")
    # Ensure Postgres is reachable, optionally starting a local dockerized instance
    ok = await _ensure_postgres_available(TEST_DB_HOST, TEST_DB_PORT, TEST_DB_USER, TEST_DB_PASSWORD, require_pg=require_pg, default_db="postgres")
    if not ok:
        if not require_pg:
            import pytest as _pytest
            _pytest.skip("PostgreSQL not available; attempted docker start; skipping AuthNZ integration tests. Set TLDW_TEST_POSTGRES_REQUIRED=1 to enforce.")
        raise RuntimeError("PostgreSQL not available and docker start failed under TLDW_TEST_POSTGRES_REQUIRED=1")
    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database="postgres"
    )

    try:
        # Drop if exists (cleanup from failed tests)
        await conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
        """)
        await conn.execute(f"DROP DATABASE IF EXISTS {db_name}")

        # Create new database
        await conn.execute(f"CREATE DATABASE {db_name}")
        logger.info(f"Created test database: {db_name}")
    finally:
        await conn.close()

    # 3. Create schema in the new database
    test_conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=db_name
    )

    try:
        await test_conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        # Create all required tables
        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                uuid UUID UNIQUE NOT NULL,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                is_superuser BOOLEAN DEFAULT FALSE,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                storage_quota_mb INTEGER DEFAULT 5120,
                storage_used_mb FLOAT DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                email_verified_at TIMESTAMP,
                two_factor_enabled BOOLEAN DEFAULT FALSE,
                two_factor_secret TEXT,
                created_by INTEGER REFERENCES users(id),
                password_changed_at TIMESTAMP
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT UNIQUE NOT NULL,
                refresh_token_hash TEXT UNIQUE,
                encrypted_token TEXT,
                encrypted_refresh TEXT,
                expires_at TIMESTAMP NOT NULL,
                refresh_expires_at TIMESTAMP,
                access_jti VARCHAR(255),
                refresh_jti VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent TEXT,
                device_id VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                is_revoked BOOLEAN DEFAULT FALSE,
                revoked_at TIMESTAMP,
                revoked_by INTEGER REFERENCES users(id),
                revoke_reason TEXT
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS password_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                is_system BOOLEAN DEFAULT FALSE
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key_hash VARCHAR(64) UNIQUE NOT NULL,
                key_prefix VARCHAR(16) NOT NULL,
                name VARCHAR(255),
                description TEXT,
                scope VARCHAR(50) DEFAULT 'read',
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used_at TIMESTAMP,
                last_used_ip VARCHAR(45),
                usage_count INTEGER DEFAULT 0,
                rate_limit INTEGER,
                allowed_ips TEXT,
                metadata JSONB,
                rotated_from INTEGER REFERENCES api_keys(id),
                rotated_to INTEGER REFERENCES api_keys(id),
                revoked_at TIMESTAMP,
                revoked_by INTEGER,
                revoke_reason TEXT,
                is_virtual BOOLEAN DEFAULT FALSE,
                parent_key_id INTEGER REFERENCES api_keys(id),
                org_id INTEGER,
                team_id INTEGER,
                llm_budget_day_tokens BIGINT,
                llm_budget_month_tokens BIGINT,
                llm_budget_day_usd DOUBLE PRECISION,
                llm_budget_month_usd DOUBLE PRECISION,
                llm_allowed_endpoints TEXT,
                llm_allowed_providers TEXT,
                llm_allowed_models TEXT
            )
        """)
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)")

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS registration_codes (
                id SERIAL PRIMARY KEY,
                code VARCHAR(255) UNIQUE NOT NULL,
                max_uses INTEGER DEFAULT 1,
                times_used INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role_to_grant VARCHAR(50) DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB,
                role_id INTEGER REFERENCES roles(id)
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action VARCHAR(255) NOT NULL,
                target_type VARCHAR(100),
                target_id INTEGER,
                success BOOLEAN DEFAULT TRUE,
                details TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # RBAC core tables (minimal for tests)
        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                is_system BOOLEAN DEFAULT FALSE
            )
        """)
        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS permissions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                category VARCHAR(100)
            )
        """)
        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS role_permissions (
                role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
                UNIQUE(role_id, permission_id)
            )
        """)
        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
                UNIQUE(user_id, role_id)
            )
        """)

        # Create indexes
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)")

        # Seed minimal roles expected by tests
        await test_conn.execute("""
            INSERT INTO roles (name, description, is_system) VALUES
            ('admin','Administrator', TRUE)
            ON CONFLICT (name) DO NOTHING
        """)
        await test_conn.execute("""
            INSERT INTO roles (name, description, is_system) VALUES
            ('user','Standard user', TRUE)
            ON CONFLICT (name) DO NOTHING
        """)

        logger.info(f"Created schema in test database: {db_name}")
    finally:
        await test_conn.close()

    # 4. Set environment variables for this test
    db_url = f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{db_name}"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-testing-only")
    monkeypatch.setenv("ENABLE_REGISTRATION", "true")
    monkeypatch.setenv("REQUIRE_REGISTRATION_CODE", "false")
    monkeypatch.setenv("EMAIL_VERIFICATION_REQUIRED", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", "1")

    # 5. Reset ALL singletons to force fresh initialization with new DB
    from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.session_manager import reset_session_manager
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.services.registration_service import reset_registration_service
    from tldw_Server_API.app.core.Audit.unified_audit_service import shutdown_audit_service

    await reset_db_pool()
    await reset_session_manager()
    reset_settings()
    await reset_registration_service()
    await shutdown_audit_service()

    # 5.1 Skip forcing a DatabasePool into the app to avoid cross-event-loop issues.
    #     Let the FastAPI app create its own pool within its own loop when handling requests.
    # 5.2 We already created the minimal schema required for registration/login above.
    #     Avoid calling module bootstrap that could prime a global pool on the fixture loop.

    # 7. Create TestClient (DB exists, singletons reset, env vars set)
    from tldw_Server_API.app.main import app as _app
    # Diagnostics: verify settings and DB URL are pointing to our per-test DB
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import get_settings as _get_settings
        _s = _get_settings()
        logger.info(f"AuthNZ test fixture DB URL: {_s.DATABASE_URL}")
        logger.info(f"AuthNZ mode: {_s.AUTH_MODE} | CSRF_ENABLED={settings.get('CSRF_ENABLED')}")
    except Exception as _diag_e:
        logger.warning(f"AuthNZ test fixture diagnostics failed: {_diag_e}")
    with TestClient(_app) as client:
        yield client, db_name

    # 8. Cleanup: reset singletons again
    await reset_db_pool()
    await reset_session_manager()
    await reset_token_blacklist()
    await reset_authnz_scheduler()
    reset_settings()
    await reset_registration_service()
    await shutdown_audit_service()

    # 9. Drop the unique database
    cleanup_conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database="postgres"
    )

    try:
        await cleanup_conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
        """)
        await cleanup_conn.execute(f"DROP DATABASE IF EXISTS {db_name}")
        logger.info(f"Dropped test database: {db_name}")
    finally:
        await cleanup_conn.close()

    # Re-enable CSRF protection after test
    settings.pop('CSRF_ENABLED', None)


@pytest_asyncio.fixture
async def setup_test_database(monkeypatch):
    """Create and setup the test database for the test session."""
    # Ensure FastAPI + core settings pick Postgres for this test DB
    require_pg = os.getenv("TLDW_TEST_POSTGRES_REQUIRED", "").lower() in ("1", "true", "yes")
    test_dsn = f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"
    monkeypatch.setenv("DATABASE_URL", test_dsn)
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings as _reset_settings
        from tldw_Server_API.app.core.AuthNZ.database import reset_db_pool as _reset_db_pool
        _reset_settings()
        # Reset any pre-existing pool so app endpoints use Postgres on first access
        # (some tests hit endpoints that call get_db_pool inside request handlers)
        await _reset_db_pool()
    except Exception:
        pass
    # Ensure Postgres reachable before creating the session DB
    ok = await _ensure_postgres_available(TEST_DB_HOST, TEST_DB_PORT, TEST_DB_USER, TEST_DB_PASSWORD, require_pg=require_pg, default_db="postgres")
    if not ok:
        if not require_pg:
            import pytest as _pytest
            _pytest.skip("PostgreSQL not available; attempted docker start; skipping AuthNZ Postgres-backed tests. Set TLDW_TEST_POSTGRES_REQUIRED=1 to enforce.")
        raise RuntimeError("PostgreSQL not available and docker start failed under TLDW_TEST_POSTGRES_REQUIRED=1")
    # Connect to postgres database to create test database
    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database="postgres"
    )

    try:
        # Drop test database if it exists
        await conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()
        """)
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")

        # Create test database
        await conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        logger.info(f"Created test database: {TEST_DB_NAME}")

    finally:
        await conn.close()

    # Connect to test database and create base minimal schema (core tables)
    test_conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=TEST_DB_NAME
    )

    try:
        await test_conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        # Create tables
        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                uuid UUID UNIQUE NOT NULL,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                is_verified BOOLEAN DEFAULT FALSE,
                is_superuser BOOLEAN DEFAULT FALSE,
                failed_login_attempts INTEGER DEFAULT 0,
                locked_until TIMESTAMP,
                storage_quota_mb INTEGER DEFAULT 5120,
                storage_used_mb FLOAT DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                email_verified_at TIMESTAMP,
                two_factor_enabled BOOLEAN DEFAULT FALSE,
                two_factor_secret TEXT,
                created_by INTEGER REFERENCES users(id),
                password_changed_at TIMESTAMP
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash TEXT UNIQUE NOT NULL,
                refresh_token_hash TEXT UNIQUE,
                encrypted_token TEXT,
                encrypted_refresh TEXT,
                expires_at TIMESTAMP NOT NULL,
                refresh_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address VARCHAR(45),
                user_agent TEXT,
                device_id VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                is_revoked BOOLEAN DEFAULT FALSE,
                revoked_at TIMESTAMP,
                revoked_by INTEGER REFERENCES users(id),
                revoke_reason TEXT,
                access_jti VARCHAR(255),
                refresh_jti VARCHAR(255)
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS password_history (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                is_system BOOLEAN DEFAULT FALSE
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key_hash VARCHAR(64) UNIQUE NOT NULL,
                key_prefix VARCHAR(16) NOT NULL,
                name VARCHAR(255),
                description TEXT,
                scope VARCHAR(50) DEFAULT 'read',
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                last_used_at TIMESTAMP,
                last_used_ip VARCHAR(45),
                usage_count INTEGER DEFAULT 0,
                rate_limit INTEGER,
                allowed_ips TEXT,
                metadata JSONB,
                rotated_from INTEGER REFERENCES api_keys(id),
                rotated_to INTEGER REFERENCES api_keys(id),
                revoked_at TIMESTAMP,
                revoked_by INTEGER,
                revoke_reason TEXT,
                is_virtual BOOLEAN DEFAULT FALSE,
                parent_key_id INTEGER REFERENCES api_keys(id),
                org_id INTEGER,
                team_id INTEGER,
                llm_budget_day_tokens BIGINT,
                llm_budget_month_tokens BIGINT,
                llm_budget_day_usd DOUBLE PRECISION,
                llm_budget_month_usd DOUBLE PRECISION,
                llm_allowed_endpoints TEXT,
                llm_allowed_providers TEXT,
                llm_allowed_models TEXT
            )
        """)
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_status ON api_keys(status)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_expires_at ON api_keys(expires_at)")

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS registration_codes (
                id SERIAL PRIMARY KEY,
                code VARCHAR(255) UNIQUE NOT NULL,
                max_uses INTEGER DEFAULT 1,
                times_used INTEGER DEFAULT 0,
                expires_at TIMESTAMP,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                role_to_grant VARCHAR(50) DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                metadata JSONB,
                role_id INTEGER REFERENCES roles(id)
            )
        """)

        await test_conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action VARCHAR(255) NOT NULL,
                target_type VARCHAR(100),
                target_id INTEGER,
                success BOOLEAN DEFAULT TRUE,
                details TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash)")
        await test_conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id)")

        logger.info("Created test database schema")

    finally:
        await test_conn.close()

    # Also run the AuthNZ module's Postgres bootstrap to ensure full schema parity
    # (sessions, registration_codes, RBAC, API keys, usage tables, etc.)
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}")
    monkeypatch.setenv("JWT_SECRET_KEY", os.environ.get("JWT_SECRET_KEY", "test-secret-key-for-testing-only"))
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.setenv("AUTHNZ_FORCE_REAL_SESSION_MANAGER", "1")
    try:
        from tldw_Server_API.app.core.AuthNZ.initialize import setup_database as _authnz_setup_db
        await _authnz_setup_db()
        logger.info("AuthNZ Postgres schema bootstrap completed for session test DB")
    except Exception as exc:
        logger.exception(f"AuthNZ schema bootstrap failed in setup_test_database: {exc}")

    yield

    # Cleanup: Drop test database after all tests
    cleanup_conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database="postgres"
    )

    try:
        await cleanup_conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()
        """)
        await cleanup_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        logger.info(f"Dropped test database: {TEST_DB_NAME}")
    finally:
        await cleanup_conn.close()


@pytest_asyncio.fixture(scope="function")
async def clean_database(setup_test_database):
    """Ensure database is clean before each test."""
    conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=TEST_DB_NAME
    )

    try:
        # Clean all tables in correct order (respecting foreign keys)
        await conn.execute("TRUNCATE TABLE audit_log CASCADE")
        await conn.execute("TRUNCATE TABLE registration_codes CASCADE")
        await conn.execute("TRUNCATE TABLE password_history CASCADE")
        await conn.execute("TRUNCATE TABLE sessions CASCADE")
        await conn.execute("TRUNCATE TABLE users CASCADE")

        logger.debug("Cleaned test database tables")
    finally:
        await conn.close()

    yield

    # Clean up after test
    cleanup_conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASSWORD,
        database=TEST_DB_NAME
    )

    try:
        await cleanup_conn.execute("TRUNCATE TABLE audit_log CASCADE")
        await cleanup_conn.execute("TRUNCATE TABLE registration_codes CASCADE")
        await cleanup_conn.execute("TRUNCATE TABLE password_history CASCADE")
        await cleanup_conn.execute("TRUNCATE TABLE sessions CASCADE")
        await cleanup_conn.execute("TRUNCATE TABLE users CASCADE")
    finally:
        await cleanup_conn.close()


@pytest_asyncio.fixture
async def test_db_pool(setup_test_database, clean_database):
    """Create a test database pool connected to the test PostgreSQL database."""
    test_database_url = f"postgresql://{TEST_DB_USER}:{TEST_DB_PASSWORD}@{TEST_DB_HOST}:{TEST_DB_PORT}/{TEST_DB_NAME}"

    test_settings = Settings(
        AUTH_MODE="multi_user",
        DATABASE_URL=test_database_url,
        JWT_SECRET_KEY="test-secret-key-for-testing-only",
        ENABLE_REGISTRATION=True,
        REQUIRE_REGISTRATION_CODE=False,
        RATE_LIMIT_ENABLED=False
    )

    pool = DatabasePool(test_settings)
    await pool.initialize()

    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def mock_db_pool():
    """Create a mock database pool for unit testing."""
    pool = AsyncMock(spec=DatabasePool)

    # Mock connection context manager
    mock_conn = AsyncMock()
    pool.transaction.return_value.__aenter__.return_value = mock_conn
    pool.transaction.return_value.__aexit__.return_value = None

    # Mock fetchone for user queries
    pool.fetchone = AsyncMock()
    pool.fetchrow = AsyncMock()
    pool.fetch = AsyncMock()
    pool.fetchval = AsyncMock()

    # Mock execute for updates
    pool.execute = AsyncMock()
    pool.acquire = AsyncMock()
    pool.release = AsyncMock()

    return pool


@pytest.fixture
def password_service():
    """Create a password service instance for testing."""
    return PasswordService()


@pytest.fixture
def jwt_settings():
    """Create JWT settings for testing."""
    return Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY="test-secret-key-for-testing-only-needs-32-chars-minimum",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
        SESSION_CLEANUP_INTERVAL_HOURS=24,
        SESSION_MAX_AGE_DAYS=30,
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_MAX_REQUESTS=100,
        RATE_LIMIT_WINDOW_SECONDS=60,
        PASSWORD_MIN_LENGTH=8,
        PASSWORD_REQUIRE_UPPERCASE=True,
        PASSWORD_REQUIRE_LOWERCASE=True,
        PASSWORD_REQUIRE_DIGIT=True,
        PASSWORD_REQUIRE_SPECIAL=False,
        REGISTRATION_ENABLED=True,
        REGISTRATION_REQUIRE_CODE=False,
        REGISTRATION_CODES=[],
        DEFAULT_USER_ROLE="user",
        DEFAULT_STORAGE_QUOTA_MB=1000,
        EMAIL_VERIFICATION_REQUIRED=False,
        CORS_ORIGINS=["*"],
        API_PREFIX="/api/v1"
    )


@pytest.fixture
def jwt_service(jwt_settings):
    """Create a JWT service instance for testing."""
    return JWTService(settings=jwt_settings)


@pytest_asyncio.fixture
async def session_manager(test_db_pool):
    """Create a session manager instance for testing."""
    manager = SessionManager(db_pool=test_db_pool)
    yield manager
    # Cleanup
    await manager.shutdown()


@pytest_asyncio.fixture
async def rate_limiter():
    """Create a rate limiter instance for testing."""
    limiter = RateLimiter()
    yield limiter
    # Cleanup
    await limiter.cleanup()


@pytest_asyncio.fixture
async def registration_service(test_db_pool, password_service):
    """Create a registration service instance for testing."""
    return RegistrationService(
        db_pool=test_db_pool,
        password_service=password_service
    )


@pytest_asyncio.fixture
async def audit_service(test_db_pool):
    """Create an audit service instance for testing."""
    service = UnifiedAuditService()
    await service.initialize()
    try:
        yield service
    finally:
        await service.stop()


@pytest_asyncio.fixture
async def storage_service(test_db_pool):
    """Create a storage quota service instance for testing."""
    return StorageQuotaService(test_db_pool)


@pytest_asyncio.fixture
async def test_user(test_db_pool, password_service):
    """Create a test user in the database."""
    user_uuid = str(uuid.uuid4())
    password = "Test@Pass#2024!"
    password_hash = password_service.hash_password(password)

    async with test_db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            INSERT INTO users (
                uuid, username, email, password_hash, role,
                is_active, is_verified, storage_quota_mb, storage_used_mb
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, uuid, username, email, role, is_active, is_verified,
                      storage_quota_mb, storage_used_mb, created_at
        """, user_uuid, "testuser", "test@example.com", password_hash,
            "user", True, True, 5120, 0.0)

    return {
        "id": user["id"],
        "uuid": str(user["uuid"]),
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "is_active": user["is_active"],
        "is_verified": user["is_verified"],
        "storage_quota_mb": user["storage_quota_mb"],
        "storage_used_mb": user["storage_used_mb"],
        "created_at": user["created_at"],
        "password": password,
        "password_hash": password_hash
    }


@pytest_asyncio.fixture
async def admin_user(test_db_pool, password_service):
    """Create an admin test user in the database."""
    user_uuid = str(uuid.uuid4())
    password = "Admin@Pass#2024!"
    password_hash = password_service.hash_password(password)

    async with test_db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            INSERT INTO users (
                uuid, username, email, password_hash, role,
                is_active, is_verified, storage_quota_mb, storage_used_mb
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, uuid, username, email, role, is_active, is_verified,
                      storage_quota_mb, storage_used_mb, created_at
        """, user_uuid, "admin", "admin@example.com", password_hash,
            "admin", True, True, 10240, 0.0)

    return {
        "id": user["id"],
        "uuid": str(user["uuid"]),
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "is_active": user["is_active"],
        "is_verified": user["is_verified"],
        "storage_quota_mb": user["storage_quota_mb"],
        "storage_used_mb": user["storage_used_mb"],
        "created_at": user["created_at"],
        "password": password,
        "password_hash": password_hash
    }


@pytest_asyncio.fixture
async def inactive_user(test_db_pool, password_service):
    """Create an inactive test user in the database."""
    user_uuid = str(uuid.uuid4())
    password = "Inactive@Pass#2024!"
    password_hash = password_service.hash_password(password)

    async with test_db_pool.acquire() as conn:
        user = await conn.fetchrow("""
            INSERT INTO users (
                uuid, username, email, password_hash, role,
                is_active, is_verified, storage_quota_mb, storage_used_mb
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id, uuid, username, email, role, is_active, is_verified,
                      storage_quota_mb, storage_used_mb, created_at
        """, user_uuid, "inactiveuser", "inactive@example.com", password_hash,
            "user", False, True, 5120, 0.0)

    return {
        "id": user["id"],
        "uuid": str(user["uuid"]),
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "is_active": user["is_active"],
        "is_verified": user["is_verified"],
        "storage_quota_mb": user["storage_quota_mb"],
        "storage_used_mb": user["storage_used_mb"],
        "created_at": user["created_at"],
        "password": password,
        "password_hash": password_hash
    }


@pytest.fixture
def valid_access_token(jwt_service, test_user):
    """Create a valid access token for testing."""
    return jwt_service.create_access_token(
        user_id=test_user['id'],
        username=test_user['username'],
        role=test_user['role']
    )


@pytest.fixture
def valid_refresh_token(jwt_service, test_user):
    """Create a valid refresh token for testing."""
    return jwt_service.create_refresh_token(
        user_id=test_user['id'],
        username=test_user['username']
    )


@pytest.fixture
def expired_access_token(jwt_service, test_user):
    """Create an expired access token for testing."""
    # Temporarily override expiry
    original_expire = jwt_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES
    jwt_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES = -1  # Expired
    token = jwt_service.create_access_token(
        user_id=test_user['id'],
        username=test_user['username'],
        role=test_user['role']
    )
    jwt_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire
    return token


@pytest.fixture
def auth_headers(valid_access_token):
    """Create authorization headers with valid token."""
    return {"Authorization": f"Bearer {valid_access_token}"}


@pytest.fixture
def api_key_headers():
    """Create API key headers for single-user mode."""
    return {"X-API-KEY": settings.get("SINGLE_USER_API_KEY", "test-api-key")}


@pytest.fixture(autouse=True)
def clear_app_overrides():
    """Clear FastAPI app dependency overrides after each test."""
    yield
    from tldw_Server_API.app.main import app
    app.dependency_overrides.clear()
