import os
import time
import socket
import contextlib
import subprocess
import threading


class _ProcLogger:
    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self.buffer = []
        self._t = threading.Thread(target=self._reader, daemon=True)
        self._t.start()

    def _reader(self):
        try:
            if not self._proc.stdout:
                return
            for line in iter(self._proc.stdout.readline, b""):
                try:
                    s = line.decode(errors="ignore").rstrip()
                except Exception:
                    s = str(line)
                self.buffer.append(s)
                # Prevent unbounded growth
                if len(self.buffer) > 1000:
                    self.buffer = self.buffer[-1000:]
        except Exception:
            pass

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
    # Use a key >=16 chars to satisfy settings validation
    env["SINGLE_USER_API_KEY"] = os.getenv("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")
    env["TEST_MODE"] = "true"
    # Avoid any optional background workers that could slow startup
    env["EPHEMERAL_CLEANUP_ENABLED"] = "false"
    env["CLAIMS_REBUILD_ENABLED"] = "false"

    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "tldw_Server_API.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    logger = _ProcLogger(proc)

    base = f"http://127.0.0.1:{port}"
    # Wait for readiness (increase timeout for slower startups)
    for _ in range(360):  # up to ~90s
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
        # Emit captured log lines to help diagnose
        logs = "\n".join(logger.buffer[-200:])
        raise RuntimeError(f"Server failed to start in time. Recent logs:\n{logs}")

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
