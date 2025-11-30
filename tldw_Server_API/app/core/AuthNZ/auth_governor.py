"""
auth_governor.py

AuthNZ-scoped governance facade built on existing virtual key budget logic.

This module provides a minimal `AuthGovernor` interface focused on LLM budgets
for virtual API keys. It decorates the existing `is_key_over_budget` result
with principal metadata and is intended as a compatibility layer while the
full ResourceGovernor integration is rolled out.
"""

from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.rate_limiter import get_rate_limiter
from tldw_Server_API.app.core.AuthNZ.virtual_keys import is_key_over_budget


class AuthGovernor:
    """
    Minimal AuthNZ governance facade.

    For v1, this class focuses on LLM virtual-key budgets by delegating to the
    existing `is_key_over_budget` helper and attaching `AuthPrincipal` metadata
    to the returned structure. Future iterations may route through the shared
    `ResourceGovernor` and maintain additional metrics.
    """

    async def check_llm_budget_for_api_key(
        self,
        principal: AuthPrincipal,
        api_key_id: int,
    ) -> Dict[str, Any]:
        """
        Check LLM budget state for a given API key and principal.

        Returns the existing `is_key_over_budget` result, augmented with a
        `principal` field that includes a stable, non-PII identifier and
        selected identity metadata for observability.
        """
        try:
            result = await is_key_over_budget(api_key_id)
        except Exception as exc:
            logger.error(f"AuthGovernor: error during is_key_over_budget for key {api_key_id}: {exc}")
            # Fail open for budget checks if underlying inspection fails; callers
            # can choose to enforce stricter behavior later if desired.
            return {
                "over": False,
                "reasons": [],
                "day": {},
                "month": {},
                "limits": {},
                "principal": {
                    "principal_id": principal.principal_id,
                    "kind": principal.kind,
                    "user_id": principal.user_id,
                    "api_key_id": principal.api_key_id,
                    "org_ids": principal.org_ids,
                    "team_ids": principal.team_ids,
                },
            }

        out: Dict[str, Any] = dict(result or {})
        limits = out.get("limits") or {}
        out["limits"] = limits
        out["principal"] = {
            "principal_id": principal.principal_id,
            "kind": principal.kind,
            "user_id": principal.user_id,
            "api_key_id": principal.api_key_id,
            "org_ids": principal.org_ids,
            "team_ids": principal.team_ids,
        }
        return out

    async def check_lockout(
        self,
        identifier: str,
        *,
        attempt_type: str = "login",
        rate_limiter=None,
    ):
        """
        Check lockout status for an identifier using the existing rate limiter.

        Returns a tuple of (is_locked, lockout_expires) when the rate limiter
        is available; otherwise fails open with (False, None).
        """
        limiter = rate_limiter
        if limiter is None:
            try:
                limiter = await get_rate_limiter()
            except Exception:
                limiter = None

        if limiter and getattr(limiter, "enabled", False):
            try:
                return await limiter.check_lockout(identifier)
            except Exception as exc:
                logger.debug(f"AuthGovernor lockout check failed for {identifier}: {exc}")
        return False, None

    async def record_auth_failure(
        self,
        identifier: str,
        *,
        attempt_type: str = "login",
        rate_limiter=None,
    ) -> Dict[str, Any]:
        """
        Record an authentication failure via the existing rate limiter.

        Returns the limiter result structure or a permissive default when
        the limiter is unavailable.
        """
        limiter = rate_limiter
        if limiter is None:
            try:
                limiter = await get_rate_limiter()
            except Exception:
                limiter = None

        if limiter and getattr(limiter, "enabled", False):
            try:
                return await limiter.record_failed_attempt(identifier=identifier, attempt_type=attempt_type)
            except Exception as exc:
                logger.debug(f"AuthGovernor record failure failed for {identifier}: {exc}")

        return {"is_locked": False, "remaining_attempts": 5}


_AUTH_GOVERNOR_SINGLETON: AuthGovernor | None = None


async def get_auth_governor() -> AuthGovernor:
    """
    Lightweight accessor for a process-local AuthGovernor instance.

    This avoids wiring a heavier dependency system while keeping the interface
    ready for more advanced backends (e.g., Redis-backed ResourceGovernor)
    in future iterations.
    """
    global _AUTH_GOVERNOR_SINGLETON
    if _AUTH_GOVERNOR_SINGLETON is None:
        _AUTH_GOVERNOR_SINGLETON = AuthGovernor()
    return _AUTH_GOVERNOR_SINGLETON
