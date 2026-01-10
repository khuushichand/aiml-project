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


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_jobs_routes_env():
     """Session-scoped baseline env so Jobs admin routes are mounted eagerly.

    Ensures that when `tldw_Server_API.app.main` is first imported during test
    discovery or module import, the 'jobs' router is included regardless of the
    order in which fixtures or tests import modules.
    """
    # Core test toggles applied as early as possible
    os.environ.setdefault("TEST_MODE", "true")
    os.environ.setdefault("MINIMAL_TEST_APP", "1")
    os.environ.setdefault("ROUTES_STABLE_ONLY", "0")
    # Make sure 'jobs' is present in ROUTES_ENABLE for non-minimal codepaths
    prev = os.environ.get("ROUTES_ENABLE", "")
    parts = [p for p in prev.split(",") if p]
    if "jobs" not in parts:
        parts.append("jobs")
        os.environ["ROUTES_ENABLE"] = ",".join(parts)
    # Avoid privilege metadata validation aborts when config file is absent
    os.environ.setdefault("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "0")


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


@pytest.fixture(autouse=True)
def _jobs_minimal_env(monkeypatch):
     """Ensure a minimal, stable app environment for Jobs tests.

    - Enables TEST_MODE and MINIMAL_TEST_APP to avoid heavy startup dependencies
    - Ensures Jobs routes are mounted via ROUTES_ENABLE
    - Disables background Jobs services that can add flakiness
    - Stabilizes acquisition priority for chatbooks domain
    """
    # Core test toggles
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "0")
    prev = os.getenv("ROUTES_ENABLE", "")
    parts = [p for p in prev.split(",") if p]
    if "jobs" not in parts:
        parts.append("jobs")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(parts))

    # Quiet background features for deterministic tests
    monkeypatch.setenv("JOBS_METRICS_GAUGES_ENABLED", "false")
    monkeypatch.setenv("JOBS_METRICS_RECONCILE_ENABLE", "false")
    # Default to no lease enforcement in Jobs tests unless a test opts in
    if os.getenv("JOBS_ENFORCE_LEASE_ACK") is None:
        monkeypatch.setenv("JOBS_DISABLE_LEASE_ENFORCEMENT", "true")
    # Disable counters and outbox by default for determinism; tests can opt-in
    if os.getenv("JOBS_COUNTERS_ENABLED") is None:
        monkeypatch.setenv("JOBS_COUNTERS_ENABLED", "false")
    if os.getenv("JOBS_EVENTS_OUTBOX") is None:
        monkeypatch.setenv("JOBS_EVENTS_OUTBOX", "false")
    # Webhooks worker defaults to off; individual tests can opt-in as needed
    if os.getenv("JOBS_WEBHOOKS_ENABLED") is None:
        monkeypatch.setenv("JOBS_WEBHOOKS_ENABLED", "false")

    # Disable core Chatbooks Jobs worker during tests to avoid races
    monkeypatch.setenv("CHATBOOKS_CORE_WORKER_ENABLED", "false")

    # Skip global privilege metadata validation for Jobs tests
    monkeypatch.setenv("PRIVILEGE_METADATA_VALIDATE_ON_STARTUP", "0")

    # Stabilize acquisition priority for chatbooks domain
    prev_desc = os.getenv("JOBS_ACQUIRE_PRIORITY_DESC_DOMAINS", "")
    domains = {d.strip() for d in prev_desc.split(",") if d.strip()}
    if "chatbooks" not in domains:
        domains.add("chatbooks")
        monkeypatch.setenv("JOBS_ACQUIRE_PRIORITY_DESC_DOMAINS", ",".join(sorted(domains)))


@pytest.fixture(autouse=True)
def _reset_jobs_acquire_gate():
     """Reset JobManager acquire gate before and after each test.

    App shutdown flips the acquire gate on; carrying that across tests
    blocks acquisitions. Ensure it's off for each test.
    """
    try:
        from tldw_Server_API.app.core.Jobs.manager import JobManager as _JM
        _JM.set_acquire_gate(False)
        yield
        _JM.set_acquire_gate(False)
    except Exception:
        # Tests that don't touch JobManager shouldn't fail on import issues
        yield

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


@pytest.fixture(scope="function")
def jobs_pg_dsn(request, monkeypatch):
     """Function-scoped DSN for Jobs tests using a temp Postgres DB.

    - Allocates a per-test database via the unified pg_temp_db fixture.
    - Ensures Jobs schema exists on that DB.
    - Sets JOBS_DB_URL for the duration of the test.
    """
    # Minimal app footprint hints and ensure Jobs routes are enabled
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MINIMAL_TEST_APP", "1")
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "0")
    prev = os.getenv("ROUTES_ENABLE", "")
    parts = [p for p in prev.split(",") if p]
    if "jobs" not in parts:
        parts.append("jobs")
    monkeypatch.setenv("ROUTES_ENABLE", ",".join(parts))
    # Resolve a fresh temp database
    pg_temp = request.getfixturevalue("pg_temp_db")
    dsn = str(pg_temp["dsn"])  # type: ignore[index]
    # Initialize Jobs schema
    from tldw_Server_API.app.core.Jobs.pg_migrations import ensure_jobs_tables_pg
    ensure_jobs_tables_pg(dsn)
    # Ensure acquisitions are allowed for these tests
    try:
        from tldw_Server_API.app.core.Jobs.manager import JobManager
        JobManager.set_acquire_gate(False)
    except Exception:
        pass
    # Bind to env for code under test
    monkeypatch.setenv("JOBS_DB_URL", dsn)
    return dsn
