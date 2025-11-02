"""Schema compatibility helpers for Pydantic v1/v2.

Currently provides a Field wrapper that transparently maps
Field(example=...) to json_schema_extra={"example": ...} on Pydantic v2
to avoid deprecation warnings, while remaining a no-op on v1.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field as _PydField

try:  # Detect Pydantic v2 APIs
    from pydantic import model_validator as _mv  # type: ignore
    _IS_PYDANTIC_V2 = True
    del _mv
except Exception:  # pragma: no cover - conservative fallback
    _IS_PYDANTIC_V2 = False


def Field(*args: Any, **kwargs: Any):  # type: ignore
    """Compatibility Field that supports example -> json_schema_extra on v2.

    - On Pydantic v2: if an ``example=...`` kwarg is provided, it is moved into
      ``json_schema_extra={"example": ...}`` while preserving any existing
      extras.
    - On Pydantic v1: passes through unchanged.
    """
    if _IS_PYDANTIC_V2 and "example" in kwargs:
        ex = kwargs.pop("example")
        extra = kwargs.get("json_schema_extra")
        # Ensure a dict for extras; preserve existing extras when provided
        if not isinstance(extra, dict) or extra is None:
            extra = {} if extra is None else {"value": extra}
        extra.setdefault("example", ex)
        kwargs["json_schema_extra"] = extra
    return _PydField(*args, **kwargs)


__all__ = ["Field"]
