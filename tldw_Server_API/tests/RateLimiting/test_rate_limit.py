import pytest
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from tldw_Server_API.app.core.RateLimiting import Rate_Limit as rate_limit


def _make_request(headers=None) -> Request:
    app = FastAPI()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": headers or [],
        "query_string": b"",
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "app": app,
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_ratelimit_dependency_ignores_token_header(monkeypatch):
    async def fake_check_daily_cap(*_args, **_kwargs):
        return False, 1, {"daily_remaining": 0}

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(rate_limit, "_rg_enabled", lambda: False)
    monkeypatch.setattr(rate_limit, "_enforce_requests_legacy", noop)
    monkeypatch.setattr(rate_limit, "check_daily_cap", fake_check_daily_cap)

    request = _make_request(headers=[(b"x-token-usage", b"999")])
    async for _ctx in rate_limit.ratelimit_dependency(request):
        pass


@pytest.mark.asyncio
async def test_ratelimit_dependency_enforces_server_tokens(monkeypatch):
    async def fake_check_daily_cap(*_args, **_kwargs):
        return False, 1, {"daily_remaining": 0}

    async def noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(rate_limit, "_rg_enabled", lambda: False)
    monkeypatch.setattr(rate_limit, "_enforce_requests_legacy", noop)
    monkeypatch.setattr(rate_limit, "check_daily_cap", fake_check_daily_cap)

    request = _make_request()
    with pytest.raises(HTTPException) as exc:
        async for ctx in rate_limit.ratelimit_dependency(request):
            ctx.add_tokens(10)
    assert exc.value.status_code == 429
