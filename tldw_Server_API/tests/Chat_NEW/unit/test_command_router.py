from typing import Optional

import asyncio
import pytest

from tldw_Server_API.app.core.Chat import command_router


@pytest.fixture(autouse=True)
def _reset_command_router_buckets():
    command_router._buckets.clear()
    command_router._global_buckets.clear()
    yield
    command_router._buckets.clear()
    command_router._global_buckets.clear()


@pytest.mark.unit
def test_commands_enabled_accepts_single_letter_y(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "y")
    assert command_router.commands_enabled() is True


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
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_GLOBAL", "100")
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


@pytest.mark.unit
def test_list_commands_includes_rich_metadata(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_USER", "3/min")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_GLOBAL", "30/min")

    by_name = {entry["name"]: entry for entry in command_router.list_commands()}
    time_cmd = by_name["time"]
    weather_cmd = by_name["weather"]

    assert time_cmd["usage"] == "/time [timezone]"
    assert time_cmd["args"] == ["timezone"]
    assert time_cmd["requires_api_key"] is True
    assert time_cmd["rbac_required"] is True
    assert "per-user 3/min" in time_cmd["rate_limit"]
    assert "global 30/min" in time_cmd["rate_limit"]
    assert weather_cmd["usage"] == "/weather [location]"
    assert weather_cmd["args"] == ["location"]


@pytest.mark.asyncio
async def test_rbac_enforcement(monkeypatch):
    # Enable commands and RBAC enforcement
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_REQUIRE_PERMISSIONS", "1")

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
async def test_rate_limit_parses_user_rpm_suffix(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_USER", "2/min")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_GLOBAL", "100/min")

    ctx = command_router.CommandContext(user_id="rpm_suffix_user")
    assert (await command_router.async_dispatch_command(ctx, "time", None)).ok
    assert (await command_router.async_dispatch_command(ctx, "time", None)).ok

    denied = await command_router.async_dispatch_command(ctx, "time", None)
    assert not denied.ok
    assert denied.metadata.get("scope") == "user"


@pytest.mark.asyncio
async def test_rate_limit_global_per_command(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_USER", "100/min")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_GLOBAL", "1/min")

    first = await command_router.async_dispatch_command(command_router.CommandContext(user_id="u1"), "time", None)
    second = await command_router.async_dispatch_command(command_router.CommandContext(user_id="u2"), "time", None)

    assert first.ok
    assert not second.ok
    assert second.metadata.get("error") == "rate_limited"
    assert second.metadata.get("scope") == "global"


@pytest.mark.asyncio
async def test_command_output_truncation(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_GLOBAL", "100")
    monkeypatch.setenv("CHAT_COMMANDS_MAX_CHARS", "20")

    class LongClient:
        def get_current(self, location: Optional[str] = None, lat=None, lon=None):
            class Result:
                ok = True
                summary = "very long weather summary " * 8
                metadata = {"provider": "test"}

            return Result()

    from tldw_Server_API.app.core.Integrations import weather_providers

    monkeypatch.setattr(weather_providers, "get_weather_client", lambda: LongClient())

    res = await command_router.async_dispatch_command(
        command_router.CommandContext(user_id="truncate-user"),
        "weather",
        "Boston",
    )
    assert res.ok
    assert len(res.content) <= 20
    assert res.metadata.get("truncated") is True
    assert res.metadata.get("max_chars") == 20
    assert int(res.metadata.get("original_chars", 0)) > 20


@pytest.mark.asyncio
async def test_async_dispatch_command_concurrent_respects_rate_limit(monkeypatch):
    monkeypatch.setenv("CHAT_COMMANDS_ENABLED", "1")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT", "5")
    monkeypatch.setenv("CHAT_COMMANDS_RATE_LIMIT_GLOBAL", "100")

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
