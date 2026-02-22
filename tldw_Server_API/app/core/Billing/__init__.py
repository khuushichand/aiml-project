"""
Billing module for subscription management and Stripe integration.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tldw_Server_API.app.core.Billing.enforcement import (
    BillingEnforcer,
    EnforcementAction,
    LimitCategory,
    LimitCheckResult,
    billing_enabled,
    enforcement_enabled,
    get_billing_enforcer,
)
from tldw_Server_API.app.core.Billing.plan_limits import (
    DEFAULT_LIMITS,
    PlanTier,
    get_plan_limits,
)

if TYPE_CHECKING:
    from tldw_Server_API.app.core.Billing.subscription_service import SubscriptionService

__all__ = [
    "BillingEnforcer",
    "DEFAULT_LIMITS",
    "EnforcementAction",
    "LimitCategory",
    "LimitCheckResult",
    "PlanTier",
    "SubscriptionService",
    "billing_enabled",
    "enforcement_enabled",
    "get_billing_enforcer",
    "get_plan_limits",
    "get_subscription_service",
]


def __getattr__(name: str) -> Any:
    """Lazily expose subscription service symbols to avoid import cycles."""
    if name in {"SubscriptionService", "get_subscription_service"}:
        from tldw_Server_API.app.core.Billing.subscription_service import (
            SubscriptionService,
            get_subscription_service,
        )
        exports = {
            "SubscriptionService": SubscriptionService,
            "get_subscription_service": get_subscription_service,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
