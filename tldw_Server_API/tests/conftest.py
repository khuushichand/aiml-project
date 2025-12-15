"""
Pytest configuration for the main test suite.

Registers shared test plugins and provides common fixtures.
"""

"""Local pytest configuration for tests subtree.

Note: pytest>=8 discourages defining `pytest_plugins` outside top-level conftest
files. We register shared plugins here to ensure discovery across the suite,
and keep per-suite conftests focused on markers and env overrides.
"""

import os
from pathlib import Path
try:
    # Ensure tests see provider keys from the canonical location
    # Load once at collection time, without overriding explicit env
    from dotenv import load_dotenv  # type: ignore
    _tests_root = Path(__file__).resolve()
    _project_root = _tests_root.parents[1]  # tldw_Server_API/
    _env_path = _project_root / "Config_Files" / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=str(_env_path), override=False)
        # If a real OpenAI key is present, prefer OpenAI as the default provider
        # to ensure real-integration tests hit OpenAI when provider is unspecified.
        if os.getenv("OPENAI_API_KEY") and not os.getenv("DEFAULT_LLM_PROVIDER"):
            os.environ.setdefault("DEFAULT_LLM_PROVIDER", "openai")
except Exception:
    # Never fail collection due to dotenv issues
    pass
# Force test-friendly env knobs
os.environ["MPLBACKEND"] = "Agg"
# Provide an explicit, deterministic API key for tests that rely on single-user/test-mode shortcuts.
# Production code no longer assumes a default for SINGLE_USER_TEST_API_KEY.
os.environ.setdefault("SINGLE_USER_TEST_API_KEY", "test-api-key-12345")
# Ensure the AuthNZ PROFILE hint does not leak from developer shells into tests.
# Tests that need a profile should set it explicitly via monkeypatch.
os.environ.pop("PROFILE", None)
# Disable background schedulers/workers that spawn threads during tests
os.environ["DISABLE_AUTHNZ_SCHEDULER"] = "1"
os.environ["AUTHNZ_SCHEDULER_DISABLED"] = "1"
os.environ["WORKFLOWS_SCHEDULER_ENABLED"] = "false"
# Relax webhook egress for test replay/egress simulations (no real network used in test short-circuit paths)
os.environ.setdefault("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "false")
os.environ.setdefault("WORKFLOWS_WEBHOOK_ALLOWLIST", "*")
# Disable AuthNZ scheduler functions proactively to avoid background threads
try:
    from tldw_Server_API.app.core.AuthNZ import scheduler as _auth_sched
    async def _noop():
        return None
    _auth_sched.start_authnz_scheduler = _noop  # type: ignore[assignment]
    _auth_sched.stop_authnz_scheduler = _noop  # type: ignore[assignment]
    _auth_sched.reset_authnz_scheduler = _noop  # type: ignore[assignment]
except Exception:
    pass
import logging
# Dump lingering non-daemon threads at exit to avoid silent hangs
import threading
import atexit
import asyncio
try:
    import faulthandler
    import signal
    import sys as _sys
    if hasattr(signal, "SIGUSR2"):
        faulthandler.register(signal.SIGUSR2, file=_sys.stderr, all_threads=True)
except Exception:
    # Best-effort; tracing is optional
    pass
import pytest


_AUTH_ENV_BASELINE_KEYS = (
    # AuthNZ mode + core configuration.
    "AUTH_MODE",
    "PROFILE",
    "JWT_SECRET_KEY",
    "DATABASE_URL",
    # Single-user auth header compatibility.
    "SINGLE_USER_API_KEY",
    "API_KEY",
    # Common guardrail toggles that can leak between tests when set via os.environ directly.
    "VIRTUAL_KEYS_ENABLED",
    "LLM_BUDGET_ENFORCE",
    "RATE_LIMIT_ENABLED",
    "CSRF_ENABLED",
    # Route gating and backend knobs used by a handful of integration tests.
    "ROUTES_ENABLE",
    "TLDW_USER_DB_BACKEND",
)

_AUTH_ENV_BASELINE = {k: os.environ.get(k) for k in _AUTH_ENV_BASELINE_KEYS}


@pytest.fixture(autouse=True)
def _restore_auth_env_and_singletons():
    """Restore shared AuthNZ-related env and singleton state between tests.

    Many tests legitimately flip `AUTH_MODE` (and related env vars) to exercise
    multi-user/JWT paths. Some of those tests historically used `os.environ[...]`
    assignments without restoring them, which makes the suite order-dependent.

    This fixture restores a small set of high-impact environment keys to their
    baseline values and resets key singletons used by the auth/jobs stacks.
    """
    yield

    for key, baseline_value in _AUTH_ENV_BASELINE.items():
        if baseline_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = baseline_value

    # Ensure subsequent tests rebuild Settings from the restored environment.
    try:
        from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

        reset_settings()
    except Exception:
        pass

    # Avoid leaking the process-wide jobs acquisition gate across tests.
    try:
        from tldw_Server_API.app.core.Jobs.manager import JobManager

        JobManager.set_acquire_gate(False)
    except Exception:
        pass


def _log_lingering_threads():
    try:
        import sys, traceback

        remaining = [
            t
            for t in threading.enumerate()
            if t is not threading.current_thread() and not t.daemon
        ]
        if remaining:
            details = []
            for t in remaining:
                stack = sys._current_frames().get(t.ident)
                formatted_stack = "".join(traceback.format_stack(stack)) if stack else ""
                details.append((t.name, getattr(t, "_target", None), formatted_stack))
                try:
                    # Best-effort shutdown to avoid interpreter hang
                    t.join(timeout=1.0)
                except Exception:
                    pass
                try:
                    t.daemon = True  # allow interpreter shutdown even if still alive
                except Exception:
                    pass
            summary = [(d[0], d[1]) for d in details]
            print(f"Non-daemon threads still running at exit: {summary}", file=sys.stderr)
            _log.warning("Non-daemon threads still running at exit: %s", summary)
            for name, target, formatted_stack in details:
                if formatted_stack:
                    _log.warning(
                        "Thread %s target=%s stack:\n%s", name, target, formatted_stack
                    )
                    print(
                        f"Thread {name} target={target} stack:\n{formatted_stack}",
                        file=sys.stderr,
                    )
    except Exception:
        pass


def _cleanup_lingering_threads(log: logging.Logger, context: str = "teardown") -> None:
    """Best-effort cleanup of lingering non-daemon threads during tests.

    Performs a first pass join with timeout for non-daemon threads and then logs
    any remaining threads with their stack frames before marking them as daemon
    to avoid interpreter shutdown hangs.
    """
    try:
        import sys

        current = threading.current_thread()
        # First pass: try to join all non-daemon threads with a timeout
        for t in threading.enumerate():
            if t is current or t.daemon:
                continue
            try:
                t.join(timeout=1.0)
            except Exception:
                pass

        # Second pass: log any remaining threads and mark them daemon
        for t in threading.enumerate():
            if t is current or t.daemon:
                continue
            try:
                stack = sys._current_frames().get(t.ident)
            except Exception:
                stack = None
            msg = (
                f"Lingering non-daemon thread during {context}: "
                f"name={t.name} target={getattr(t, '_target', None)}"
            )
            print(msg, file=sys.stderr)
            try:
                log.warning("%s stack=%s", msg, stack)
            except Exception:
                pass
            try:
                t.daemon = True  # allow interpreter shutdown to proceed
            except Exception:
                pass
    except Exception as e:
        try:
            import sys as _local_sys

            print(
                f"Failed to log lingering threads during {context}: {e}",
                file=_local_sys.stderr,
            )
        except Exception:
            pass


atexit.register(_log_lingering_threads)
# Ensure problematic optional routers don't import during test collection
# and enable test-friendly behaviors before importing the app.
_log = logging.getLogger(__name__)
try:
    # Disable heavy 'research' router to avoid importing Web_Scraping during collection
    existing_disable = os.getenv("ROUTES_DISABLE", "")
    if "research" not in existing_disable:
        os.environ["ROUTES_DISABLE"] = (existing_disable + ",research").strip(",")
    # Unless explicitly opted-in, disable Evaluations routes during tests to avoid heavy imports
    _run_evals = str(os.getenv("RUN_EVALUATIONS", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
    _rd = os.getenv("ROUTES_DISABLE", "")
    if _run_evals:
        # Evaluations suite is enabled: ensure routes are not disabled
        parts = [p for p in _rd.replace(" ", ",").split(",") if p]
        parts = [p for p in parts if p.lower() != "evaluations"]
        os.environ["ROUTES_DISABLE"] = ",".join(dict.fromkeys(parts))
        # Evaluations rely on the full app profile; disable minimal-test app mode
        os.environ["MINIMAL_TEST_APP"] = "0"
    else:
        # Default: prefer minimal app profile for faster, deterministic tests
        os.environ.setdefault("MINIMAL_TEST_APP", "1")
        if "evaluations" not in ",".join([_rd]):
            os.environ["ROUTES_DISABLE"] = ((_rd + ",evaluations").strip(","))
    # Ensure Workflows/Scheduler routes stay enabled in tests to avoid 404s when stable_only is true
    try:
        _re = os.getenv("ROUTES_ENABLE", "")
        parts = [p for p in _re.replace(" ", ",").split(",") if p]
        for k in ["workflows", "scheduler"]:
            if k not in [p.lower() for p in parts]:
                parts.append(k)
        os.environ["ROUTES_ENABLE"] = ",".join(dict.fromkeys(parts))
    except Exception:
        pass
    # Ensure notes endpoints stay enabled for health tests even if ROUTES_DISABLE includes them
    try:
        _rd = os.getenv("ROUTES_DISABLE", "")
        parts = [p for p in _rd.replace(" ", ",").split(",") if p]
        parts = [p for p in parts if p.lower() != "notes"]
        os.environ["ROUTES_DISABLE"] = ",".join(dict.fromkeys(parts))
    except Exception:
        pass
    # Enable deterministic test behaviors across subsystems
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    # Ensure Postgres helpers see consistent defaults immediately at import time.
    # Many PG tests call get_pg_env() at module import; set test user/password
    # here so precedence falls to the correct, compose-aligned credentials.
    os.environ.setdefault("POSTGRES_TEST_USER", "tldw_user")
    os.environ.setdefault("POSTGRES_TEST_PASSWORD", "TestPassword123!")
    # Also mirror to generic POSTGRES_* if unset to avoid helper drift.
    os.environ.setdefault("POSTGRES_USER", "tldw_user")
    os.environ.setdefault("POSTGRES_PASSWORD", "TestPassword123!")
    # Ensure Postgres tests use a proper DSN instead of falling back to a SQLite DATABASE_URL.
    # If a dedicated DSN is provided via TEST_DATABASE_URL or POSTGRES_TEST_DSN, prefer it.
    # Otherwise, if POSTGRES_TEST_HOST/USER/DB are present, synthesize a DSN.
    try:
        _pg_dsn = os.getenv("TEST_DATABASE_URL") or os.getenv("POSTGRES_TEST_DSN")
        if not _pg_dsn:
            _pg_host = os.getenv("POSTGRES_TEST_HOST")
            _pg_port = os.getenv("POSTGRES_TEST_PORT", "5432")
            _pg_user = os.getenv("POSTGRES_TEST_USER")
            _pg_pass = os.getenv("POSTGRES_TEST_PASSWORD", "")
            _pg_db = os.getenv("POSTGRES_TEST_DATABASE") or os.getenv("POSTGRES_TEST_DB")
            if _pg_host and _pg_user and _pg_db:
                # Compose a DSN and set TEST_DATABASE_URL so PG helpers don't pick SQLite DATABASE_URL
                _auth = f"{_pg_user}:{_pg_pass}" if _pg_pass else _pg_user
                _pg_dsn = f"postgresql://{_auth}@{_pg_host}:{int(_pg_port)}/{_pg_db}"
        if _pg_dsn and _pg_dsn.lower().startswith("postgres"):
            os.environ["TEST_DATABASE_URL"] = _pg_dsn
    except Exception:
        pass
except Exception as e:
    # Surface environment setup failures in test output
    _log.exception("Failed to apply test environment setup in conftest.py")
import pytest
from fastapi.testclient import TestClient
import contextlib

# Register shared test plugins for the whole suite
pytest_plugins = (
    "tldw_Server_API.tests._plugins.e2e_fixtures",
    "tldw_Server_API.tests._plugins.e2e_state_fixtures",
    "tldw_Server_API.tests._plugins.chat_fixtures",
    "tldw_Server_API.tests._plugins.media_fixtures",
    "tldw_Server_API.tests._plugins.postgres",
)


# Skip Jobs-marked tests by default unless explicitly enabled via RUN_JOBS.
# This ensures general CI workflows never run Jobs tests; the dedicated
# jobs-suite workflow sets RUN_JOBS=1 to include them.
import pytest as _pytest_jobs_gate

@_pytest_jobs_gate.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):  # pragma: no cover - collection-time behavior
    try:
        run_jobs = str(os.getenv("RUN_JOBS", "")).lower() in {"1", "true", "yes", "y", "on"}
    except Exception:
        run_jobs = False
    try:
        run_evals = str(os.getenv("RUN_EVALUATIONS", "")).lower() in {"1", "true", "yes", "y", "on"}
    except Exception:
        run_evals = False

    skip_jobs = _pytest_jobs_gate.mark.skip(reason="Jobs tests run only in the jobs-suite CI workflow")
    skip_evals = _pytest_jobs_gate.mark.skip(reason="Evaluations tests run only when RUN_EVALUATIONS=1")
    jobs_markers = {"jobs", "pg_jobs", "pg_jobs_stress"}
    for item in items:
        try:
            if not run_jobs and any(m.name in jobs_markers for m in item.iter_markers()):
                item.add_marker(skip_jobs)
            if not run_evals and any(m.name == "evaluations" for m in item.iter_markers()):
                item.add_marker(skip_evals)
        except Exception:
            # Never break collection on marker inspection
            pass

def pytest_configure(config):  # pragma: no cover - registration only
    try:
        config.addinivalue_line("markers", "evaluations: heavy Evaluations tests (opt-in via RUN_EVALUATIONS=1)")
        config.addinivalue_line("markers", "stt_golden: real-audio STT adapter golden tests (opt-in via TLDW_STT_GOLDEN_ENABLE=1)")
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):  # pragma: no cover - diagnostics/cleanup
    """Log and relax any remaining non-daemon threads to avoid interpreter shutdown hangs."""
    try:
        import sys, traceback
        current = threading.current_thread()
        threads = [t for t in threading.enumerate() if t is not current and not t.daemon]
        if threads:
            summary = [(t.name, getattr(t, "_target", None)) for t in threads]
            print(f"[pytest_sessionfinish] Non-daemon threads before exit: {summary}", file=sys.stderr)
            for t in threads:
                stack = sys._current_frames().get(t.ident)
                if stack:
                    formatted_stack = "".join(traceback.format_stack(stack))
                    print(f"[pytest_sessionfinish] Thread {t.name} target={getattr(t, '_target', None)} stack:\n{formatted_stack}", file=sys.stderr)
                # Stop common offenders (e.g., aiosqlite worker threads) to avoid hangs
                try:
                    import aiosqlite  # type: ignore
                    if isinstance(t, getattr(aiosqlite, "Connection", (aiosqlite.core.Connection,))):  # type: ignore[attr-defined]
                        try:
                            t._stop_running()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        try:
                            t.join(timeout=1.0)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    t.daemon = True
                except Exception:
                    pass
    except Exception:
        # Do not interfere with pytest shutdown on logging failures
        pass


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

    # Import the FastAPI app and dependencies lazily to avoid heavy imports during test collection
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
    from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
    from tldw_Server_API.app.api.v1.API_Deps.personalization_deps import get_usage_event_logger
    from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal, AuthContext

    async def _override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    def _override_logger():
        return usage_logger

    async def _override_principal(request=None):
        principal = AuthPrincipal(
            kind="user",
            user_id=1,
            api_key_id=None,
            subject="single-user",
            token_type="single_user",
            jti=None,
            roles=["admin"],
            permissions=["media.create"],
            is_admin=True,
            org_ids=[],
            team_ids=[],
        )
        if request is not None:
            try:
                request.state.auth = AuthContext(
                    principal=principal,
                    ip=None,
                    user_agent=None,
                    request_id=None,
                )
            except Exception as e:
                # Best-effort; don't fail tests if state attachment fails
                import logging
                logging.getLogger(__name__).debug("Failed to set request.state.auth: %s", e)
        return principal

    fastapi_app.dependency_overrides[get_request_user] = _override_user
    fastapi_app.dependency_overrides[get_usage_event_logger] = _override_logger
    fastapi_app.dependency_overrides[get_auth_principal] = _override_principal

    with TestClient(fastapi_app) as client:
        yield client, usage_logger

    fastapi_app.dependency_overrides.pop(get_request_user, None)
    fastapi_app.dependency_overrides.pop(get_usage_event_logger, None)
    fastapi_app.dependency_overrides.pop(get_auth_principal, None)


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
    # Proactively join/mark any lingering non-daemon threads so interpreter shutdown won't hang
    _cleanup_lingering_threads(_log, context="teardown")


@pytest.fixture(autouse=True)
def _reset_workflow_scheduler():
    """Reset WorkflowScheduler singleton state between tests to avoid stale queues/active counts."""
    try:
        from tldw_Server_API.app.core.Workflows.engine import WorkflowScheduler
        WorkflowScheduler._inst = None  # type: ignore[attr-defined]
    except Exception:
        pass
    yield
    try:
        from tldw_Server_API.app.core.Workflows.engine import WorkflowScheduler
        WorkflowScheduler._inst = None  # type: ignore[attr-defined]
    except Exception:
        pass


    # Log any lingering non-daemon threads with their stack frames to aid debugging hangs
    _cleanup_lingering_threads(_log, context="scheduler reset")


# Unified Postgres fixtures are provided by tldw_Server_API.tests._plugins.postgres


@pytest.fixture()
def bypass_api_limits(monkeypatch):
    """Context manager to bypass ingress rate limiting for a given FastAPI app.

    Usage:
        with bypass_api_limits(app, limiters=(audio_ep.limiter,)):
            ... make requests ...

    - Sets TEST_MODE=true for deterministic behavior
    - Disables RGSimpleMiddleware by removing it from app.user_middleware
    - Disables any provided SlowAPI limiter(s) during the context
    """

    @contextlib.contextmanager
    def _bypass(app, *, limiters: tuple = ()):  # type: ignore[override]
        # Ensure test-friendly behaviors
        monkeypatch.setenv("TEST_MODE", "true")
        monkeypatch.setenv("RG_ENABLED", "0")

        # Snapshot existing middleware stack
        original_user_middleware = getattr(app, "user_middleware", [])[:]
        # Remove RGSimpleMiddleware if present
        try:
            from tldw_Server_API.app.core.Resource_Governance.middleware_simple import RGSimpleMiddleware
            app.user_middleware = [
                m for m in original_user_middleware if getattr(m, "cls", None) is not RGSimpleMiddleware
            ]
            app.middleware_stack = app.build_middleware_stack()
        except Exception:
            pass

        # Disable provided SlowAPI limiter(s)
        limiter_states = []
        for lim in limiters or ():
            try:
                limiter_states.append((lim, getattr(lim, "enabled", True)))
                lim.enabled = False
            except Exception:
                limiter_states.append((lim, None))

        try:
            yield
        finally:
            # Restore limiter states
            for lim, prev in limiter_states:
                if prev is not None:
                    try:
                        lim.enabled = prev
                    except Exception:
                        pass
            # Restore middleware stack
            try:
                app.user_middleware = original_user_middleware
                app.middleware_stack = app.build_middleware_stack()
            except Exception:
                pass

    return _bypass
