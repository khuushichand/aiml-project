"""
Pytest configuration for the main test suite.

Registers shared test plugins and provides common fixtures.
"""

# Shared Chat/AuthNZ fixtures used across multiple test packages
pytest_plugins = (
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.authnz_fixtures",
    # Expose isolated Chat fixtures (unit_test_client, isolated_db, etc.) globally
    "tldw_Server_API.tests.Chat.integration.conftest_isolated",
    # Optional pgvector fixtures for tests that need live PG
    "tldw_Server_API.tests.helpers.pgvector",
)

import os
import logging
# Ensure problematic optional routers don't import during test collection
# and enable test-friendly behaviors before importing the app.
_log = logging.getLogger(__name__)
try:
    # Disable heavy 'research' router to avoid importing Web_Scraping during collection
    existing_disable = os.getenv("ROUTES_DISABLE", "")
    if "research" not in existing_disable:
        os.environ["ROUTES_DISABLE"] = (existing_disable + ",research").strip(",")
    # Enable deterministic test behaviors across subsystems
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
except Exception as e:
    # Surface environment setup failures in test output
    _log.exception("Failed to apply test environment setup in conftest.py")
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger


# Bump file-descriptor limit for macOS/Linux test runs to avoid spurious
# 'Too many open files' and SQLite 'unable to open database file' errors
# caused by module-level TestClient instances in some test modules.
@pytest.fixture(scope="session", autouse=True)
def _raise_fd_limit():  # pragma: no cover - platform-dependent behavior
    try:
        import resource  # POSIX only
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        # Aim for at least 4096 if permitted by the hard limit
        target = 4096
        new_soft = min(max(soft, target), hard if hard > 0 else target)
        if new_soft > soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
    except Exception:
        # On platforms without 'resource' (e.g., Windows) or when permissions
        # disallow raising limits, silently continue.
        pass

class _TestUsageLogger:
    def __init__(self):
        self.events = []

    def log_event(self, name, resource_id=None, tags=None, metadata=None):
        self.events.append((name, resource_id, tags, metadata))


@pytest.fixture()
def client_with_single_user(monkeypatch):
    """Provide a TestClient for the full FastAPI app with a single-user auth override.

    Returns a tuple of (client, usage_logger) for tests that also need to inspect usage events.
    """
    # Ensure tests run in non-production behavior
    os.environ.setdefault("TESTING", "true")

    usage_logger = _TestUsageLogger()

    async def _override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def _override_logger():
        return usage_logger

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_usage_event_logger] = _override_logger

    with TestClient(fastapi_app) as client:
        yield client, usage_logger

    fastapi_app.dependency_overrides.pop(get_request_user, None)
    fastapi_app.dependency_overrides.pop(get_usage_event_logger, None)


@pytest.fixture()
def client_user_only(client_with_single_user):
    """Shorthand fixture that returns only the TestClient from client_with_single_user."""
    client, _ = client_with_single_user
    return client


# Global session teardown to prevent test-run hangs from lingering executors/threads
@pytest.fixture(scope="session", autouse=True)
def _shutdown_executors_and_evaluations_pool():
    """Ensure global executors and the Evaluations connection pool are shut down at session end.

    Prevents pytest from hanging due to non-daemon worker threads started by
    CPU-bound helpers and background maintenance in the Evaluations module when
    app lifespan teardown is not exercised during tests.
    """
    yield
    # Best-effort shutdown of registered executors (thread/process pools)
    try:
        from tldw_Server_API.app.core.Utils.executor_registry import (
            shutdown_all_registered_executors_sync,
        )
        shutdown_all_registered_executors_sync(wait=True, cancel_futures=True)
    except Exception:
        pass
    # Explicit CPU pools cleanup (idempotent)
    try:
        from tldw_Server_API.app.core.Utils.cpu_bound_handler import cleanup_pools
        cleanup_pools()
    except Exception:
        pass


# --- Postgres params fixture for non-AuthNZ suites (Evaluations, etc.) ---
# Provides host/port/db/user/password derived from TEST_DATABASE_URL/DATABASE_URL
# or POSTGRES_TEST_* environment variables. Tests depending on this fixture will
# skip cleanly when Postgres is not configured.
def _parse_pg_dsn_for_tests(dsn: str):  # pragma: no cover - env dependent
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
        return {"host": host, "port": port, "user": user, "password": password, "database": db}
    except Exception:
        return None


import pytest


@pytest.fixture()
def pg_eval_params():
    """Return Postgres connection params for Evaluations tests if available.

    Priority:
    - TEST_DATABASE_URL or DATABASE_URL
    - POSTGRES_TEST_DSN
    - POSTGRES_TEST_HOST/PORT/DB/USER/PASSWORD
    If none are set, use local default 127.0.0.1:5432/tldw_test with
    tldw_user/TestPassword123!. Before yielding, perform a light availability
    probe; skip the test only if Postgres is unreachable.
    """
    # 1) Resolve from DSN or env vars
    dsn = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_TEST_DSN")
    cfg = _parse_pg_dsn_for_tests(dsn) if dsn else None
    if not cfg:
        host = os.getenv("POSTGRES_TEST_HOST")
        port = int(os.getenv("POSTGRES_TEST_PORT", "5432")) if os.getenv("POSTGRES_TEST_PORT") else 5432
        user = os.getenv("POSTGRES_TEST_USER")
        password = os.getenv("POSTGRES_TEST_PASSWORD")
        database = os.getenv("POSTGRES_TEST_DATABASE") or os.getenv("POSTGRES_TEST_DB")
        if host and user and database:
            cfg = {"host": host, "port": int(port), "user": user, "password": password or "", "database": database}
    # 2) Fallback to local defaults for out-of-the-box runs
    if not cfg:
        cfg = {
            "host": "127.0.0.1",
            "port": 5432,
            "user": "tldw_user",
            "password": "TestPassword123!",
            "database": "tldw_test",
        }
    # 3) Quick availability probe: prefer driver connect; fallback to TCP check
    def _tcp_reachable(host: str, port: int, timeout: float = 1.5) -> bool:
        try:
            import socket
            with socket.create_connection((host, int(port)), timeout=timeout):
                return True
        except Exception:
            return False
    reached = False
    # Try psycopg (v3) first
    try:  # pragma: no cover - optional dependency
        import psycopg  # type: ignore
        try:
            conn = psycopg.connect(host=cfg["host"], port=int(cfg["port"]), dbname=cfg["database"], user=cfg["user"], password=cfg.get("password") or None, connect_timeout=2)
            conn.close()
            reached = True
        except Exception:
            # If the specific database doesn't exist or auth fails, at least try TCP reachability
            reached = _tcp_reachable(cfg["host"], int(cfg["port"]))
    except Exception:
        # Try psycopg2
        try:  # pragma: no cover - optional dependency
            import psycopg2  # type: ignore
            try:
                conn = psycopg2.connect(host=cfg["host"], port=int(cfg["port"]), database=cfg["database"], user=cfg["user"], password=cfg.get("password") or None, connect_timeout=2)
                conn.close()
                reached = True
            except Exception:
                reached = _tcp_reachable(cfg["host"], int(cfg["port"]))
        except Exception:
            # No driver; fall back to TCP port probe only
            reached = _tcp_reachable(cfg["host"], int(cfg["port"]))

    if not reached:
        # Attempt to auto-start a local Dockerized Postgres when targeting localhost
        host_is_local = str(cfg["host"]) in {"127.0.0.1", "localhost", "::1"}
        no_docker = os.getenv("TLDW_TEST_NO_DOCKER", "").lower() in ("1", "true", "yes")
        if host_is_local and not no_docker:
            try:
                import shutil, subprocess, time
                docker_bin = shutil.which("docker")
                if docker_bin:
                    image = os.getenv("TLDW_TEST_PG_IMAGE", "postgres:18")
                    container = os.getenv("TLDW_TEST_PG_CONTAINER_NAME", "tldw_postgres_test")
                    # Best-effort remove existing container with same name
                    try:
                        subprocess.run([docker_bin, "rm", "-f", container], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
                    envs = [
                        "-e", f"POSTGRES_USER={cfg['user']}",
                        "-e", f"POSTGRES_PASSWORD={cfg.get('password') or ''}",
                        # Use 'postgres' as initial DB, then ensure target DB exists post-start
                        "-e", "POSTGRES_DB=postgres",
                    ]
                    ports = ["-p", f"{cfg['port']}:5432"]
                    run_cmd = [docker_bin, "run", "-d", "--name", container, *envs, *ports, image]
                    try:
                        _log  # reuse module logger if available
                    except NameError:
                        import logging as _logging
                        _log = _logging.getLogger(__name__)
                    _log.info(
                        "Attempting Docker auto-start for Postgres: container=%s image=%s host=%s port=%s",
                        container,
                        image,
                        cfg["host"],
                        cfg["port"],
                    )
                    subprocess.run(run_cmd, check=False, capture_output=True)
                    # Wait up to ~30s for readiness
                    for _ in range(30):
                        if _tcp_reachable(cfg["host"], int(cfg["port"])):
                            reached = True
                            break
                        time.sleep(1)
                    # Ensure target DB exists
                    if reached:
                        try:
                            import psycopg  # type: ignore
                            base_conn = psycopg.connect(host=cfg["host"], port=int(cfg["port"]), dbname="postgres", user=cfg["user"], password=cfg.get("password") or None, autocommit=True, connect_timeout=3)
                            try:
                                with base_conn.cursor() as cur:
                                    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (cfg["database"],))
                                    if cur.fetchone() is None:
                                        cur.execute(f'CREATE DATABASE "{cfg["database"]}"')
                            finally:
                                base_conn.close()
                        except Exception:
                            try:
                                import psycopg2  # type: ignore
                                base_conn = psycopg2.connect(host=cfg["host"], port=int(cfg["port"]), database="postgres", user=cfg["user"], password=cfg.get("password") or None)
                                base_conn.autocommit = True
                                try:
                                    with base_conn.cursor() as cur:
                                        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (cfg["database"],))
                                        if cur.fetchone() is None:
                                            cur.execute(f'CREATE DATABASE "{cfg["database"]}"')
                                finally:
                                    base_conn.close()
                            except Exception:
                                # If we cannot ensure the DB exists due to missing drivers, rely on tests that create schemas to error clearly
                                pass
            except Exception:
                # Ignore docker start errors and fall through to skip
                pass

    if not reached:
        pytest.skip("Postgres not reachable at configured/default location (docker not started or unavailable)")
    return cfg
    # Stop Evaluations connection pool maintenance thread and close connections
    try:
        from tldw_Server_API.app.core.Evaluations.connection_pool import connection_manager
        connection_manager.shutdown()
    except Exception:
        pass
