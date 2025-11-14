from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Optional
from loguru import logger


@dataclass(frozen=True)
class TenantScopeConfig:
    enabled: bool = False
    header: str = "X-TLDW-Tenant"
    jwt_claim: str = "tenant_id"


def get_tenant_id(
    headers: Mapping[str, str],
    claims: Optional[Mapping[str, Any]] = None,
    config: Optional[TenantScopeConfig] = None,
) -> Optional[str]:
    """
    Extract a tenant identifier from request headers or JWT claims.

    This helper performs simple extraction only; caller is responsible for
    trusting proxy headers and providing validated claims.
    """
    cfg = config or TenantScopeConfig()
    if not cfg.enabled:
        return None

    # Header takes precedence when present
    val = headers.get(cfg.header) or headers.get(cfg.header.lower())
    if val:
        s = str(val).strip()
        return s or None

    # Fallback to JWT claim when present
    if claims and cfg.jwt_claim in claims:
        v = claims.get(cfg.jwt_claim)
        if v is None:
            return None
        return str(v).strip() or None

    return None


_LOG_HASH_SECRET_WARNED = False


def hash_entity(value: str, secret: Optional[str] = None) -> str:
    """
    Produce a stable, non-reversible identifier for logging/metrics.

    HMAC-SHA256 with a server-side secret (env: TLDW_LOG_HASH_SECRET).
    When no secret is supplied, reads from env; if still missing, uses a
    process-unique fallback (less ideal for multi-process correlation).
    """
    global _LOG_HASH_SECRET_WARNED
    env_secret = os.getenv("TLDW_LOG_HASH_SECRET")
    enforce = str(os.getenv("TLDW_ENFORCE_LOG_HASH_SECRET") or "").strip().lower() in ("1", "true", "yes", "on")
    if not secret and not env_secret:
        if enforce:
            # In enforced mode, fail fast to avoid cross-process instability
            raise RuntimeError("TLDW_LOG_HASH_SECRET is required but not set (TLDW_ENFORCE_LOG_HASH_SECRET=1)")
        if not _LOG_HASH_SECRET_WARNED:
            try:
                logger.warning("hash_entity using process-local fallback; set TLDW_LOG_HASH_SECRET for stable hashing across processes")
            except Exception:
                pass
            _LOG_HASH_SECRET_WARNED = True
    key = (secret or env_secret or os.getpid().__repr__()).encode()
    return hmac.new(key, value.encode(), sha256).hexdigest()


def parse_tenant_config(data: Mapping[str, Any]) -> TenantScopeConfig:
    """
    Build a TenantScopeConfig from a dictionary, e.g., policy snapshot's `tenant` section.
    Unknown keys are ignored.
    """
    enabled = bool(data.get("enabled", False))
    header = str(data.get("header", TenantScopeConfig.header))
    claim = str(data.get("jwt_claim", TenantScopeConfig.jwt_claim))
    return TenantScopeConfig(enabled=enabled, header=header, jwt_claim=claim)
