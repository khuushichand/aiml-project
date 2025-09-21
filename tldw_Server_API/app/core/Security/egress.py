from __future__ import annotations

import os
import socket
import ipaddress
from typing import Iterable


PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _resolve_host_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
        addrs = []
        for _, _, _, _, sockaddr in infos:
            ip = sockaddr[0]
            addrs.append(ip)
        return list(dict.fromkeys(addrs))
    except Exception:
        return []


def is_private_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in PRIVATE_RANGES)
    except Exception:
        return True


def is_url_allowed(url: str) -> bool:
    """Check egress policy for a URL using env allowlist and private IP blocks."""
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        if p.scheme not in {"http", "https"}:
            return False
        host = p.hostname or ""
        # domain allowlist
        raw = os.getenv("WORKFLOWS_EGRESS_ALLOWLIST", "").strip()
        allow = [h.strip().lower() for h in raw.split(",") if h.strip()]
        if allow and not any(host.endswith(a) for a in allow):
            return False
        # block private IPs if enabled
        if os.getenv("WORKFLOWS_EGRESS_BLOCK_PRIVATE", "true").lower() in {"1", "true", "yes"}:
            ips = _resolve_host_ips(host)
            if not ips:
                # if we cannot resolve, be conservative only if allowlist is set
                return not allow
            for ip in ips:
                if is_private_ip(ip):
                    return False
        return True
    except Exception:
        return False

