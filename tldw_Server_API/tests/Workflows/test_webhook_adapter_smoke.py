import os
import asyncio
import pytest

from tldw_Server_API.app.core.Workflows.adapters import run_webhook_adapter


@pytest.mark.timeout(10)
def test_webhook_adapter_test_mode(monkeypatch):
    # Force TEST_MODE so adapter short-circuits without network
    monkeypatch.setenv("TEST_MODE", "1")
    cfg = {"url": "https://example.com/echo", "method": "POST", "headers": {}, "body": {"hello": "world"}}
    ctx = {"tenant_id": "default", "user_id": "1"}
    out = asyncio.run(run_webhook_adapter(cfg, ctx))
    assert out.get("dispatched") is False
    assert out.get("test_mode") is True
