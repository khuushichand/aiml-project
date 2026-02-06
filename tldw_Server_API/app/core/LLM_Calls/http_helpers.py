"""Helpers to construct a sync session facade with retries for legacy streaming paths.

This module avoids importing chat_calls to prevent recursion. It uses the
centralized http_client underneath while preserving a minimal Session-like API.
"""

import contextlib
import time
from collections.abc import Iterable
from typing import Any, Optional

from tldw_Server_API.app.core.http_client import (
    RetryPolicy as _HC_RetryPolicy,
)
from tldw_Server_API.app.core.http_client import (
    create_client as _hc_create_client,
)
from tldw_Server_API.app.core.http_client import (
    fetch as _hc_fetch,
)
from tldw_Server_API.app.core.LLM_Calls.error_utils import is_network_error


class _StreamResponse:
    def __init__(self, response: Any, ctx: Any) -> None:
        self._response = response
        self._ctx = ctx
        self._closed = False
        self.status_code = getattr(response, "status_code", None)
        self.headers = getattr(response, "headers", None)

    @property
    def text(self) -> str:
        return getattr(self._response, "text", "")

    def json(self) -> Any:
        return self._response.json()

    def raise_for_status(self) -> None:
        self._response.raise_for_status()

    def iter_lines(self, *args, **kwargs):
        return self._response.iter_lines(*args, **kwargs)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._response.close()
        finally:
            with contextlib.suppress(Exception):
                self._ctx.__exit__(None, None, None)


class _RetrySession:
    def __init__(
        self,
        *,
        total: int = 3,
        backoff_factor: float = 1.0,
        status_forcelist: Optional[Iterable[int]] = None,
        allowed_methods: Optional[Iterable[str]] = None,
    ) -> None:
        methods = tuple(m.upper() for m in (allowed_methods or ["POST"]))
        retry_on_status = tuple(status_forcelist or (429, 500, 502, 503, 504))
        backoff_ms = max(0, int(float(backoff_factor) * 1000))
        self._retry = _HC_RetryPolicy(
            attempts=max(1, int(total)),
            backoff_base_ms=backoff_ms,
            retry_on_status=retry_on_status,
            retry_on_methods=methods,
            retry_on_unsafe=any(m not in {"GET", "HEAD", "OPTIONS"} for m in methods),
        )
        self._client = None

    def _get_client(self) -> Any:
        if self._client is None:
            self._client = _hc_create_client()
        return self._client

    def post(self, url, *, headers=None, json=None, stream: bool = False, timeout=None, **kwargs):
        if not stream:
            return _hc_fetch(
                method="POST",
                url=url,
                headers=headers,
                json=json,
                timeout=timeout,
                retry=self._retry,
                client=self._get_client(),
            )

        attempts = max(1, int(self._retry.attempts))
        for attempt in range(attempts):
            ctx = None
            resp = None
            try:
                client = self._get_client()
                ctx = client.stream("POST", url, headers=headers, json=json, timeout=timeout)
                resp = ctx.__enter__()
                # Retry on status codes before returning the stream
                if resp.status_code in self._retry.retry_on_status and attempt + 1 < attempts:
                    resp.close()
                    ctx.__exit__(None, None, None)
                    time.sleep(float(self._retry.backoff_base_ms) / 1000.0)
                    continue
                return _StreamResponse(resp, ctx)
            except Exception as exc:
                if resp is not None:
                    with contextlib.suppress(Exception):
                        resp.close()
                if ctx is not None:
                    with contextlib.suppress(Exception):
                        ctx.__exit__(None, None, None)
                if attempt + 1 >= attempts or not is_network_error(exc):
                    raise
                time.sleep(float(self._retry.backoff_base_ms) / 1000.0)
        raise RuntimeError("Streaming request exhausted retry attempts")

    def close(self) -> None:
        try:
            if self._client is not None:
                self._client.close()
        except Exception:
            pass


def create_session_with_retries(
    total: int = 3,
    backoff_factor: float = 1.0,
    status_forcelist: Optional[Iterable[int]] = None,
    allowed_methods: Optional[Iterable[str]] = None,
):
    return _RetrySession(
        total=total,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
    )
