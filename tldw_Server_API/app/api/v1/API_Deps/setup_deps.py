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
    """Return True if the request originates from a local address.

    When proxy trust is enabled and a forwarded IP is present, prefer the
    forwarded IP for locality checks; otherwise fall back to the client host.
    """
    # Prefer forwarded IP when available and trusted
    if forwarded_ip:
        return forwarded_ip in LOCAL_HOSTS
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

    Special-case: Allow GET /api/v1/setup/config when the request targets
    localhost (by Host header or client IP), even if proxy headers are present.
    This keeps the Setup UI functional behind common local reverse proxies,
    while keeping POST/PUT restricted.
    """
    allow_remote = os.getenv("TLDW_SETUP_ALLOW_REMOTE", "").strip().lower() in {"1", "true", "yes", "on", "y"}
    if allow_remote:
        return

    path = (request.url.path or "").lower()
    method = (request.method or "").upper()

    # Localhost and proxy header helpers
    client_host = request.client.host if request.client else None
    forwarded_ip = _first_forwarded_ip(request)
    host_header_is_local = _host_header_is_local(request)
    client_is_local = _is_local_host(client_host, forwarded_ip)

    # Permit GET to setup config snapshot only if effectively local.
    # If proxy headers are present, require forwarded IP to be local.
    if method == "GET" and path.endswith("/api/v1/setup/config"):
        if host_header_is_local or client_is_local:
            if _has_proxy_headers(request):
                if forwarded_ip and _is_local_host(client_host, forwarded_ip):
                    logger.debug("Allowing proxied localhost GET to /api/v1/setup/config with local forwarded IP")
                    return
                # Proxied but remote forwarded IP -> block
                logger.warning("Blocked proxied GET to setup config from remote forwarded IP: %s", forwarded_ip)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Setup access is restricted to local requests. Forwarded client is not local."
                    ),
                )
            # No proxy headers, treat as local GET
            return

    # For all other guarded endpoints, if behind a proxy and the forwarded IP
    # is not local, block. If forwarded IP is local, allow as local.
    if _has_proxy_headers(request):
        if forwarded_ip is None:
            # Proxy headers present but not trusted or malformed; block by default
            logger.warning("Blocked setup access due to untrusted/missing forwarded IP under proxy")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Setup changes are restricted to local requests. Set TLDW_SETUP_TRUST_PROXY=1 to honor "
                    "X-Forwarded-For and TLDW_SETUP_ALLOW_REMOTE=1 to permit remote access temporarily."
                ),
            )
        if not _is_local_host(client_host, forwarded_ip):
            logger.warning("Blocked setup access from proxied remote IP: %s", forwarded_ip)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Setup changes are restricted to local requests. Forwarded client is not local."
                ),
            )

    # Require both client host to be local and Host header to target local
    if client_is_local and host_header_is_local:
        return

    logger.warning("Blocked remote setup access from host=%s", client_host)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Setup changes are restricted to local requests. Set TLDW_SETUP_ALLOW_REMOTE=1 "
            "to permit remote access temporarily."
        ),
    )
