"""Stream execution helpers for chat orchestration."""

from __future__ import annotations

from typing import Any


def execute_stream(stream_response: Any) -> Any:
    """Return a wrapped stream preserving provider chunk order and shape."""
    if hasattr(stream_response, "__iter__") and not isinstance(
        stream_response, (str, bytes, dict)
    ):
        def _sync_iter() -> Any:
            for chunk in stream_response:
                yield chunk

        return _sync_iter()

    if hasattr(stream_response, "__aiter__"):
        async def _async_iter() -> Any:
            async for chunk in stream_response:
                yield chunk

        return _async_iter()

    return stream_response
