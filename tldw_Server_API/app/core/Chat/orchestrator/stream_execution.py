"""Stream execution helpers for chat orchestration."""

from __future__ import annotations

import contextlib
import inspect
from typing import Any


def _close_sync_stream(stream_response: Any) -> None:
    close_fn = getattr(stream_response, "close", None)
    if callable(close_fn):
        with contextlib.suppress(Exception):
            close_fn()


async def _close_async_stream(stream_response: Any) -> None:
    aclose_fn = getattr(stream_response, "aclose", None)
    if callable(aclose_fn):
        with contextlib.suppress(Exception):
            result = aclose_fn()
            if inspect.isawaitable(result):
                await result
        return
    _close_sync_stream(stream_response)


def execute_stream(stream_response: Any) -> Any:
    """Return a wrapped stream preserving provider chunk order and shape."""
    if hasattr(stream_response, "__iter__") and not isinstance(
        stream_response, (str, bytes, dict)
    ):
        def _sync_iter() -> Any:
            try:
                for chunk in stream_response:
                    yield chunk
            finally:
                _close_sync_stream(stream_response)

        return _sync_iter()

    if hasattr(stream_response, "__aiter__"):
        async def _async_iter() -> Any:
            try:
                async for chunk in stream_response:
                    yield chunk
            finally:
                await _close_async_stream(stream_response)

        return _async_iter()

    return stream_response
