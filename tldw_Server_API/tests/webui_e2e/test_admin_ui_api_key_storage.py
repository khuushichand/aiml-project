import contextlib
import re
import os
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import urlparse

import pytest


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            continue
        if value[0] in ("'", '"') and value[-1] == value[0]:
            value = value[1:-1]
        elif "#" in value:
            value = value.split("#", 1)[0].rstrip()
        if value:
            values[key] = value
    return values


def _load_env_values(paths: Iterable[Path]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for path in paths:
        merged.update(_parse_env_file(path))
    return merged


def _resolve_api_key(repo_root: Path) -> Optional[str]:
    api_key = os.environ.get("ADMIN_UI_API_KEY")
    if api_key:
        return api_key

    env_paths = [
        repo_root / ".env",
        repo_root / ".env.local",
        repo_root / "tldw_Server_API" / "Config_Files" / ".env",
        repo_root / "admin-ui" / ".env.local",
        repo_root / "admin-ui" / ".env",
    ]
    values = _load_env_values(env_paths)
    for key in (
        "ADMIN_UI_API_KEY",
        "SINGLE_USER_API_KEY",
        "NEXT_PUBLIC_X_API_KEY",
        "SERVER_X_API_KEY",
    ):
        value = values.get(key)
        if value:
            return value
    return None


def _fetch_login_page(base_url: str) -> Dict[str, Optional[str]]:
    url = f"{base_url}/login"
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            body = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="ignore")
            return {"status": str(response.status), "body": body}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")
        return {"status": str(error.code), "body": body}
    except Exception:
        return {"status": None, "body": None}


def _is_admin_ui_response(body: Optional[str]) -> bool:
    if not body:
        return False
    return "tldw Admin" in body or "Admin Panel" in body


def _is_admin_ui_running(base_url: str) -> bool:
    response = _fetch_login_page(base_url)
    return _is_admin_ui_response(response["body"])


def _wait_for_admin_ui(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_admin_ui_running(base_url):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Admin UI did not start within {timeout} seconds at {base_url}.")


@contextlib.contextmanager
def _ensure_admin_ui_running(repo_root: Path, base_url: str):
    response = _fetch_login_page(base_url)
    if _is_admin_ui_response(response["body"]):
        yield None
        return
    if response["status"] is not None:
        pytest.skip(
            "Admin UI port is already in use by a different service. "
            "Set ADMIN_UI_URL to the correct admin UI host/port."
        )

    admin_ui_dir = repo_root / "admin-ui"
    if not admin_ui_dir.exists():
        pytest.skip("admin-ui directory not found; cannot auto-start admin UI.")

    parsed = urlparse(base_url)
    port = parsed.port or 3001
    env = os.environ.copy()
    env.setdefault("NEXT_PUBLIC_DEFAULT_AUTH_MODE", "apikey")
    admin_api_url = env.get("ADMIN_UI_API_URL")
    if admin_api_url:
        env["NEXT_PUBLIC_API_URL"] = admin_api_url

    log_path = admin_ui_dir / "admin-ui-dev.log"
    log_file = log_path.open("w", encoding="utf-8")
    command = ["npm", "run", "dev", "--", "-p", str(port)]
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(admin_ui_dir),
            env=env,
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,
        )
    except FileNotFoundError:
        log_file.close()
        pytest.skip("npm is not available; start the admin UI manually.")
    try:
        _wait_for_admin_ui(base_url, timeout=90.0)
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        log_file.close()


@pytest.fixture(scope="session")
def admin_ui_base_url() -> str:
    return os.environ.get("ADMIN_UI_URL", "http://127.0.0.1:3001").rstrip("/")


@pytest.fixture(scope="session")
def admin_ui_api_key() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    api_key = _resolve_api_key(repo_root)
    if not api_key:
        pytest.skip(
            "Set ADMIN_UI_API_KEY (or SINGLE_USER_API_KEY / NEXT_PUBLIC_X_API_KEY in .env) to run this test."
        )
    return api_key


@pytest.fixture(scope="session")
def admin_ui_server(admin_ui_base_url: str):
    repo_root = Path(__file__).resolve().parents[3]
    with _ensure_admin_ui_running(repo_root, admin_ui_base_url):
        yield


@pytest.mark.e2e
def test_admin_ui_api_key_session_storage_only(
    browser,
    admin_ui_api_key: str,
    admin_ui_base_url: str,
    admin_ui_server,
):
    context = browser.new_context()
    try:
        page = context.new_page()
        page.set_default_timeout(90_000)
        page.goto(f"{admin_ui_base_url}/login", wait_until="domcontentloaded")
        page.get_by_role("heading", name="tldw Admin").wait_for()
        page.wait_for_function("document.readyState === 'complete'")
        page.wait_for_timeout(500)

        api_key_tab = page.locator("button", has_text="API Key").first
        api_key_tab.wait_for(state="visible")

        api_key_input = page.locator("input#apiKey")
        if not api_key_input.is_visible():
            for _ in range(3):
                api_key_tab.click()
                page.wait_for_timeout(300)
                if api_key_input.is_visible():
                    break
                page.evaluate(
                    """
                    const btn = [...document.querySelectorAll('button')]
                      .find(el => (el.textContent || '').trim() === 'API Key');
                    if (btn) btn.click();
                    """
                )
                page.wait_for_timeout(300)
                if api_key_input.is_visible():
                    break

        if not api_key_input.is_visible():
            api_key_input = page.get_by_placeholder("Enter your API key")
        if not api_key_input.is_visible():
            api_key_input = page.locator("input[name='apiKey']")
        api_key_input.wait_for(state="visible")
        api_key_input.fill(admin_ui_api_key)

        submit = page.get_by_role(
            "button",
            name=re.compile(r"(Connect with API Key|Validating\.\.\.)", re.IGNORECASE),
        )
        if submit.is_visible():
            submit.click()
        else:
            api_key_input.press("Enter")
        page.wait_for_url(f"{admin_ui_base_url}/")

        session_key = page.evaluate("sessionStorage.getItem('x_api_key')")
        local_key = page.evaluate("localStorage.getItem('x_api_key')")
        assert session_key == admin_ui_api_key
        assert local_key is None

        page.reload()
        session_key_after_reload = page.evaluate("sessionStorage.getItem('x_api_key')")
        assert session_key_after_reload == admin_ui_api_key
    finally:
        context.close()

    context2 = browser.new_context()
    try:
        page2 = context2.new_page()
        page2.goto(f"{admin_ui_base_url}/login", wait_until="domcontentloaded")
        assert page2.evaluate("sessionStorage.getItem('x_api_key')") is None
    finally:
        context2.close()
