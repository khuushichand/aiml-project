"""
command_router.py

Lightweight slash-command router for chat pre-processing.

Stage 4 scope:
- Registry with /time and stub /weather commands
- Per-user, per-command rate limit using TokenBucket from existing limiter
- Simple RBAC hook (no-op by default)
- Metrics logging

Env flags:
- CHAT_COMMANDS_ENABLED: '1' to enable (default: off)
- CHAT_COMMANDS_RATE_LIMIT: per-user RPM per command (default: 10)
- CHAT_COMMAND_INJECTION_MODE: 'system', 'preface', or 'replace' (default: 'system')
- DEFAULT_LOCATION: fallback location for /weather (default: '')
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Callable, Optional

from loguru import logger

from tldw_Server_API.app.core.Chat.rate_limiter import TokenBucket
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.Integrations import weather_providers
from tldw_Server_API.app.core.Metrics import increment_counter
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter

try:
    from tldw_Server_API.app.core.AuthNZ.rbac import user_has_permission as _user_has_permission
except Exception:  # pragma: no cover - fallback if AuthNZ is trimmed in tests
    def _user_has_permission(user_id: int, permission: str) -> bool:  # type: ignore
        return True


SLASH_RE = re.compile(r"^/(\w+)(?:\s+(.*))?$")


def _cfg() -> any | None:
    try:
        return load_comprehensive_config()
    except Exception:
        return None


def _cfg_bool(env_name: str, cfg_key: str, fallback: bool) -> bool:
    v = os.getenv(env_name)
    if isinstance(v, str) and v.strip():
        return v.strip().lower() in {"1", "true", "yes", "on"}
    cp = _cfg()
    if cp and cp.has_section('Chat-Commands'):
        try:
            raw = cp.get('Chat-Commands', cfg_key, fallback=str(fallback))
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}
        except Exception:
            return fallback
    return fallback


def _cfg_int(env_name: str, cfg_key: str, fallback: int) -> int:
    v = os.getenv(env_name)
    if isinstance(v, str) and v.strip():
        try:
            return max(1, int(v))
        except Exception:
            return fallback
    cp = _cfg()
    if cp and cp.has_section('Chat-Commands'):
        try:
            raw = cp.get('Chat-Commands', cfg_key, fallback=str(fallback))
            return max(1, int(str(raw)))
        except Exception:
            return fallback
    return fallback


def _cfg_str(env_name: str, cfg_key: str, fallback: str) -> str:
    v = os.getenv(env_name)
    if isinstance(v, str) and v.strip():
        return v.strip()
    cp = _cfg()
    if cp and cp.has_section('Chat-Commands'):
        try:
            raw = cp.get('Chat-Commands', cfg_key, fallback=fallback)
            return str(raw).strip()
        except Exception:
            return fallback
    return fallback


def commands_enabled() -> bool:
    return _cfg_bool("CHAT_COMMANDS_ENABLED", "commands_enabled", False)


def is_single_user_mode() -> bool:
    """Return True when AuthNZ is configured in single-user mode.

    This helper exists primarily as a test seam for RBAC behavior; production
    code should prefer env/config-driven enforcement.
    """
    try:
        return str(os.getenv("AUTH_MODE", "")).strip().lower() == "single_user"
    except Exception:
        return False


def get_injection_mode() -> str:
    mode = _cfg_str("CHAT_COMMAND_INJECTION_MODE", "injection_mode", "system").lower().strip()
    # Supported modes:
    # - system: inject result as a separate system message
    # - preface: preface the user's message with the command result
    # - replace: replace the user's message content with the command result
    return mode if mode in {"system", "preface", "replace"} else "system"


def _per_command_rpm() -> int:
    return _cfg_int("CHAT_COMMANDS_RATE_LIMIT", "commands_rate_limit", 10)


@dataclass
class CommandContext:
    user_id: str = "anonymous"
    conversation_id: str | None = None
    request_meta: dict | None = None
    auth_user_id: int | None = None  # numeric user id when available for RBAC


@dataclass
class CommandResult:
    ok: bool
    command: str
    content: str
    metadata: dict


Handler = Callable[[CommandContext, Optional[str]], CommandResult]


@dataclass
class CommandSpec:
    name: str
    description: str
    handler: Handler
    allowed_roles: list[str] | None = None  # reserved for future RBAC
    required_permission: str | None = None  # permission string when enforcement is enabled


_registry: dict[str, CommandSpec] = {}
_buckets: dict[tuple[str, str], TokenBucket] = {}


def register_command(
    name: str,
    description: str,
    handler: Handler,
    allowed_roles: list[str] | None = None,
    required_permission: str | None = None,
) -> None:
    _registry[name.lower()] = CommandSpec(
        name=name.lower(),
        description=description,
        handler=handler,
        allowed_roles=allowed_roles,
        required_permission=required_permission,
    )


def list_commands() -> list[dict[str, str]]:
    return [{"name": spec.name, "description": spec.description} for spec in _registry.values()]


def parse_slash_command(message: str) -> tuple[str, str | None] | None:
    if not isinstance(message, str):
        return None
    m = SLASH_RE.match(message.strip())
    if not m:
        return None
    cmd = (m.group(1) or "").lower()
    args = (m.group(2) or "").strip() or None
    if cmd in _registry:
        return cmd, args
    return None


def _acquire_bucket(user_id: str, command: str) -> TokenBucket:
    key = (user_id or "anonymous", command)
    if key not in _buckets:
        rpm = _per_command_rpm()
        _buckets[key] = TokenBucket(capacity=rpm, refill_rate=rpm / 60.0)
    return _buckets[key]


def dispatch_command(ctx: CommandContext, command: str, args: str | None) -> CommandResult:
    raise RuntimeError(
        "command_router.dispatch_command has been removed. "
        "Use async_dispatch_command(...) or the chat orchestrator "
        "(achat or its sync wrapper) instead."
    )


async def async_dispatch_command(ctx: CommandContext, command: str, args: str | None) -> CommandResult:
    """Async variant of dispatch_command that uses TokenBucket.consume() safely.

    Mirrors dispatch_command behavior but awaits the bucket's consume method to
    respect its asyncio.Lock and prevent race conditions under concurrency.
    """
    cmd = command.lower()
    spec = _registry.get(cmd)
    if not spec:
        return CommandResult(ok=False, command=cmd, content=f"Unknown command: /{cmd}", metadata={"error": "unknown_command"})

    # RBAC: optional enforcement via env flag
    rbac_enforced = _cfg_bool("CHAT_COMMANDS_REQUIRE_PERMISSIONS", "require_permissions", False)
    if rbac_enforced and spec.required_permission:
        permitted = False
        details = {"checked": True, "required_permission": spec.required_permission}
        try:
            if ctx.auth_user_id is not None:
                permitted = bool(_user_has_permission(int(ctx.auth_user_id), spec.required_permission))
            else:
                permitted = False
        except Exception:
            permitted = False
        if not permitted:
            log_counter("chat_command_error", labels={"command": cmd, "reason": "permission_denied"})
            try:
                increment_counter("chat_command_errors_total", labels={"command": cmd, "reason": "permission_denied"})
                increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "denied"})
            except Exception:
                pass
            details.update({"permitted": False})
            return CommandResult(
                ok=False,
                command=cmd,
                content=f"Permission denied for /{cmd}",
                metadata={"error": "permission_denied", **details},
            )

    # Per-user per-command rate limiting (safe, lock-respecting)
    bucket = _acquire_bucket(ctx.user_id, cmd)
    allowed = await bucket.consume(1)
    if not allowed:
        log_counter("chat_command_error", labels={"command": cmd, "reason": "rate_limited"})
        try:
            increment_counter("chat_command_errors_total", labels={"command": cmd, "reason": "rate_limited"})
            increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "rate_limited"})
        except Exception:
            pass
        return CommandResult(
            ok=False,
            command=cmd,
            content=f"Command /{cmd} is rate limited. Please try again shortly.",
            metadata={"error": "rate_limited"},
        )

    try:
        res = spec.handler(ctx, args)
        if asyncio.iscoroutine(res):  # future-proof if handlers become async
            res = await res  # type: ignore[assignment]
        # annotate result metadata with RBAC info when applicable
        if rbac_enforced and spec.required_permission:
            try:
                res.metadata = {**(res.metadata or {}), "rbac": {"checked": True, "required_permission": spec.required_permission, "permitted": True}}
            except Exception:
                pass
        log_counter("chat_command_invoked", labels={"command": cmd})
        try:
            increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "success"})
        except Exception:
            pass
        return res
    except Exception as e:
        logger.error(f"Error executing /{cmd}: {e}", exc_info=True)
        log_counter("chat_command_error", labels={"command": cmd, "reason": "exception"})
        try:
            increment_counter("chat_command_errors_total", labels={"command": cmd, "reason": "exception"})
            increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "error"})
        except Exception:
            pass
        return CommandResult(ok=False, command=cmd, content=f"Command /{cmd} failed: {e}", metadata={"error": "exception"})


# -----------------------------
# Built-in command handlers
# -----------------------------

def _time_handler(ctx: CommandContext, args: str | None) -> CommandResult:
    from datetime import datetime
    try:
        # Optional timezone support via zoneinfo
        tzlabel = (args or "").strip() if args else None
        dt = None
        tzused = "local"
        if tzlabel:
            try:
                from zoneinfo import ZoneInfo  # Python 3.9+
                dt = datetime.now(ZoneInfo(tzlabel))
                tzused = tzlabel
            except Exception:
                dt = datetime.now()
                tzused = "local"
        else:
            dt = datetime.now()
        text = dt.strftime("%Y-%m-%d %H:%M:%S")
        return CommandResult(
            ok=True,
            command="time",
            content=f"Current time ({tzused}): {text}",
            metadata={"tz": tzused},
        )
    except Exception as e:
        return CommandResult(ok=False, command="time", content=f"Time lookup failed: {e}", metadata={"error": "time_error"})


def _weather_handler(ctx: CommandContext, args: str | None) -> CommandResult:
    location = (args or "").strip()
    if not location:
        location = _cfg_str("DEFAULT_LOCATION", "default_location", "").strip()
    # Obtain client via test seam so monkeypatches take effect
    try:
        client = get_weather_client(ctx)
    except TypeError:
        # Backward-compatible: some tests patch a zero-arg seam
        client = get_weather_client()
    try:
        result = client.get_current(location=location or None)
        if result.ok:
            return CommandResult(ok=True, command="weather", content=result.summary, metadata=result.metadata)
        return CommandResult(ok=False, command="weather", content=result.summary, metadata={"error": "unavailable"})
    except Exception as e:
        logger.error(f"Weather provider error: {e}", exc_info=True)
        return CommandResult(ok=False, command="weather", content=f"Weather unavailable: {e}", metadata={"error": "exception"})


# Register built-in commands on import
register_command("time", "Show the current time (optional TZ).", _time_handler, required_permission="chat.commands.time")
register_command("weather", "Show current weather for a location.", _weather_handler, required_permission="chat.commands.weather")

# --- Test seam helpers ---
def get_weather_client(ctx: CommandContext | None = None):
    """Thin wrapper to allow tests to monkeypatch the weather client at the router level.

    Tests expect to patch command_router.get_weather_client; delegate to the
    actual provider factory so production code continues to use the unified
    weather providers module.
    """
    return weather_providers.get_weather_client()
