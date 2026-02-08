"""
command_router.py

Lightweight slash-command router for chat pre-processing.

Scope:
- Registry with /time and /weather commands
- Per-user + global per-command rate limits using TokenBucket
- Optional RBAC enforcement hooks
- Command output truncation for safe injection paths
- Metrics logging

Env flags:
- CHAT_COMMANDS_ENABLED: '1' to enable (default: off)
- CHAT_COMMANDS_RATE_LIMIT_USER: per-user RPM per command (default: 10)
- CHAT_COMMANDS_RATE_LIMIT_GLOBAL: global RPM per command (default: 100)
- CHAT_COMMANDS_RATE_LIMIT: backward-compatible alias for USER limit
- CHAT_COMMANDS_MAX_CHARS: max chars in command output (default: 300)
- CHAT_COMMAND_INJECTION_MODE: 'system', 'preface', or 'replace' (default: 'system')
- DEFAULT_LOCATION: fallback location for /weather (default: '')
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from loguru import logger

from tldw_Server_API.app.core.Chat.rate_limiter import TokenBucket
from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.Integrations import weather_providers
from tldw_Server_API.app.core.Metrics import increment_counter
from tldw_Server_API.app.core.Metrics.metrics_logger import log_counter
from tldw_Server_API.app.core.testing import is_truthy

_COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    UnicodeDecodeError,
    ValueError,
)

try:
    from tldw_Server_API.app.core.AuthNZ.rbac import user_has_permission as _user_has_permission
except ImportError:  # pragma: no cover - fallback if AuthNZ is trimmed in tests
    def _user_has_permission(user_id: int, permission: str) -> bool:  # type: ignore
        return True


SLASH_RE = re.compile(r"^/(\w+)(?:\s+(.*))?$")
RPM_VALUE_RE = re.compile(
    r"^\s*(?P<value>\d+)\s*(?:$|/(?P<unit>m|min|minute|minutes)|\s+per\s+(?P<unit_per>m|min|minute|minutes))\s*$",
    re.IGNORECASE,
)


def _cfg() -> any | None:
    try:
        return load_comprehensive_config()
    except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
        return None


def _cfg_bool(env_name: str, cfg_key: str, fallback: bool) -> bool:
    v = os.getenv(env_name)
    if isinstance(v, str) and v.strip():
        return is_truthy(v)
    cp = _cfg()
    if cp and cp.has_section('Chat-Commands'):
        try:
            raw = cp.get('Chat-Commands', cfg_key, fallback=str(fallback))
            return is_truthy(raw)
        except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
            return fallback
    return fallback


def _cfg_int(env_name: str, cfg_key: str, fallback: int) -> int:
    v = os.getenv(env_name)
    if isinstance(v, str) and v.strip():
        try:
            return max(1, int(v))
        except (TypeError, ValueError):
            return fallback
    cp = _cfg()
    if cp and cp.has_section('Chat-Commands'):
        try:
            raw = cp.get('Chat-Commands', cfg_key, fallback=str(fallback))
            return max(1, int(str(raw)))
        except (TypeError, ValueError):
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
        except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
            return fallback
    return fallback


def _parse_positive_int(raw: object) -> int | None:
    try:
        return max(1, int(str(raw).strip()))
    except (TypeError, ValueError):
        return None


def _parse_rpm(raw: object) -> int | None:
    if isinstance(raw, int):
        return max(1, raw)
    text = str(raw).strip().lower()
    if not text:
        return None
    m = RPM_VALUE_RE.match(text)
    if not m:
        return None
    try:
        return max(1, int(m.group("value")))
    except (TypeError, ValueError):
        return None


def _cfg_int_alias(
    env_names: tuple[str, ...],
    cfg_keys: tuple[str, ...],
    fallback: int,
    *,
    parse_rpm: bool = False,
) -> int:
    parser = _parse_rpm if parse_rpm else _parse_positive_int
    for env_name in env_names:
        raw = os.getenv(env_name)
        if isinstance(raw, str) and raw.strip():
            parsed = parser(raw)
            if parsed is not None:
                return parsed
    cp = _cfg()
    if cp and cp.has_section("Chat-Commands"):
        for cfg_key in cfg_keys:
            with contextlib.suppress(_COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS):
                raw = cp.get("Chat-Commands", cfg_key, fallback=None)
                if raw is None:
                    continue
                parsed = parser(raw)
                if parsed is not None:
                    return parsed
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
    except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
        return False


def get_injection_mode() -> str:
    mode = _cfg_str("CHAT_COMMAND_INJECTION_MODE", "injection_mode", "system").lower().strip()
    # Supported modes:
    # - system: inject result as a separate system message
    # - preface: preface the user's message with the command result
    # - replace: replace the user's message content with the command result
    return mode if mode in {"system", "preface", "replace"} else "system"


def _per_command_user_rpm() -> int:
    return _cfg_int_alias(
        ("CHAT_COMMANDS_RATE_LIMIT_USER", "CHAT_COMMANDS_RATE_LIMIT"),
        ("commands_rate_limit_user", "commands_rate_limit"),
        10,
        parse_rpm=True,
    )


def _per_command_global_rpm() -> int:
    return _cfg_int_alias(
        ("CHAT_COMMANDS_RATE_LIMIT_GLOBAL",),
        ("commands_rate_limit_global",),
        100,
        parse_rpm=True,
    )


def _per_command_rpm() -> int:
    # Backward-compatible seam retained for older tests.
    return _per_command_user_rpm()


def _command_max_chars() -> int:
    return _cfg_int_alias(
        ("CHAT_COMMANDS_MAX_CHARS",),
        ("commands_max_chars",),
        300,
        parse_rpm=False,
    )


def default_rate_limit_display() -> str:
    return f"per-user {_per_command_user_rpm()}/min, global {_per_command_global_rpm()}/min"


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
    metadata: dict[str, Any]


Handler = Callable[[CommandContext, Optional[str]], CommandResult]


@dataclass
class CommandSpec:
    name: str
    description: str
    handler: Handler
    allowed_roles: list[str] | None = None  # reserved for future RBAC
    required_permission: str | None = None  # permission string when enforcement is enabled
    usage: str | None = None
    args: list[str] | None = None
    requires_api_key: bool = True
    rate_limit: str | None = None
    rbac_required: bool | None = None


_registry: dict[str, CommandSpec] = {}
_buckets: dict[tuple[str, str], TokenBucket] = {}
_global_buckets: dict[str, TokenBucket] = {}


def register_command(
    name: str,
    description: str,
    handler: Handler,
    allowed_roles: list[str] | None = None,
    required_permission: str | None = None,
    usage: str | None = None,
    args: list[str] | None = None,
    requires_api_key: bool = True,
    rate_limit: str | None = None,
    rbac_required: bool | None = None,
) -> None:
    computed_rbac_required = bool(required_permission) if rbac_required is None else bool(rbac_required)
    _registry[name.lower()] = CommandSpec(
        name=name.lower(),
        description=description,
        handler=handler,
        allowed_roles=allowed_roles,
        required_permission=required_permission,
        usage=usage,
        args=list(args or []),
        requires_api_key=bool(requires_api_key),
        rate_limit=rate_limit,
        rbac_required=computed_rbac_required,
    )


def list_commands() -> list[dict[str, Any]]:
    default_rate_limit = default_rate_limit_display()
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "required_permission": spec.required_permission,
            "usage": spec.usage,
            "args": list(spec.args or []),
            "requires_api_key": bool(spec.requires_api_key),
            "rate_limit": spec.rate_limit or default_rate_limit,
            "rbac_required": (
                bool(spec.required_permission)
                if spec.rbac_required is None
                else bool(spec.rbac_required)
            ),
        }
        for spec in _registry.values()
    ]


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
        rpm = _per_command_user_rpm()
        _buckets[key] = TokenBucket(capacity=rpm, refill_rate=rpm / 60.0)
    return _buckets[key]


def _acquire_global_bucket(command: str) -> TokenBucket:
    key = command
    if key not in _global_buckets:
        rpm = _per_command_global_rpm()
        _global_buckets[key] = TokenBucket(capacity=rpm, refill_rate=rpm / 60.0)
    return _global_buckets[key]


def _finalize_result(result: CommandResult) -> CommandResult:
    source = result.content if isinstance(result.content, str) else str(result.content)
    max_chars = _command_max_chars()
    truncated = False
    content = source
    if max_chars > 0 and len(source) > max_chars:
        truncated = True
        if max_chars <= 3:
            content = source[:max_chars]
        else:
            content = f"{source[:max_chars - 3].rstrip()}..."

    metadata = dict(result.metadata or {})
    metadata.setdefault("max_chars", max_chars)
    if truncated:
        metadata["truncated"] = True
        metadata["original_chars"] = len(source)
        with contextlib.suppress(_COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS):
            increment_counter("chat_command_output_truncated_total", labels={"command": result.command})
    return CommandResult(
        ok=bool(result.ok),
        command=result.command,
        content=content,
        metadata=metadata,
    )


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
        return _finalize_result(
            CommandResult(
                ok=False,
                command=cmd,
                content=f"Unknown command: /{cmd}",
                metadata={"error": "unknown_command"},
            )
        )

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
        except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
            permitted = False
        if not permitted:
            log_counter("chat_command_error", labels={"command": cmd, "reason": "permission_denied"})
            try:
                increment_counter("chat_command_errors_total", labels={"command": cmd, "reason": "permission_denied"})
                increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "denied"})
            except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
                pass
            details.update({"permitted": False})
            return _finalize_result(
                CommandResult(
                    ok=False,
                    command=cmd,
                    content=f"Permission denied for /{cmd}",
                    metadata={"error": "permission_denied", **details},
                )
            )

    # Global per-command and per-user per-command rate limiting (safe, lock-respecting)
    global_bucket = _acquire_global_bucket(cmd)
    global_allowed = await global_bucket.consume(1)
    if not global_allowed:
        log_counter("chat_command_error", labels={"command": cmd, "reason": "rate_limited"})
        try:
            increment_counter("chat_command_errors_total", labels={"command": cmd, "reason": "rate_limited"})
            increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "rate_limited"})
        except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
            pass
        return _finalize_result(
            CommandResult(
                ok=False,
                command=cmd,
                content=f"Command /{cmd} is globally rate limited. Please try again shortly.",
                metadata={"error": "rate_limited", "scope": "global"},
            )
        )

    bucket = _acquire_bucket(ctx.user_id, cmd)
    allowed = await bucket.consume(1)
    if not allowed:
        with contextlib.suppress(_COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS):
            await global_bucket.refund(1)
        log_counter("chat_command_error", labels={"command": cmd, "reason": "rate_limited"})
        try:
            increment_counter("chat_command_errors_total", labels={"command": cmd, "reason": "rate_limited"})
            increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "rate_limited"})
        except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
            pass
        return _finalize_result(
            CommandResult(
                ok=False,
                command=cmd,
                content=f"Command /{cmd} is rate limited. Please try again shortly.",
                metadata={"error": "rate_limited", "scope": "user"},
            )
        )

    try:
        res = spec.handler(ctx, args)
        if asyncio.iscoroutine(res):  # future-proof if handlers become async
            res = await res  # type: ignore[assignment]
        if not isinstance(res, CommandResult):
            raise TypeError(f"Command handler for /{cmd} returned {type(res)}")
        # annotate result metadata with RBAC info when applicable
        if rbac_enforced and spec.required_permission:
            with contextlib.suppress(_COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS):
                res.metadata = {
                    **(res.metadata or {}),
                    "rbac": {
                        "checked": True,
                        "required_permission": spec.required_permission,
                        "permitted": True,
                    },
                }
        log_counter("chat_command_invoked", labels={"command": cmd})
        with contextlib.suppress(_COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS):
            increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "success"})
        return _finalize_result(res)
    except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Error executing /{cmd}: {e}", exc_info=True)
        log_counter("chat_command_error", labels={"command": cmd, "reason": "exception"})
        try:
            increment_counter("chat_command_errors_total", labels={"command": cmd, "reason": "exception"})
            increment_counter("chat_command_invoked_total", labels={"command": cmd, "status": "error"})
        except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
            pass
        return _finalize_result(
            CommandResult(
                ok=False,
                command=cmd,
                content=f"Command /{cmd} failed: {e}",
                metadata={"error": "exception"},
            )
        )


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
            except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS:
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
    except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS as e:
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
    except _COMMAND_ROUTER_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"Weather provider error: {e}", exc_info=True)
        return CommandResult(ok=False, command="weather", content=f"Weather unavailable: {e}", metadata={"error": "exception"})


# Register built-in commands on import
register_command(
    "time",
    "Show the current time (optional TZ).",
    _time_handler,
    required_permission="chat.commands.time",
    usage="/time [timezone]",
    args=["timezone"],
    requires_api_key=True,
    rbac_required=True,
)
register_command(
    "weather",
    "Show current weather for a location.",
    _weather_handler,
    required_permission="chat.commands.weather",
    usage="/weather [location]",
    args=["location"],
    requires_api_key=True,
    rbac_required=True,
)

# --- Test seam helpers ---
def get_weather_client(ctx: CommandContext | None = None):
    """Thin wrapper to allow tests to monkeypatch the weather client at the router level.

    Tests expect to patch command_router.get_weather_client; delegate to the
    actual provider factory so production code continues to use the unified
    weather providers module.
    """
    return weather_providers.get_weather_client()
