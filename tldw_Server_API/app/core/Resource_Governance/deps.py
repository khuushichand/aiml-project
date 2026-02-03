from __future__ import annotations

"""
Helpers and FastAPI dependencies for deriving Resource Governor entity keys.

Preference order:
  1) Auth scopes (request.state.user_id → user:{id})
  2) API key scope (request.state.api_key_id → api_key:{id})
  3) API key header (X-API-KEY → api_key:{hmac})
  4) Authorization: Bearer ... (treated as api_key hash if present)
  5) IP scope (trusted header via RG_CLIENT_IP_HEADER else request.client.host)
"""

import ipaddress
import os

from fastapi import Request

from .tenant import hash_entity


def _parse_trusted_proxies(env_val: str | None) -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    if not env_val:
        return nets
    for part in env_val.split(","):
        s = part.strip()
        if not s:
            continue
        try:
            # Accept both single IPs and CIDRs
            if "/" in s:
                nets.append(ipaddress.ip_network(s, strict=False))
            else:
                # Represent single host as /32 or /128 network
                ip_obj = ipaddress.ip_address(s)
                mask = 32 if ip_obj.version == 4 else 128
                nets.append(ipaddress.ip_network(f"{s}/{mask}", strict=False))
        except Exception:
            continue
    return nets


def _is_trusted_proxy(remote_ip: str, trusted: list[ipaddress._BaseNetwork]) -> bool:
    try:
        if not remote_ip or not trusted:
            return False
        ip_obj = ipaddress.ip_address(remote_ip)
        return any(ip_obj in n for n in trusted)
    except Exception:
        return False


def derive_client_ip(request: Request) -> str:
    """Derive client IP with trusted proxy handling.

    - Trust header specified by RG_CLIENT_IP_HEADER (e.g., X-Forwarded-For) only when
      the immediate peer (request.client.host) is within RG_TRUSTED_PROXIES (CIDR/IP list).
    - Otherwise, fall back to request.client.host.
    """
    # Immediate peer address
    remote_ip = None
    try:
        client = request.client
        if client and client.host:
            remote_ip = client.host
    except Exception:
        remote_ip = None
    # Normalize non-IP placeholders used by Starlette TestClient
    # Many tests see client.host == 'testclient'; treat as loopback
    try:
        import ipaddress as _ip
        if not remote_ip:
            remote_ip = None
        else:
            try:
                _ip.ip_address(remote_ip)
            except Exception:
                # Not a valid IP literal → assume loopback for local tests
                remote_ip = "127.0.0.1"
    except Exception:
        # best-effort
        pass

    trusted = _parse_trusted_proxies(os.getenv("RG_TRUSTED_PROXIES"))
    header_name = os.getenv("RG_CLIENT_IP_HEADER")

    # Use header only when the remote peer is trusted
    if header_name and _is_trusted_proxy(remote_ip or "", trusted):
        val = request.headers.get(header_name) or request.headers.get(header_name.lower())
        if val:
            # For X-Forwarded-For, choose left-most IP
            candidate = str(val).split(",")[0].strip()
            try:
                ipaddress.ip_address(candidate)
                if candidate:
                    return candidate
            except Exception:
                pass

    # Fallback: use direct peer address
    if remote_ip:
        return remote_ip
    return "unknown"


def derive_entity_key(request: Request) -> str:
    # Prefer authenticated user scope
    try:
        uid = getattr(request.state, "user_id", None)
        if isinstance(uid, int) or (isinstance(uid, str) and uid):
            return f"user:{uid}"
    except Exception:
        pass

    # Prefer API key id scope when available
    try:
        kid = getattr(request.state, "api_key_id", None)
        if kid is not None:
            return f"api_key:{kid}"
    except Exception:
        pass

    # Header-based API key fallback (hashed)
    try:
        raw = request.headers.get("X-API-KEY")
        if raw:
            return f"api_key:{hash_entity(raw)}"
    except Exception:
        pass

    # Authorization bearer fallback (hashed as api_key)
    try:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[len("Bearer "):].strip()
            if token:
                return f"api_key:{hash_entity(token)}"
    except Exception:
        pass

    # IP fallback
    ip = derive_client_ip(request)
    return f"ip:{ip}"


async def get_entity_key(request: Request) -> str:
    """FastAPI dependency that returns an entity key for Resource Governor."""
    return derive_entity_key(request)
