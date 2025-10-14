"""Dependencies for protecting setup endpoints.

By default we restrict mutating setup actions to local requests only (loopback).
Set the environment variable ``TLDW_SETUP_ALLOW_REMOTE=1`` to disable this guard
for special scenarios (e.g., when accessing the setup UI through a reverse proxy
on a trusted network). In tests, Starlette's TestClient reports host as
``testclient``; this value is treated as local unless an ``X-Forwarded-For``
header is provided.
"""

from __future__ import annotations

import ipaddress
import os
import time
from configparser import ConfigParser
from typing import Optional

from fastapi import HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.core.Setup import setup_manager


LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
# Treat these as local hostnames for the Host header check.
# Include IPv6 localhost as well.
LOCAL_HOST_HEADERS = {"localhost", "127.0.0.1", "::1", "testserver"}
_FALSEY_ENV_VALUES = {"0", "false", "no", "off", "n"}

_CONFIG_REMOTE_CACHE_TTL = 30.0  # seconds
_config_remote_cached: Optional[bool] = None
_config_remote_cached_at = 0.0


def reset_remote_access_cache(value: Optional[bool] = None) -> None:
    """Reset the cached remote access flag (test helper/administrative hook)."""
    _set_remote_access_cache(value)


def _set_remote_access_cache(value: Optional[bool]) -> None:
    global _config_remote_cached, _config_remote_cached_at
    if value is None:
        _config_remote_cached = None
        _config_remote_cached_at = 0.0
    else:
        _config_remote_cached = value
        _config_remote_cached_at = time.monotonic()


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


def _is_loopback_host(host: str | None) -> bool:
    """Return True if the provided hostname/IP represents a local loopback address."""
    if not host:
        return False

    value = host.strip().lower()
    if not value:
        return False

    if value in LOCAL_HOSTS:
        return True

    # Strip IPv6 scope identifiers before parsing
    candidate = value.split("%", 1)[0]
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


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
    allow_remote_env = os.getenv("TLDW_SETUP_ALLOW_REMOTE", "").strip().lower() in {"1", "true", "yes", "on", "y"}
    allow_remote_config = _config_allows_remote()
    if allow_remote_env or allow_remote_config:
        if allow_remote_config and not allow_remote_env:
            logger.info("Remote setup access permitted via config.txt (allow_remote_setup_access=true)")
        return

    path = (request.url.path or "").lower()
    method = (request.method or "").upper()

    has_proxy_headers = _has_proxy_headers(request)
    client_host = request.client.host if request.client else None
    forwarded_ip = _first_forwarded_ip(request)
    client_is_local = _is_loopback_host(client_host)
    forwarded_is_local = _is_loopback_host(forwarded_ip)
    host_header_is_local = _host_header_is_local(request)

    # Permit GET to setup config snapshot only if effectively local.
    # If proxy headers are present, require both the proxy connection and forwarded IP to be loopback.
    if method == "GET" and path.endswith("/api/v1/setup/config"):
        if not host_header_is_local:
            logger.warning("Blocked GET to setup config due to non-local Host header: %s", request.headers.get("host"))
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Setup access is restricted to local requests. Host header must target localhost.",
            )
        if not has_proxy_headers and client_is_local:
            return
        if has_proxy_headers and client_is_local and forwarded_is_local:
            logger.debug("Allowing proxied localhost GET to /api/v1/setup/config with loopback client and forwarded IP")
            return
        logger.warning(
            "Blocked proxied GET to setup config from client=%s forwarded=%s (local=%s/%s)",
            client_host,
            forwarded_ip,
            client_is_local,
            forwarded_is_local,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Setup access is restricted to local requests. Forwarded client is not local. "
                "Set TLDW_SETUP_ALLOW_REMOTE=1 or enable allow_remote_setup_access in config.txt to bypass."
            ),
        )

    if has_proxy_headers:
        if not (client_is_local and forwarded_is_local and host_header_is_local):
            logger.warning(
                "Blocked setup access via proxy (client=%s, forwarded=%s, host_local=%s)",
                client_host,
                forwarded_ip,
                host_header_is_local,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Setup changes are restricted to local requests. Forwarded client is not local. "
                    "Set TLDW_SETUP_ALLOW_REMOTE=1 or enable allow_remote_setup_access in config.txt to bypass."
                ),
            )
        return

    if client_is_local and host_header_is_local:
        return

    logger.warning("Blocked remote setup access from host=%s", client_host)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Setup changes are restricted to local requests. Set TLDW_SETUP_ALLOW_REMOTE=1 "
            "or enable allow_remote_setup_access in config.txt to permit remote access temporarily."
        ),
    )


def _config_allows_remote() -> bool:
    """Return True when config.txt enables remote setup access."""
    global _config_remote_cached, _config_remote_cached_at

    now = time.monotonic()
    if (
        _config_remote_cached is not None
        and (now - _config_remote_cached_at) < _CONFIG_REMOTE_CACHE_TTL
    ):
        return _config_remote_cached

    allow_remote = False
    try:
        config_path = setup_manager.get_config_file_path()
        parser = ConfigParser()
        parser.read(config_path, encoding="utf-8")
        allow_remote = parser.getboolean("Setup", "allow_remote_setup_access", fallback=False)
    except Exception:
        logger.debug("Unable to read allow_remote_setup_access from config.txt", exc_info=True)

    _set_remote_access_cache(allow_remote)
    return allow_remote


def _on_remote_access_updated(enabled: bool) -> None:
    """Callback fired when config.txt flips remote access."""
    _set_remote_access_cache(enabled)
    if enabled:
        logger.warning(
            "Setup remote access enabled via config.txt; remote clients are now permitted to call setup APIs."
        )
    else:
        logger.info("Setup remote access disabled via config.txt; setup APIs restricted to localhost.")


setup_manager.register_remote_access_hook(_on_remote_access_updated)
