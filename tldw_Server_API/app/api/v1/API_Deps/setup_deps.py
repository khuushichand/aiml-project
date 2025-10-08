"""Dependencies for protecting setup endpoints.

By default we restrict mutating setup actions to local requests only (loopback).
Set the environment variable ``TLDW_SETUP_ALLOW_REMOTE=1`` to disable this guard
for special scenarios (e.g., when accessing the setup UI through a reverse proxy
on a trusted network). In tests, Starlette's TestClient reports host as
``testclient``; this value is treated as local unless an ``X-Forwarded-For``
header is provided.
"""

from __future__ import annotations

import os
from fastapi import HTTPException, Request, status
from loguru import logger


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _first_forwarded_ip(request: Request) -> str | None:
    """Return the left-most IP from X-Forwarded-For if present.

    We read at most the first token to avoid trusting a chain of proxies. If the
    header is missing or malformed, returns None.
    """
    raw = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
    if not raw:
        return None
    # header can be comma-separated list of IPs
    try:
        first = raw.split(",", 1)[0].strip()
        return first or None
    except Exception:  # noqa: BLE001
        return None


def _is_local_host(host: str | None, forwarded_ip: str | None) -> bool:
    # If a forwarded IP is present, prefer it for locality decisions.
    if forwarded_ip:
        return forwarded_ip in LOCAL_HOSTS
    if not host:
        return False
    return host in LOCAL_HOSTS


async def require_local_setup_access(request: Request) -> None:
    """Guard mutating setup operations so they can only be called locally.

    Bypass when ``TLDW_SETUP_ALLOW_REMOTE`` is set to a truthy value.
    """
    allow_remote = os.getenv("TLDW_SETUP_ALLOW_REMOTE", "").strip().lower() in {"1", "true", "yes", "on", "y"}
    if allow_remote:
        return

    forwarded = _first_forwarded_ip(request)
    host = request.client.host if request.client else None
    if _is_local_host(host, forwarded):
        return

    logger.warning(
        "Blocked remote setup access from host=%s forwarded=%s", host, forwarded,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Setup changes are restricted to local requests. Set TLDW_SETUP_ALLOW_REMOTE=1 "
            "to permit remote access temporarily."
        ),
    )

