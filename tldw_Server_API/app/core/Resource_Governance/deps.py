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

from typing import Optional
import os

from fastapi import Request

from .tenant import hash_entity


def derive_client_ip(request: Request) -> str:
    header = os.getenv("RG_CLIENT_IP_HEADER")
    if header:
        val = request.headers.get(header) or request.headers.get(header.lower())
        if val:
            ip = str(val).split(",")[0].strip()
            if ip:
                return ip
    try:
        client = request.client
        if client and client.host:
            return client.host
    except Exception:
        pass
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

