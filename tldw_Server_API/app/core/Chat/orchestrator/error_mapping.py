"""Error mapping helpers for chat stream execution."""

from __future__ import annotations


def map_stream_error(exc: Exception) -> dict[str, str]:
    """Normalize provider/stream exceptions into a stable error shape."""
    return {
        "code": "provider_error",
        "message": str(exc),
    }
