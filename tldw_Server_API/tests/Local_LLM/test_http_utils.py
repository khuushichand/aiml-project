import asyncio
import warnings
import httpx
import pytest

from tldw_Server_API.app.core.Local_LLM.http_utils import (
    request_json,
    redact_cmd_args,
    wait_for_http_ready,
    LocalHTTPStatusError,
)


class FakeClient:
    def __init__(self):
        self.calls = 0

    async def request(self, method, url, json=None, headers=None):
        self.calls += 1
        req = httpx.Request(method, url)
        if self.calls == 1:
            resp = httpx.Response(500, request=req, text="server error")
            # Mimic status without raising; request_json should retry on 5xx
            return resp
        return httpx.Response(200, request=req, json={"ok": True})


@pytest.mark.asyncio
async def test_request_json_retries_on_5xx():
    client = FakeClient()
    # Suppress deprecation warning for FakeClient
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        data = await request_json(client, "GET", "http://x/y", retries=1, backoff=0)
    assert data["ok"] is True
    assert client.calls == 2


@pytest.mark.asyncio
async def test_request_json_retries_zero_makes_single_attempt():
    client = FakeClient()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(LocalHTTPStatusError):
            await request_json(client, "GET", "http://x/y", retries=0, backoff=0)
    assert client.calls == 1


# --- Tests for redact_cmd_args improvements ---


def test_redact_cmd_args_basic():
    """Test basic space-separated flag redaction."""
    args = ["cmd", "--api-key", "secret123", "-m", "model.gguf"]
    result = redact_cmd_args(args)
    assert result == ["cmd", "--api-key", "REDACTED", "-m", "model.gguf"]


def test_redact_cmd_args_equals_format():
    """Test equals-separated flag redaction (--flag=value)."""
    args = ["cmd", "--api-key=secret123", "-m", "model.gguf"]
    result = redact_cmd_args(args)
    assert result == ["cmd", "--api-key=REDACTED", "-m", "model.gguf"]


def test_redact_cmd_args_multiple_flags():
    """Test redaction of multiple sensitive flags."""
    args = ["cmd", "--hf-token", "tok1", "--password", "pass", "--other", "val"]
    result = redact_cmd_args(args)
    assert result == ["cmd", "--hf-token", "REDACTED", "--password", "REDACTED", "--other", "val"]


def test_redact_cmd_args_new_flags():
    """Test redaction of newly added sensitive flags."""
    new_flags = [
        "--password",
        "--secret",
        "--auth",
        "--bearer",
        "--credential",
        "--credentials",
        "--access-token",
        "--refresh-token",
        "--client-secret",
    ]
    for flag in new_flags:
        args = ["cmd", flag, "sensitive_value"]
        result = redact_cmd_args(args)
        assert result == ["cmd", flag, "REDACTED"], f"Failed for flag: {flag}"


def test_redact_cmd_args_mixed_formats():
    """Test redaction with mixed space and equals formats."""
    args = ["cmd", "--api-key=secret1", "--hf-token", "secret2", "--password=secret3"]
    result = redact_cmd_args(args)
    assert result == ["cmd", "--api-key=REDACTED", "--hf-token", "REDACTED", "--password=REDACTED"]


def test_redact_cmd_args_non_sensitive_equals():
    """Test that non-sensitive equals args are not redacted."""
    args = ["cmd", "--model=gpt-4", "--port=8080"]
    result = redact_cmd_args(args)
    assert result == ["cmd", "--model=gpt-4", "--port=8080"]


# --- Tests for wait_for_http_ready improvements ---


@pytest.mark.asyncio
async def test_wait_for_http_ready_accepts_200(monkeypatch):
    """Test that 200 OK is accepted as ready."""
    call_count = {"n": 0}

    async def mock_afetch(method, url, client):
        call_count["n"] += 1
        req = httpx.Request(method, url)
        return httpx.Response(200, request=req)

    import tldw_Server_API.app.core.Local_LLM.http_utils as http_utils

    monkeypatch.setattr(http_utils, "afetch", mock_afetch)

    result = await wait_for_http_ready("http://localhost:8080", timeout_total=1.0, interval=0.1)
    assert result is True
    assert call_count["n"] >= 1


@pytest.mark.asyncio
async def test_wait_for_http_ready_rejects_404_by_default(monkeypatch):
    """Test that 404 is NOT accepted as ready by default (stricter check)."""
    call_count = {"n": 0}

    async def mock_afetch(method, url, client):
        call_count["n"] += 1
        req = httpx.Request(method, url)
        return httpx.Response(404, request=req)

    import tldw_Server_API.app.core.Local_LLM.http_utils as http_utils

    monkeypatch.setattr(http_utils, "afetch", mock_afetch)

    result = await wait_for_http_ready("http://localhost:8080", timeout_total=0.5, interval=0.1)
    assert result is False


@pytest.mark.asyncio
async def test_wait_for_http_ready_legacy_accepts_404(monkeypatch):
    """Test that legacy mode (accept_any_non_5xx=True) accepts 404."""
    call_count = {"n": 0}

    async def mock_afetch(method, url, client):
        call_count["n"] += 1
        req = httpx.Request(method, url)
        return httpx.Response(404, request=req)

    import tldw_Server_API.app.core.Local_LLM.http_utils as http_utils

    monkeypatch.setattr(http_utils, "afetch", mock_afetch)

    result = await wait_for_http_ready(
        "http://localhost:8080", timeout_total=1.0, interval=0.1, accept_any_non_5xx=True  # Legacy mode
    )
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_http_ready_rejects_5xx(monkeypatch):
    """Test that 5xx errors are not accepted in any mode."""

    async def mock_afetch(method, url, client):
        req = httpx.Request(method, url)
        return httpx.Response(503, request=req)

    import tldw_Server_API.app.core.Local_LLM.http_utils as http_utils

    monkeypatch.setattr(http_utils, "afetch", mock_afetch)

    result = await wait_for_http_ready(
        "http://localhost:8080", timeout_total=0.5, interval=0.1, accept_any_non_5xx=True
    )
    assert result is False


# --- Test for deprecation warning on non-AsyncClient ---


@pytest.mark.asyncio
async def test_request_json_deprecation_warning():
    """Test that using non-AsyncClient emits a deprecation warning."""
    client = FakeClient()
    with pytest.warns(DeprecationWarning, match="non-httpx.AsyncClient.*deprecated"):
        await request_json(client, "GET", "http://x/y", retries=1, backoff=0)
