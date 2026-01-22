from __future__ import annotations

from typing import Optional, Iterable, Any
import ipaddress

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings


def _normalize_entries(raw: Iterable[Any]) -> list[str]:
    return [str(entry).strip() for entry in raw if str(entry).strip()]


def _ip_in_allowlist(ip: Optional[str], allowlist: list[str]) -> bool:
    """Return True when IP matches any entry in allowlist (CIDR or exact)."""
    if not ip:
        return False
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError as exc:
        logger.debug(f"IP allowlist: invalid client IP '{ip}': {exc}")
        return False
    for entry in allowlist:
        token = entry.strip()
        if not token:
            continue
        try:
            if "/" in token:
                if ip_obj in ipaddress.ip_network(token, strict=False):
                    return True
            else:
                if ip_obj == ipaddress.ip_address(token):
                    return True
        except ValueError as exc:
            logger.debug(f"IP allowlist: invalid entry '{token}': {exc}")
            continue
    return False


def is_trusted_proxy_ip(ip: Optional[str], settings: Optional[Settings] = None) -> bool:
    """Return True when IP is in the trusted proxy allowlist."""
    s = settings or get_settings()
    raw = getattr(s, "AUTH_TRUSTED_PROXY_IPS", None) or []
    allowlist = _normalize_entries(raw)
    if not allowlist:
        return False
    return _ip_in_allowlist(ip, allowlist)


def resolve_client_ip(request: Any, settings: Optional[Settings] = None) -> Optional[str]:
    """Resolve client IP, honoring proxy headers only for trusted proxies."""
    if request is None:
        return None
    s = settings or get_settings()
    try:
        peer = getattr(getattr(request, "client", None), "host", None)
    except Exception:
        peer = None

    trust_xff = bool(getattr(s, "AUTH_TRUST_X_FORWARDED_FOR", False))
    if trust_xff and is_trusted_proxy_ip(peer, s):
        try:
            xr = request.headers.get("x-real-ip") or request.headers.get("X-Real-IP")
        except Exception:
            xr = None
        if xr:
            xr_val = xr.strip()
            try:
                ipaddress.ip_address(xr_val)
                return xr_val
            except ValueError:
                pass
        try:
            fwd = request.headers.get("x-forwarded-for") or request.headers.get("X-Forwarded-For")
        except Exception:
            fwd = None
        if fwd:
            try:
                leftmost = fwd.split(",", 1)[0].strip()
            except Exception:
                leftmost = ""
            if leftmost:
                try:
                    ipaddress.ip_address(leftmost)
                    return leftmost
                except ValueError:
                    pass
    return peer


def is_single_user_ip_allowed(ip: Optional[str], settings: Optional[Settings] = None) -> bool:
    """Return True when the client IP is allowed for single-user API key auth."""
    s = settings or get_settings()
    allowed_raw = getattr(s, "SINGLE_USER_ALLOWED_IPS", None) or []
    allowed = _normalize_entries(allowed_raw)
    if not allowed:
        return True
    return _ip_in_allowlist(ip, allowed)


def is_service_token_ip_allowed(ip: Optional[str], settings: Optional[Settings] = None) -> bool:
    """Return True when the client IP is allowed for service token auth."""
    s = settings or get_settings()
    allowed_raw = getattr(s, "SERVICE_TOKEN_ALLOWED_IPS", None) or []
    allowed = _normalize_entries(allowed_raw)
    if not ip:
        return False

    # If allowlist provided, require match.
    if allowed:
        return _ip_in_allowlist(ip, allowed)

    # Default: loopback only when no allowlist configured.
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError as exc:
        logger.debug(f"Service token IP allowlist: invalid client IP '{ip}': {exc}")
        return False
    return bool(getattr(ip_obj, "is_loopback", False))


__all__ = [
    "is_single_user_ip_allowed",
    "is_service_token_ip_allowed",
    "is_trusted_proxy_ip",
    "resolve_client_ip",
]
