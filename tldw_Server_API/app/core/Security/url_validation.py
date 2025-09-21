import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException, status

PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),    # loopback
    ipaddress.ip_network("10.0.0.0/8"),     # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),  # RFC1918
    ipaddress.ip_network("192.168.0.0/16"), # RFC1918
    ipaddress.ip_network("169.254.0.0/16"), # link-local
    ipaddress.ip_network("::1/128"),        # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),       # unique local
    ipaddress.ip_network("fe80::/10"),      # link-local unicast
]

ALLOWED_SCHEMES = {"http", "https"}


def _resolve_host_ips(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
        ips = []
        for info in infos:
            addr = info[4][0]
            ips.append(addr)
        return list(set(ips))
    except Exception:
        return []


def _ip_is_private(ip_str: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        for net in PRIVATE_NETWORKS:
            if ip_obj in net:
                return True
        return False
    except ValueError:
        return True  # treat invalid IPs as unsafe


def assert_url_safe(url: str) -> None:
    """Validate that the given URL is safe for outbound requests (SSRF guard).

    - Scheme must be http or https
    - Host must not resolve to private, loopback, or link-local IPs
    - Reject empty/relative/opaque URLs
    """
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL")

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported URL scheme")

    if not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL must include a hostname")

    host = parsed.hostname or ""
    ips = _resolve_host_ips(host)
    if not ips:
        # If cannot resolve, treat as invalid
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Host could not be resolved")

    for ip in ips:
        if _ip_is_private(ip):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL resolves to a private address")

