import os
import socket
import time
import shutil
import subprocess
import pytest

from tldw_Server_API.tests.helpers.pg_env import get_pg_env


_TRUTHY = {"1", "true", "yes", "y", "on"}


def _truthy(v: str | None) -> bool:
    return bool(v and v.strip().lower() in _TRUTHY)


def _ensure_local_pg(pg_host: str, pg_port: int, user: str, password: str, database: str) -> None:
    if pg_host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Local docker bootstrap only supported for localhost hosts")
    if _truthy(os.getenv("TLDW_TEST_NO_DOCKER")):
        raise RuntimeError("Docker bootstrap disabled via TLDW_TEST_NO_DOCKER")
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise RuntimeError("Docker not found in PATH")
    image = os.getenv("TLDW_TEST_PG_IMAGE", "postgres:15")
    container = os.getenv("TLDW_TEST_PG_CONTAINER_NAME", "tldw_jobs_postgres_test")
    # Remove any old container
    subprocess.run([docker_bin, "rm", "-f", container], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    envs = [
        "-e", f"POSTGRES_USER={user}",
        "-e", f"POSTGRES_PASSWORD={password}",
        "-e", f"POSTGRES_DB={database}",
    ]
    ports = ["-p", f"{pg_port}:5432"]
    run_cmd = [docker_bin, "run", "-d", "--name", container, *envs, *ports, image]
    subprocess.run(run_cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Wait up to 30s
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with socket.create_connection((pg_host, int(pg_port)), timeout=1.0):
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Postgres did not become reachable after docker start attempts")


@pytest.fixture
def jobs_pg(monkeypatch):
    """Ensure Postgres for Jobs tests and set JOBS_DB_URL.

    - Skips the test unless RUN_PG_JOBS_TESTS is truthy
    - Resolves DSN using tests/helpers/pg_env precedence
    - Attempts a quick TCP probe; if local and docker allowed, starts a container
    - Sets JOBS_DB_URL (adds connect_timeout=2) and returns the DSN
    - Ensures Jobs schema exists (idempotent)
    """
    if not _truthy(os.getenv("RUN_PG_JOBS_TESTS")):
        pytest.skip("FIXME: Postgres outbox tests disabled by default; set RUN_PG_JOBS_TESTS=1 to enable")

    # Minimal app footprint and router gating hints
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "0")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(filter(None, [os.getenv("ROUTES_ENABLE", ""), "jobs"])))

    # Quiet jobs background features
    monkeypatch.setenv("JOBS_METRICS_GAUGES_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_RECONCILE_ENABLE", "false")
    monkeypatch.setenv("JOBS_WEBHOOKS_ENABLED", "false")

    pg = get_pg_env()
    # Reachability check
    try:
        with socket.create_connection((pg.host, int(pg.port)), timeout=1.5):
            pass
    except Exception:
        try:
            _ensure_local_pg(pg.host, int(pg.port), pg.user, pg.password, pg.database)
        except Exception:
            pytest.skip(f"Postgres not reachable at {pg.host}:{pg.port} and docker bootstrap failed/disabled")

    dsn = pg.dsn
    dsn_ct = dsn + ("&" if "?" in dsn else "?") + "connect_timeout=2"
    monkeypatch.setenv("JOBS_DB_URL", dsn_ct)
    # Ensure schema
    try:
        from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
        ensure_jobs_tables_pg(dsn_ct)
    except Exception:
        # Best-effort; individual calls will surface issues
        pass

    return dsn_ct


@pytest.fixture
def route_debugger():
    """Helper to print app routes when debugging 404s in tests.

    Usage:
        if resp.status_code == 404:
            route_debugger(app)
    """
    def _debug(app):
        try:
            from starlette.routing import BaseRoute
            lines = []
            for r in getattr(app, "routes", []):
                path = getattr(r, "path", None) or getattr(r, "path_format", None) or str(r)
                methods = sorted(list(getattr(r, "methods", set()))) if hasattr(r, "methods") else []
                name = getattr(r, "name", "")
                lines.append(f"- {path} [{','.join(methods)}] name={name}")
            print("[route-debug] Mounted routes:\n" + "\n".join(lines))
        except Exception as e:  # pragma: no cover - debugging helper
            print(f"[route-debug] failed: {e}")

    return _debug
