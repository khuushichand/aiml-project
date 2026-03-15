"""Chat loop helpers used to gate legacy tool auto-execution paths."""

from __future__ import annotations

from typing import Any


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "y", "on", "enabled", "enable"}:
            return True
        if token in {"0", "false", "no", "n", "off", "disabled", "disable", "legacy"}:
            return False
    return False


def is_chat_loop_mode_enabled(cleaned_args: dict[str, Any] | None) -> bool:
    """Return True when the request opts into server chat loop mode."""
    if not isinstance(cleaned_args, dict):
        return False
    return _coerce_bool(cleaned_args.get("chat_loop_mode"))
