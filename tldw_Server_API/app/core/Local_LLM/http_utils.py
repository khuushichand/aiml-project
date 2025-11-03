"""HTTP utilities for Local_LLM handlers.

Provides a shared httpx AsyncClient factory, simple retry helpers,
readiness polling, and command redaction for safer logging.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Iterable, Tuple

import httpx
from loguru import logger

from tldw_Server_API.app.core.http_client import (
    create_async_client as _create_async_client,
    afetch_json,
    adownload,
    afetch,
    RetryPolicy,
)


DEFAULT_TIMEOUT: float = 120.0
DEFAULT_RETRIES: int = 2
DEFAULT_BACKOFF: float = 0.75


def redact_cmd_args(args: Iterable[str], sensitive_flags: Tuple[str, ...] = ("--api-key",)) -> list[str]:
    """Redact values for flags like --api-key in a command list.

    Example: ["llamafile", "--api-key", "secret", "-m", "model"] ->
             ["llamafile", "--api-key", "REDACTED", "-m", "model"]
    """
    redacted: list[str] = []
    itr = iter(args)
    for token in itr:
        redacted.append(token)
        if token in sensitive_flags:
            # Replace the next token with REDACTED if present
            try:
                _ = next(itr)
                redacted.append("REDACTED")
            except StopIteration:
                # Nothing to redact
                pass
    return redacted


def create_async_client(timeout: Optional[float] = None) -> httpx.AsyncClient:
    """Create a configured AsyncClient via central factory.

    Uses centralized defaults (trust_env=False, HTTP/2 if available).
    """
    to = httpx.Timeout(timeout or DEFAULT_TIMEOUT)
    return _create_async_client(timeout=to)


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json: Optional[dict] = None,
    headers: Optional[dict] = None,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
):
    """Perform an HTTP request and return parsed JSON via central helpers.

    Uses centralized egress enforcement, retries, and backoff.
    """
    # Backward-compat shim: if client is not an httpx.AsyncClient (e.g., tests provide a FakeClient),
    # fall back to the legacy minimal retry loop without extra kwargs.
    if not isinstance(client, httpx.AsyncClient):
        attempt = 0
        while True:
            try:
                resp = await client.request(method.upper(), url, json=json, headers=headers)
                if 500 <= resp.status_code < 600 and attempt < retries:
                    attempt += 1
                    await asyncio.sleep(backoff * (attempt or 1))
                    continue
                if resp.status_code >= 400:
                    raise httpx.HTTPStatusError("", request=resp.request, response=resp)
                return resp.json()
            except httpx.HTTPStatusError as e:
                status = getattr(e.response, "status_code", None)
                if status and status >= 500 and attempt < retries:
                    attempt += 1
                    await asyncio.sleep(backoff * (attempt or 1))
                    continue
                raise
            except httpx.RequestError:
                if attempt < retries:
                    attempt += 1
                    await asyncio.sleep(backoff * (attempt or 1))
                    continue
                raise

    # Map legacy semantics (attempts = 1 + retries) for real httpx clients
    attempts = max(1, int(retries)) + 1
    # Convert legacy backoff seconds to ms base with a reasonable cap
    backoff_ms = max(50, int(backoff * 1000))
    policy = RetryPolicy(attempts=attempts, backoff_base_ms=backoff_ms)
    return await afetch_json(
        method=method,
        url=url,
        client=client,
        headers=headers,
        json=json,
        retry=policy,
    )


async def wait_for_http_ready(
    base_url: str,
    *,
    paths: Tuple[str, ...] = ("/health", "/v1/models"),
    timeout_total: float = 30.0,
    interval: float = 0.5,
) -> bool:
    """Poll service until one of the candidate paths responds with a non-error status.

    Returns True if ready within timeout; otherwise False.
    """
    async with create_async_client(timeout=5.0) as client:
        deadline = asyncio.get_event_loop().time() + timeout_total
        while asyncio.get_event_loop().time() < deadline:
            for path in paths:
                url = base_url.rstrip("/") + "/" + path.lstrip("/")
                try:
                    resp = await afetch(method="GET", url=url, client=client)
                    if resp.status_code < 500:
                        return True
                except Exception:
                    # Not ready yet
                    pass
            await asyncio.sleep(interval)
    return False


async def wait_for_ollama_ready(base_url: str, timeout_total: float = 30.0, interval: float = 0.5) -> bool:
    """Poll Ollama until ready by checking common endpoints."""
    return await wait_for_http_ready(
        base_url,
        paths=("/api/version", "/api/tags"),
        timeout_total=timeout_total,
        interval=interval,
    )


async def async_stream_download(
    url: str,
    dest_path: str,
    *,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    chunk_size: int = 8192,
) -> None:
    """Download a file via centralized downloader with safety checks.

    Uses atomic rename and optional resume (disabled). On failure, partial
    files are removed by the downloader.
    """
    attempts = max(1, int(retries)) + 1
    backoff_ms = max(50, int(backoff * 1000))
    policy = RetryPolicy(attempts=attempts, backoff_base_ms=backoff_ms)
    try:
        await adownload(url=url, dest=dest_path, retry=policy)
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        raise
