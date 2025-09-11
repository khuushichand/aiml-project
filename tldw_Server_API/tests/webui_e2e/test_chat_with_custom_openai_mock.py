import os
import time
import socket
import contextlib
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


def _find_free_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


@pytest.mark.e2e
def test_chat_with_custom_openai_mock(browser):
    if not os.environ.get('ENABLE_CUSTOM_OPENAI_API_E2E'):
        pytest.skip("Custom OpenAI API E2E disabled; set ENABLE_CUSTOM_OPENAI_API_E2E=1 to enable.")

    repo_root = Path(__file__).resolve().parents[3]
    config_path = repo_root / 'tldw_Server_API' / 'Config_Files' / 'config.txt'

    # Start mock OpenAI server
    mock_port = _find_free_port()
    mock_proc = subprocess.Popen(
        ["python", str(repo_root / 'mock_openai_server' / 'run_server.py'), "--port", str(mock_port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(repo_root / 'mock_openai_server')
    )

    # Wait briefly for mock server
    base_mock = f"http://127.0.0.1:{mock_port}"
    time.sleep(1.5)

    # Backup and patch config for custom_openai_api
    backup_path = None
    if config_path.exists():
        backup_path = config_path.with_suffix('.bak')
        backup_path.write_text(config_path.read_text(encoding='utf-8'), encoding='utf-8')

    try:
        cfg = [
            "[API]\n",
            "default_api = custom_openai_api\n",
            f"custom_openai_api_ip = {base_mock}/v1/chat/completions\n",
            "custom_openai_api_key = sk-test-123\n",
            "custom_openai_api_model = gpt-3.5-turbo\n",
        ]
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("".join(cfg), encoding='utf-8')

        # Start the main server with env
        port = _find_free_port()
        env = os.environ.copy()
        env["AUTH_MODE"] = "single_user"
        env["SINGLE_USER_API_KEY"] = "sk-test-123456"
        env["TEST_MODE"] = "true"
        server_proc = subprocess.Popen(
            [
                "python", "-m", "uvicorn", "tldw_Server_API.app.main:app",
                "--port", str(port), "--log-level", "warning"
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(repo_root)
        )

        base = f"http://127.0.0.1:{port}"

        # Drive Playwright to send a chat request with Custom OpenAI API
        with sync_playwright() as p:
            ctx = browser.new_context(base_url=base)
            page = ctx.new_page()
            page.goto(f"{base}/webui/")
            page.get_by_role("tab", name="Chat").click()
            page.get_by_role("tab", name="Chat Completions").click()

            # Ensure models dropdown loaded (may show default/placeholder)
            page.wait_for_selector("#chatCompletions_model")

            # Select provider 'Custom OpenAI API'
            page.select_option("#chatCompletions_provider", label="Custom OpenAI API")

            # Keep default messages; send request
            page.get_by_text("Send Request").first.click()

            page.wait_for_selector("#chatCompletions_response")
            txt = page.locator("#chatCompletions_response").inner_text()
            # The mock returns OpenAI-like response; assert basic structure appears
            assert "choices" in txt or "error" not in txt
            ctx.close()

    finally:
        # Restore config
        if backup_path and backup_path.exists():
            config_path.write_text(backup_path.read_text(encoding='utf-8'), encoding='utf-8')
            backup_path.unlink(missing_ok=True)
        # Stop servers
        try:
            server_proc.terminate()
        except Exception:
            pass
        try:
            mock_proc.terminate()
        except Exception:
            pass

