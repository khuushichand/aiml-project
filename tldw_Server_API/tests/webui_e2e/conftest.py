import contextlib
import os
import socket
from pathlib import Path
from typing import Dict, Optional

import pytest

from tldw_Server_API.scripts import server_lifecycle


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
