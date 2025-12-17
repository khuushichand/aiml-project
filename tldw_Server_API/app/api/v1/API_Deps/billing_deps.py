"""
billing_deps.py

FastAPI dependencies for billing and limit enforcement.
Provides guards that check subscription limits before allowing operations.
"""
from __future__ import annotations

from typing import Callable, Dict, Any, Optional

from fastapi import Depends, Header, HTTPException, Request, Response, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo
from tldw_Server_API.app.core.Resource_Governance import cost_units
from tldw_Server_API.app.core.Billing.enforcement import (
    BillingEnforcer,
    LimitCategory,
    LimitCheckResult,
    EnforcementAction,
    get_billing_enforcer,
    enforcement_enabled,
)


# Warning header name for soft limit notifications
BILLING_WARNING_HEADER = "X-Billing-Warning"
BILLING_LIMIT_HEADER = "X-Billing-Limit"
BILLING_USAGE_HEADER = "X-Billing-Usage"


async def _resolve_org_id(
    principal: AuthPrincipal,
    x_tldw_org_id: Optional[int] = None,
) -> Optional[int]:
    """
    Resolve the organization ID for billing purposes.

    Priority:
    1. X-TLDW-Org-Id header
    2. First org in user's membership list
    3. None (user has no orgs)
    """
    if x_tldw_org_id is not None:
        return x_tldw_org_id

    try:
        pool = await get_db_pool()
        repo = AuthnzOrgsTeamsRepo(db_pool=pool)
        memberships = await repo.list_org_memberships_for_user(principal.user_id)

        if memberships:
            return memberships[0].get("org_id")
    except Exception as exc:
        logger.debug(f"Failed to resolve org_id for user {principal.user_id}: {exc}")

    return None


def require_within_limit(category: LimitCategory, units: int = 1):
    """
    Dependency factory that enforces a billing limit.

    Blocks requests that would exceed the organization's limit.
    Adds warning headers when approaching limits.

    Args:
        category: The limit category to check
        units: Number of units this operation will consume

    Usage:
        @router.post("/chat")
        async def chat(
            _: LimitCheckResult = Depends(require_within_limit(LimitCategory.LLM_TOKENS_MONTH, 1000))
        ):
            ...
    """
    async def _check_limit(
        request: Request,
        response: Response,
        principal: AuthPrincipal = Depends(get_auth_principal),
        x_tldw_org_id: Optional[int] = Header(None, alias="X-TLDW-Org-Id"),
    ) -> LimitCheckResult:
        # Skip enforcement if disabled
        if not enforcement_enabled():
            return LimitCheckResult(
                category=category.value,
                action=EnforcementAction.ALLOW,
                current=0,
                limit=-1,
                percent_used=0,
                unlimited=True,
            )

        # Resolve org_id
        org_id = await _resolve_org_id(principal, x_tldw_org_id)

        if org_id is None:
            # No org - use permissive defaults (single-user mode)
            return LimitCheckResult(
                category=category.value,
                action=EnforcementAction.ALLOW,
                current=0,
                limit=-1,
                percent_used=0,
                unlimited=True,
            )

        # Check the limit
        enforcer = get_billing_enforcer()
        result = await enforcer.check_limit(org_id, category, requested_units=units)

        # Add headers
        response.headers[BILLING_LIMIT_HEADER] = str(result.limit) if not result.unlimited else "unlimited"
        response.headers[BILLING_USAGE_HEADER] = str(result.current)

        if result.should_warn and result.message:
            response.headers[BILLING_WARNING_HEADER] = result.message

        # Block if limit exceeded
        if result.should_block:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED
                if result.action == EnforcementAction.SOFT_BLOCK
                else status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "limit_exceeded",
                    "category": category.value,
                    "current": result.current,
                    "limit": result.limit,
                    "message": result.message or f"Limit exceeded for {category.value}",
                    "upgrade_url": "/billing/plans",  # Frontend can use this
                },
                headers={
                    "Retry-After": str(result.retry_after) if result.retry_after else "3600",
                },
            )

        return result

    return _check_limit


def require_feature(feature: str):
    """
    Dependency factory that checks feature access.

    Blocks requests if the organization doesn't have access to the feature.

    Args:
        feature: Feature name (e.g., "advanced_analytics", "sso_enabled")

    Usage:
        @router.get("/analytics")
        async def get_analytics(
            _: bool = Depends(require_feature("advanced_analytics"))
        ):
            ...
    """
    async def _check_feature(
        principal: AuthPrincipal = Depends(get_auth_principal),
        x_tldw_org_id: Optional[int] = Header(None, alias="X-TLDW-Org-Id"),
    ) -> bool:
        # Skip enforcement if disabled
        if not enforcement_enabled():
            return True

        # Resolve org_id
        org_id = await _resolve_org_id(principal, x_tldw_org_id)

        if org_id is None:
            # No org - assume feature is available (single-user mode)
            return True

        # Check feature access
        enforcer = get_billing_enforcer()
        has_access = await enforcer.check_feature_access(org_id, feature)

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "feature_not_available",
                    "feature": feature,
                    "message": f"Your subscription plan does not include {feature.replace('_', ' ')}",
                    "upgrade_url": "/billing/plans",
                },
            )

        return True

    return _check_feature


async def get_org_limits(
    principal: AuthPrincipal = Depends(get_auth_principal),
    x_tldw_org_id: Optional[int] = Header(None, alias="X-TLDW-Org-Id"),
) -> Dict[str, Any]:
    """
    Dependency that returns the current org's subscription limits.

    Use this when you need to access limits for informational purposes
    without enforcing them.
    """
    org_id = await _resolve_org_id(principal, x_tldw_org_id)

    if org_id is None:
        # Return permissive defaults
        return {
            "api_calls_day": -1,
            "llm_tokens_month": -1,
            "storage_gb": -1,
            "team_members": -1,
            "unlimited": True,
        }

    enforcer = get_billing_enforcer()
    return await enforcer.get_org_limits(org_id)


async def add_billing_headers(
    response: Response,
    principal: AuthPrincipal = Depends(get_auth_principal),
    x_tldw_org_id: Optional[int] = Header(None, alias="X-TLDW-Org-Id"),
) -> None:
    """
    Dependency that adds billing info headers to the response.

    Useful for endpoints that don't enforce limits but want to inform
    clients about their usage.
    """
    if not enforcement_enabled():
        return

    org_id = await _resolve_org_id(principal, x_tldw_org_id)
    if org_id is None:
        return

    try:
        enforcer = get_billing_enforcer()
        limits = await enforcer.get_org_limits(org_id)
        usage = await enforcer.get_org_usage(org_id)

        # Add summary headers
        response.headers["X-Billing-Plan-Api-Limit"] = str(limits.get("api_calls_day", "unlimited"))
        response.headers["X-Billing-Api-Usage-Today"] = str(usage.api_calls_today)

    except Exception as exc:
        logger.debug(f"Failed to add billing headers: {exc}")


class LimitEnforcer:
    """
    Context manager for limit enforcement with automatic recording.

    Usage:
        async with LimitEnforcer(org_id, LimitCategory.LLM_TOKENS_MONTH, estimated=1000) as enforcer:
            # Do the operation
            actual_tokens = await call_llm(...)
            enforcer.record_actual(actual_tokens)
    """

    def __init__(
        self,
        org_id: int,
        category: LimitCategory,
        estimated_units: int = 1,
    ):
        self.org_id = org_id
        self.category = category
        self.estimated_units = estimated_units
        self.actual_units: Optional[int] = None
        self._enforcer = get_billing_enforcer()
        self._check_result: Optional[LimitCheckResult] = None

    async def __aenter__(self) -> "LimitEnforcer":
        """Check limit on entry."""
        if enforcement_enabled():
            self._check_result = await self._enforcer.check_limit(
                self.org_id,
                self.category,
                requested_units=self.estimated_units,
            )

            if self._check_result.should_block:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "limit_exceeded",
                        "category": self.category.value,
                        "message": self._check_result.message,
                    },
                )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Record actual usage on exit (if operation succeeded)."""
        if exc_type is None and self.actual_units is not None and enforcement_enabled():
            try:
                units = int(self.actual_units)
            except Exception:
                units = 0

            if units > 0:
                # Best-effort in-memory cache delta for billing checks
                try:
                    self._enforcer.apply_usage_delta(self.org_id, self.category, units)
                except Exception as exc:
                    logger.debug(f"LimitEnforcer: apply_usage_delta failed for org_id={self.org_id}: {exc}")

                # Mirror usage into the generic cost-units ledger so that
                # cross-category budgets can reason about org-level usage.
                try:
                    tokens = 0
                    minutes = 0.0
                    requests = 0

                    if self.category == LimitCategory.LLM_TOKENS_MONTH:
                        tokens = units
                    elif self.category in (LimitCategory.API_CALLS_DAY, LimitCategory.RAG_QUERIES_DAY):
                        requests = units
                    elif self.category == LimitCategory.TRANSCRIPTION_MINUTES_MONTH:
                        minutes = float(units)

                    if tokens or minutes or requests:
                        await cost_units.record_cost_units_for_entity(
                            entity_scope="org",
                            entity_value=str(self.org_id),
                            tokens=tokens,
                            minutes=minutes,
                            requests=requests,
                        )
                except Exception as exc:
                    logger.debug(f"LimitEnforcer: cost-units ledger write failed for org_id={self.org_id}: {exc}")

        # Invalidate cache so next request gets fresh data
        if self.actual_units is not None:
            self._enforcer.invalidate_cache(self.org_id)

    def record_actual(self, units: int) -> None:
        """Record the actual units consumed by the operation."""
        self.actual_units = units

    @property
    def check_result(self) -> Optional[LimitCheckResult]:
        """Get the limit check result."""
        return self._check_result
