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
# Treat these as local hostnames for the Host header check.
# Include IPv6 localhost as well.
LOCAL_HOST_HEADERS = {"localhost", "127.0.0.1", "::1", "testserver"}
_FALSEY_ENV_VALUES = {"0", "false", "no", "off", "n"}


def _should_trust_proxy() -> bool:
    """Decide whether to honor proxy headers for locality checks.

    We default to trusting local reverse proxies unless ops explicitly
    disable it by setting ``TLDW_SETUP_TRUST_PROXY`` to a false-like value
    (e.g. ``0`` or ``false``). This preserves the historical behaviour where
    ``X-Forwarded-For`` was always honored, preventing proxy bypasses by
    remote clients.
    """

    raw = os.getenv("TLDW_SETUP_TRUST_PROXY")
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSEY_ENV_VALUES


def _first_forwarded_ip(request: Request) -> str | None:
    """Return the left-most IP from X-Forwarded-For when proxy trust enabled."""

    if not _should_trust_proxy():
        return None
    raw = request.headers.get("x-forwarded-for")
    if not raw:
        return None
    try:
        # header can be comma-separated list of IPs; take the first hop
        first = raw.split(",", 1)[0].strip()
        return first or None
    except Exception:  # noqa: BLE001
        return None


def _is_local_host(host: str | None, forwarded_ip: str | None) -> bool:
    # We do not trust forwarded IPs unless explicitly allowed elsewhere.
    if not host:
        return False
    return host in LOCAL_HOSTS


def _has_proxy_headers(request: Request) -> bool:
    # Treat any of these headers as evidence of a proxy hop; block by default.
    proxy_headers = (
        "x-forwarded-for",
        "forwarded",
        "x-real-ip",
        "x-forwarded-host",
        "x-forwarded-proto",
    )
    headers = request.headers
    for key in proxy_headers:
        if key in headers or key.title() in headers:
            return True
    return False


def _host_header_is_local(request: Request) -> bool:
    """Return True if the Host header targets a local hostname.

    Handles IPv6 bracketed hosts (e.g., "[::1]:8000").
    """
    raw = request.headers.get("host") or request.headers.get("Host")
    if not raw:
        return False

    host = raw.strip()

    # IPv6 addresses in Host header are bracketed: [::1]:8000
    if host.startswith("["):
        end = host.find("]")
        if end == -1:
            return False
        hostname = host[1:end].strip().lower()
    else:
        # Strip port if present (hostname:port)
        hostname = host.split(":", 1)[0].strip().lower()

    return hostname in LOCAL_HOST_HEADERS


async def require_local_setup_access(request: Request) -> None:
    """Guard mutating setup operations so they can only be called locally.

    Bypass when ``TLDW_SETUP_ALLOW_REMOTE`` is set to a truthy value.
    """
    allow_remote = os.getenv("TLDW_SETUP_ALLOW_REMOTE", "").strip().lower() in {"1", "true", "yes", "on", "y"}
    if allow_remote:
        return

    # If we detect proxy-related headers, block by default to avoid local spoofing via reverse proxies.
    if _has_proxy_headers(request):
        logger.warning("Blocked setup access due to proxy headers present")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Setup changes are restricted to local requests (no proxies). Set TLDW_SETUP_ALLOW_REMOTE=1 "
                "to permit remote access temporarily."
            ),
        )

    # Require both client host to be local and Host header to target local
    host = request.client.host if request.client else None
    if _is_local_host(host, None) and _host_header_is_local(request):
        return

    logger.warning(
        "Blocked remote setup access from host=%s", host,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Setup changes are restricted to local requests. Set TLDW_SETUP_ALLOW_REMOTE=1 "
            "to permit remote access temporarily."
        ),
    )
