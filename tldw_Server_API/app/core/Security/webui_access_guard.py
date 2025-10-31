from __future__ import annotations

import ipaddress
from typing import Callable, Optional

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

from tldw_Server_API.app.core.config import load_comprehensive_config
import os


def _env_true(name: str) -> bool:
    raw = os.getenv(name)
    if not raw:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def webui_remote_access_enabled() -> bool:
    """Return True if remote access to /webui is allowed via env or config.

    Checks (in order):
    - Env var TLDW_WEBUI_ALLOW_REMOTE
    - Env var WEBUI_ALLOW_REMOTE (legacy/alternate)
    - Config [Server] allow_remote_webui_access (bool)
    """
    if _env_true("TLDW_WEBUI_ALLOW_REMOTE") or _env_true("WEBUI_ALLOW_REMOTE"):
        return True
    try:
        cp = load_comprehensive_config()
        if cp and cp.has_section("Server"):
            return cp.getboolean("Server", "allow_remote_webui_access", fallback=False)
    except Exception:
        # If config cannot be read yet, default to False (local-only)
        pass
    return False


def _get_peer_ip(request: Request) -> Optional[str]:
    try:
        return request.client.host if request.client else None
    except Exception:
        return None


def _is_loopback(ip_str: Optional[str]) -> bool:
    if not ip_str:
        return False
    if ip_str in {"testclient", "localhost"}:
        return True
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return ip_obj.is_loopback
    except Exception:
        # Non-IP or parse failure; treat as remote
        return False


def setup_remote_access_enabled() -> bool:
    if _env_true("TLDW_SETUP_ALLOW_REMOTE"):
        return True
    try:
        cp = load_comprehensive_config()
        if cp and cp.has_section("Setup"):
            return cp.getboolean("Setup", "allow_remote_setup_access", fallback=False)
    except Exception:
        pass
        return False


class WebUIAccessGuardMiddleware(BaseHTTPMiddleware):
    """Blocks remote access to /webui unless explicitly allowed by config/env.

    Default: local-only. Enable remote access by setting either:
      - TLDW_WEBUI_ALLOW_REMOTE=1 (or WEBUI_ALLOW_REMOTE=1), or
      - [Server] allow_remote_webui_access=true in Config_Files/config.txt
    """

    def _parse_allowlist(self, raw: Optional[str]) -> list[ipaddress._BaseNetwork]:
        nets: list[ipaddress._BaseNetwork] = []
        if not raw:
            return nets
        for token in [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]:
            try:
                # Accept CIDR or single IP; for single IP, convert to /32 or /128
                if "/" in token:
                    nets.append(ipaddress.ip_network(token, strict=False))
                else:
                    ip = ipaddress.ip_address(token)
                    nets.append(ipaddress.ip_network(ip.exploded + ("/32" if ip.version == 4 else "/128"), strict=False))
            except Exception:
                logger.warning(f"Invalid allowlist entry ignored: {token}")
        return nets

    def _load_allowlist(self, section: str, field: str, env_name: str) -> list[ipaddress._BaseNetwork]:
        # ENV takes precedence
        raw_env = os.getenv(env_name)
        if raw_env:
            return self._parse_allowlist(raw_env)
        try:
            cp = load_comprehensive_config()
            if cp and cp.has_section(section):
                raw_cfg = cp.get(section, field, fallback="").strip()
                if raw_cfg:
                    return self._parse_allowlist(raw_cfg)
        except Exception:
            pass
        return []

    def _resolve_client_ip(self, request: Request, trusted_proxies: list[ipaddress._BaseNetwork]) -> Optional[str]:
        """Resolve client IP using X-Forwarded-For only when the peer is a trusted proxy.

        - If remote peer is in trusted_proxies and XFF present, use the first (leftmost) XFF IP.
        - Else, use the socket peer.
        - X-Real-IP is considered only when peer is trusted and header is present.
        """
        peer = _get_peer_ip(request)
        try:
            peer_ip_obj = ipaddress.ip_address(peer) if peer else None
        except Exception:
            peer_ip_obj = None
        def _is_trusted(ip: Optional[ipaddress._BaseAddress]) -> bool:
            return bool(ip and any(ip in net for net in trusted_proxies))

        if _is_trusted(peer_ip_obj):
            # Prefer X-Real-IP if present and valid; else leftmost XFF element
            xr = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
            if xr:
                try:
                    ipaddress.ip_address(xr.strip())
                    return xr.strip()
                except Exception:
                    pass
            fwd = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
            if fwd:
                try:
                    leftmost = fwd.split(",")[0].strip()
                    ipaddress.ip_address(leftmost)
                    return leftmost
                except Exception:
                    pass
        return peer

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path or ""
        if not (path.startswith("/webui") or path == "/setup"):
            return await call_next(request)

        # Build allow/deny lists and trusted proxies (environment or config)
        webui_allowlist = self._load_allowlist("Server", "webui_ip_allowlist", "TLDW_WEBUI_ALLOWLIST")
        setup_allowlist = self._load_allowlist("Setup", "setup_ip_allowlist", "TLDW_SETUP_ALLOWLIST")
        webui_denylist = self._load_allowlist("Server", "webui_ip_denylist", "TLDW_WEBUI_DENYLIST")
        setup_denylist = self._load_allowlist("Setup", "setup_ip_denylist", "TLDW_SETUP_DENYLIST")
        trusted_proxies = self._load_allowlist("Server", "trusted_proxies", "TLDW_TRUSTED_PROXIES")

        client_ip = self._resolve_client_ip(request, trusted_proxies)
        if _is_loopback(client_ip):
            return await call_next(request)

        # Convert client_ip to ip_address object for membership checks
        client_ip_obj: Optional[ipaddress._BaseAddress] = None
        try:
            client_ip_obj = ipaddress.ip_address(client_ip) if client_ip else None
        except Exception:
            client_ip_obj = None

        # Determine policy for this path
        if path == "/setup":
            # Denylist takes precedence (except loopback handled above)
            if setup_denylist and client_ip_obj and any(client_ip_obj in net for net in setup_denylist):
                which = "Setup"
                logger.warning(f"Blocked remote {which} (denylist) from {client_ip}")
                return PlainTextResponse("Access denied by IP denylist.", status_code=403)
            # If an allowlist is provided, treat it as enabling remote access for matching IPs
            if setup_allowlist and client_ip_obj and any(client_ip_obj in net for net in setup_allowlist):
                return await call_next(request)
            if setup_remote_access_enabled():
                return await call_next(request)
        else:  # /webui
            if webui_denylist and client_ip_obj and any(client_ip_obj in net for net in webui_denylist):
                which = "WebUI"
                logger.warning(f"Blocked remote {which} (denylist) from {client_ip}")
                return PlainTextResponse("Access denied by IP denylist.", status_code=403)
            if webui_allowlist and client_ip_obj and any(client_ip_obj in net for net in webui_allowlist):
                return await call_next(request)
            if webui_remote_access_enabled():
                return await call_next(request)

        which = "WebUI" if path.startswith("/webui") else "Setup"
        logger.warning(
            f"Blocked remote {which} access from {client_ip} (enable via config/env toggle)"
        )
        return PlainTextResponse(
            (
                "Remote WebUI access is disabled.\n\n"
                "To allow remote WebUI access, set TLDW_WEBUI_ALLOW_REMOTE=1 (or WEBUI_ALLOW_REMOTE=1)\n"
                "and run the server with a public host (e.g., uvicorn --host 0.0.0.0),\n"
                "or set [Server] allow_remote_webui_access=true in Config_Files/config.txt.\n\n"
                "Optionally, restrict by IP/CIDR allowlist:\n"
                "- Env:  TLDW_WEBUI_ALLOWLIST=192.168.1.0/24,10.0.0.5\n"
                "- Config: [Server] webui_ip_allowlist=192.168.1.0/24, 10.0.0.5\n\n"
                "For Setup (/setup), use TLDW_SETUP_ALLOW_REMOTE=1 or set\n"
                "[Setup] allow_remote_setup_access=true.\n"
                "Optionally, [Setup] setup_ip_allowlist or TLDW_SETUP_ALLOWLIST can restrict who can access /setup."
            ),
            status_code=403,
        )


__all__ = ["WebUIAccessGuardMiddleware", "webui_remote_access_enabled"]
