import pytest
from fastapi import HTTPException, status
from starlette.requests import Request

import tldw_Server_API.app.api.v1.API_Deps.setup_deps as setup_deps
from tldw_Server_API.app.api.v1.API_Deps.setup_deps import require_local_setup_access


@pytest.fixture(autouse=True)
def _reset_remote_cache():
    setup_deps.reset_remote_access_cache(None)
    yield
    setup_deps.reset_remote_access_cache(None)


@pytest.mark.asyncio
async def test_setup_guard_blocks_loopback_spoof(monkeypatch):
    """Remote hosts cannot spoof loopback via X-Forwarded-For."""
    monkeypatch.delenv("TLDW_SETUP_ALLOW_REMOTE", raising=False)
    monkeypatch.delenv("TLDW_SETUP_TRUST_PROXY", raising=False)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/setup/config",
        "client": ("203.0.113.50", 34567),
        "headers": [
            (b"host", b"localhost"),
            (b"x-forwarded-for", b"127.0.0.1"),
        ],
    }

    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        await require_local_setup_access(request)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_setup_guard_allows_local_browser(monkeypatch):
    """Direct browser on the host can access setup endpoints."""
    monkeypatch.delenv("TLDW_SETUP_ALLOW_REMOTE", raising=False)
    monkeypatch.delenv("TLDW_SETUP_TRUST_PROXY", raising=False)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/setup/config",
        "client": ("127.0.0.1", 54321),
        "headers": [
            (b"host", b"localhost"),
        ],
    }
    request = Request(scope)
    await require_local_setup_access(request)


@pytest.mark.asyncio
async def test_setup_guard_allows_local_proxy(monkeypatch):
    """Loopback proxy plus loopback forwarded IP is accepted."""
    monkeypatch.delenv("TLDW_SETUP_ALLOW_REMOTE", raising=False)
    monkeypatch.setenv("TLDW_SETUP_TRUST_PROXY", "1")

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/setup/config",
        "client": ("127.0.0.1", 12345),
        "headers": [
            (b"host", b"localhost"),
            (b"x-forwarded-for", b"127.0.0.1"),
        ],
    }
    request = Request(scope)
    await require_local_setup_access(request)


@pytest.mark.asyncio
async def test_setup_guard_config_allows_remote(monkeypatch):
    """Config flag can relax locality restriction."""
    monkeypatch.delenv("TLDW_SETUP_ALLOW_REMOTE", raising=False)
    monkeypatch.delenv("TLDW_SETUP_TRUST_PROXY", raising=False)
    setup_deps.reset_remote_access_cache(True)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/setup/config",
        "client": ("198.51.100.25", 4242),
        "headers": [
            (b"host", b"example.com"),
        ],
    }
    request = Request(scope)
    await require_local_setup_access(request)
