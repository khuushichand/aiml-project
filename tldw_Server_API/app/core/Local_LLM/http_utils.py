"""HTTP utilities for Local_LLM handlers.

Provides a shared httpx AsyncClient factory, simple retry helpers,
readiness polling, and command redaction for safer logging.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Iterable, Tuple

import httpx


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
    """Create a configured httpx AsyncClient with sane defaults."""
    return httpx.AsyncClient(timeout=timeout or DEFAULT_TIMEOUT)


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
    """Perform an HTTP request with simple retries and return parsed JSON.

    Retries on network errors and 5xx status codes.
    """
    attempt = 0
    while True:
        try:
            resp = await client.request(method.upper(), url, json=json, headers=headers)
            if 500 <= resp.status_code < 600 and attempt < retries:
                attempt += 1
                await asyncio.sleep(backoff * attempt)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            status = getattr(e.response, "status_code", None)
            if status and status >= 500 and attempt < retries:
                attempt += 1
                await asyncio.sleep(backoff * attempt)
                continue
            raise
        except httpx.RequestError:
            if attempt < retries:
                attempt += 1
                await asyncio.sleep(backoff * attempt)
                continue
            raise


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
                    resp = await client.get(url)
                    if resp.status_code < 500:
                        return True
                except httpx.RequestError:
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
    """Download a file via streaming with basic retry/backoff.

    Overwrites existing file at `dest_path` on success. Removes partial
    file if an error occurs.
    """
    attempt = 0
    while True:
        try:
            async with create_async_client(timeout=300.0) as client:
                async with client.stream("GET", url, follow_redirects=True) as resp:
                    resp.raise_for_status()
                    tmp_path = dest_path + ".part"
                    with open(tmp_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size):
                            if chunk:
                                f.write(chunk)
                    # Move temp to final name
                    import os
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    os.replace(tmp_path, dest_path)
                    return
        except (httpx.HTTPError, Exception):
            # Cleanup partial
            import os
            try:
                os.remove(dest_path + ".part")
            except Exception:
                pass
            if attempt < retries:
                attempt += 1
                await asyncio.sleep(backoff * attempt)
                continue
            raise
