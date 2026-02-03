"""
datetime_utils.py
------------------

Shared datetime and timed-effects helpers for API v1.

These utilities are intentionally lightweight and avoid FastAPI/router
dependencies so they can be imported from endpoints and, where useful,
from core services without creating circular imports.
"""

from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from tldw_Server_API.app.api.v1.schemas.chat_dictionary_schemas import TimedEffects


def coerce_datetime(value: Any) -> _dt.datetime:
    """
    Best-effort conversion of common timestamp representations to a timezone-aware datetime.

    Accepts:
    - datetime instances (returned as-is)
    - strings in a few common formats and ISO-8601
    Falls back to `datetime.now(timezone.utc)` when parsing fails.
    """
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                return _dt.datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            return _dt.datetime.fromisoformat(value)
        except Exception:
            pass
    return _dt.datetime.now(_dt.timezone.utc)


def parse_timed_effects(value: Any) -> TimedEffects | None:
    """
    Normalize various representations into a TimedEffects instance.

    Accepts:
    - None → None
    - TimedEffects → returned as-is
    - dict → TimedEffects(**dict) when possible
    - JSON string containing a dict payload
    """
    if value is None:
        return None
    if isinstance(value, TimedEffects):
        return value
    if isinstance(value, dict):
        try:
            return TimedEffects(**value)
        except Exception:
            return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return TimedEffects(**parsed)
        except Exception:
            return None
    return None
