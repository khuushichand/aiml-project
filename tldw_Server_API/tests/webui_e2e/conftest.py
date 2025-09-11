import os
import time
import socket
import contextlib
import subprocess

import pytest

try:
    import requests
except Exception:  # requests might not be installed; fallback to stdlib
    requests = None
    import urllib.request


def _find_free_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server_url():
    port = _find_free_port()
    env = os.environ.copy()
    env["AUTH_MODE"] = "single_user"
    env["SINGLE_USER_API_KEY"] = "sk-test-123456"
    env["TEST_MODE"] = "true"

    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "tldw_Server_API.app.main:app",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    base = f"http://127.0.0.1:{port}"
    # Wait for readiness
    for _ in range(120):
        try:
            if requests:
                r = requests.get(f"{base}/health", timeout=1)
                ok = r.status_code in (200, 206)
            else:
                with urllib.request.urlopen(f"{base}/health", timeout=1) as resp:
                    ok = resp.status in (200, 206)
            if ok:
                break
        except Exception:
            pass
        time.sleep(0.25)
    else:
        proc.terminate()
        raise RuntimeError("Server failed to start in time")

    yield base

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser, server_url):
    context = browser.new_context(base_url=server_url)
    page = context.new_page()
    yield page
    context.close()

