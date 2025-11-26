import os
from typing import Optional

import asyncio
import pytest

from tldw_Server_API.app.core.Chat import command_router


@pytest.mark.asyncio
async def test_parse_and_dispatch_time(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    parsed = command_router.parse_slash_command("/time")
    assert parsed is not None
    name, args = parsed
    assert name == "time"
    ctx = command_router.CommandContext(user_id="u1")
    res = await command_router.async_dispatch_command(ctx, name, args)
    assert res.ok
    assert "Current time" in res.content


@pytest.mark.asyncio
async def test_rate_limit_per_user_per_command(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT", "1")
    # Ensure a fresh process bucket by using a unique user id
    ctx = command_router.CommandContext(user_id="rl_user")
    # First call allowed
    res1 = await command_router.async_dispatch_command(ctx, "time", None)
    assert res1.ok
    # Second call immediately after should be rate-limited
    res2 = await command_router.async_dispatch_command(ctx, "time", None)
    assert not res2.ok
    assert "rate limited" in res2.content.lower()


@pytest.mark.asyncio
async def test_weather_stub(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")

    class OkClient:
        def get_current(self, location: Optional[str] = None, lat=None, lon=None):
            class Result:
                ok = True
                summary = f"Sunny at {location or 'somewhere'}"
                metadata = {"provider": "test"}

            return Result()

    # Patch provider factory
    from tldw_Server_API.app.core.Integrations import weather_providers

    monkeypatch.setattr(weather_providers, "get_weather_client", lambda: OkClient())

    ctx = command_router.CommandContext(user_id="u2")
    res = await command_router.async_dispatch_command(ctx, "weather", "Boston")
    assert res.ok
    assert "Sunny" in res.content


@pytest.mark.asyncio
async def test_rbac_enforcement(monkeypatch):
    # Enable commands and RBAC enforcement
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_REQUIRE_PERMISSIONS", "1")

    # Force multi-user mode for this test
    monkeypatch.setattr(command_router, "is_single_user_mode", lambda: False)

    # Without auth_user_id, permission should be denied for a command requiring permission
    ctx = command_router.CommandContext(user_id="anon", auth_user_id=None)
    denied = await command_router.async_dispatch_command(ctx, "time", None)
    assert not denied.ok
    assert denied.metadata.get("error") == "permission_denied"

    # With auth_user_id and granted permission, should pass
    monkeypatch.setattr(command_router, "_user_has_permission", lambda uid, perm: True)
    ctx2 = command_router.CommandContext(user_id="u", auth_user_id=42)
    allowed = await command_router.async_dispatch_command(ctx2, "time", None)
    assert allowed.ok


def test_dispatch_command_removed_raises():
    ctx = command_router.CommandContext(user_id="legacy")
    with pytest.raises(RuntimeError):
        command_router.dispatch_command(ctx, "time", None)


@pytest.mark.asyncio
async def test_async_dispatch_command_concurrent_respects_rate_limit(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT", "5")

    ctx = command_router.CommandContext(user_id="async_rl_user")

    async def call():
        return await command_router.async_dispatch_command(ctx, "time", None)

    results = await asyncio.gather(*[call() for _ in range(10)])
    ok = [r for r in results if r.ok]
    limited = [r for r in results if not r.ok and "rate limited" in r.content.lower()]

    # At most the configured limit should be allowed.
    assert len(ok) <= 5
    # Under concurrent load, we should see some rate-limited responses.
    assert len(limited) >= 1
