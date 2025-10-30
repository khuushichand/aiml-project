import contextlib
import os
import socket
from pathlib import Path
from typing import Dict, Optional

import pytest

# Robust import of server_lifecycle regardless of PYTHONPATH layout in CI.
# Prefer the package import; on failure, locate repository root dynamically and
# add it (and package dir) to sys.path, then retry.
try:
    from tldw_Server_API.tests.scripts import server_lifecycle
except ModuleNotFoundError:  # pragma: no cover - environment specific
    import sys
    import importlib
    here = Path(__file__).resolve()
    repo_root = None
    for cand in [here.parent, *here.parents]:
        if (cand / "tldw_Server_API" / "scripts" / "server_lifecycle.py").exists():
            repo_root = cand
            break
    # Fallback: assume 3 parents up is the repo root (…/tldw_Server_API/tests/webui_e2e/../../..)
    if repo_root is None:
        try:
            repo_root = here.parents[3]
        except Exception:
            repo_root = here.parent.parent
    if repo_root and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    # Also add the package directory directly as a secondary fallback
    pkg_dir = repo_root / "tldw_Server_API" if repo_root else None
    if pkg_dir and str(pkg_dir) not in sys.path:
        sys.path.insert(0, str(pkg_dir))

    # If a stale, preinstalled package is already loaded (e.g., older version
    # without the 'scripts' subpackage), remove it so import uses the local path.
    for key in list(sys.modules.keys()):
        if key == "tldw_Server_API" or key.startswith("tldw_Server_API."):
            sys.modules.pop(key, None)

    try:
        server_lifecycle = importlib.import_module("tldw_Server_API.tests.scripts.server_lifecycle")
    except ModuleNotFoundError:
        # Final fallback: import directly from file path to avoid any packaging
        # or path precedence issues in CI.
        import importlib.util as importlib_util

        if not pkg_dir:
            raise
        module_path = pkg_dir / "scripts" / "server_lifecycle.py"
        if not module_path.exists():
            raise
        spec = importlib_util.spec_from_file_location(
            "tldw_Server_API.tests.scripts.server_lifecycle", str(module_path)
        )
        assert spec and spec.loader
        module = importlib_util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore[assignment]
        server_lifecycle = module


def _find_free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


def _set_env(overrides: Dict[str, str]) -> Dict[str, Optional[str]]:
    original = {key: os.environ.get(key) for key in overrides}
    for key, value in overrides.items():
        os.environ[key] = value
    return original


def _restore_env(original: Dict[str, Optional[str]]) -> None:
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _print_server_log(label: str) -> None:
    log_path = Path(f"server-{label}.log")
    if log_path.exists():
        print(f"===== server log ({label}) =====")
        try:
            print(log_path.read_text(encoding="utf-8"))
        except Exception:
            pass


@pytest.fixture(scope="session")
def server_url() -> str:
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    label = os.environ.get("SERVER_LABEL", "webui")

    overrides = {
        "SERVER_LABEL": label,
        "SERVER_PORT": str(port),
        "E2E_TEST_BASE_URL": base_url,
        "AUTH_MODE": "single_user",
        "SINGLE_USER_API_KEY": os.getenv("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID"),
        "TEST_MODE": "true",
        "EPHEMERAL_CLEANUP_ENABLED": "false",
        "CLAIMS_REBUILD_ENABLED": "false",
    }

    original_env = _set_env(overrides)

    try:
        server_lifecycle.start_server()
        server_lifecycle.health_check()
    except Exception:
        _print_server_log(label)
        _restore_env(original_env)
        raise

    try:
        yield base_url
    finally:
        try:
            server_lifecycle.stop_server()
        finally:
            _restore_env(original_env)


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            browser.close()


@pytest.fixture
def page(server_url: str, browser):
    context = browser.new_context(base_url=server_url)
    try:
        page = context.new_page()
        yield page
    finally:
        context.close()
