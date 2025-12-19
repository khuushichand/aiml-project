from __future__ import annotations

from typing import Optional
import ipaddress

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.settings import Settings, get_settings


def is_single_user_ip_allowed(ip: Optional[str], settings: Optional[Settings] = None) -> bool:
    """Return True when the client IP is allowed for single-user API key auth."""
    s = settings or get_settings()
    allowed_raw = getattr(s, "SINGLE_USER_ALLOWED_IPS", None) or []
    allowed = [str(entry).strip() for entry in allowed_raw if str(entry).strip()]
    if not allowed:
        return True
    if not ip:
        return False
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError as exc:
        logger.debug(f"Single-user IP allowlist: invalid client IP '{ip}': {exc}")
        return False

    for entry in allowed:
        try:
            if "/" in entry:
                if ip_obj in ipaddress.ip_network(entry, strict=False):
                    return True
            else:
                if str(ip_obj) == entry:
                    return True
        except ValueError as exc:
            logger.debug(f"Single-user IP allowlist: invalid entry '{entry}': {exc}")
            continue
    return False


__all__ = ["is_single_user_ip_allowed"]
