from __future__ import annotations

import ipaddress
import os
from typing import Any

from fastapi import Request

from tldw_Server_API.app.core.config import load_comprehensive_config
from tldw_Server_API.app.core.Security.setup_access_guard import setup_remote_access_enabled

_ADMIN_NETWORK_NONCRITICAL_EXCEPTIONS = (
    AttributeError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def parse_nets(raw: str | None) -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    if not raw:
        return nets
    for token in [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]:
        try:
            if "/" in token:
                nets.append(ipaddress.ip_network(token, strict=False))
            else:
                ip = ipaddress.ip_address(token)
                nets.append(ipaddress.ip_network(ip.exploded + ("/32" if ip.version == 4 else "/128"), strict=False))
        except ValueError:
            # Skip invalid entries
            pass
    return nets


def load_list(section: str, field: str, env_name: str) -> list[ipaddress._BaseNetwork]:
    raw_env = os.getenv(env_name)
    if raw_env:
        return parse_nets(raw_env)
    try:
        cp = load_comprehensive_config()
        if cp and cp.has_section(section):
            raw_cfg = cp.get(section, field, fallback="").strip()
            if raw_cfg:
                return parse_nets(raw_cfg)
    except _ADMIN_NETWORK_NONCRITICAL_EXCEPTIONS:
        pass
    return []


def resolve_client_ip(request: Request, trusted_proxies: list[ipaddress._BaseNetwork]) -> tuple[str | None, bool]:
    def _is_trusted(ip: ipaddress._BaseAddress | None) -> bool:
        return bool(ip and any(ip in net for net in trusted_proxies))

    peer = request.client.host if request.client else None
    try:
        peer_ip_obj = ipaddress.ip_address(peer) if peer else None
    except ValueError:
        peer_ip_obj = None

    if _is_trusted(peer_ip_obj):
        xr = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
        if xr:
            try:
                ipaddress.ip_address(xr.strip())
                return xr.strip(), True
            except ValueError:
                pass
        fwd = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        if fwd:
            try:
                leftmost = fwd.split(",")[0].strip()
                ipaddress.ip_address(leftmost)
                return leftmost, True
            except ValueError:
                pass
    return peer, False


def is_loopback(ip_str: str | None) -> bool:
    if not ip_str:
        return False
    if ip_str in {"testclient", "localhost"}:
        return True
    try:
        return ipaddress.ip_address(ip_str).is_loopback
    except ValueError:
        return False


def build_network_info(request: Request) -> dict[str, Any]:
    trusted_proxies = load_list("Server", "trusted_proxies", "TLDW_TRUSTED_PROXIES")
    setup_allow = load_list("Setup", "setup_ip_allowlist", "TLDW_SETUP_ALLOWLIST")
    setup_deny = load_list("Setup", "setup_ip_denylist", "TLDW_SETUP_DENYLIST")

    resolved_ip, via_proxy = resolve_client_ip(request, trusted_proxies)
    loopback = is_loopback(resolved_ip)
    try:
        ip_obj = ipaddress.ip_address(resolved_ip) if resolved_ip else None
    except ValueError:
        ip_obj = None

    def _decide_setup() -> dict[str, str]:
        if loopback:
            return {"decision": "allow", "reason": "loopback"}
        toggle = setup_remote_access_enabled()
        if setup_deny and ip_obj and any(ip_obj in net for net in setup_deny):
            return {"decision": "deny", "reason": "denylist"}
        if setup_allow:
            if ip_obj and any(ip_obj in net for net in setup_allow):
                return {"decision": "allow", "reason": "allowlist"}
            return {"decision": "allow" if toggle else "deny", "reason": "toggle" if toggle else "no-allowlist-match"}
        return {"decision": "allow" if toggle else "deny", "reason": "toggle" if toggle else "toggle-off"}

    return {
        "peer_ip": request.client.host if request.client else None,
        "resolved_client_ip": resolved_ip,
        "via_trusted_proxy": via_proxy,
        "headers": {
            "x_forwarded_for": request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For"),
            "x_real_ip": request.headers.get("x-real-ip") or request.headers.get("X-Real-IP"),
        },
        "is_loopback": loopback,
        "setup": {
            "remote_toggle": setup_remote_access_enabled(),
            "allowlist": [str(n) for n in setup_allow],
            "denylist": [str(n) for n in setup_deny],
            **_decide_setup(),
        },
    }
