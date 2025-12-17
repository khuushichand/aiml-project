"""
enforcement.py

Billing limit enforcement that integrates with the Resource Governor system.
Provides dependencies for checking and enforcing subscription limits.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.Billing.plan_limits import (
    check_limit,
    SOFT_LIMIT_PERCENT,
)


class LimitCategory(str, Enum):
    """Categories of limits that can be enforced."""
    API_CALLS_DAY = "api_calls_day"
    LLM_TOKENS_MONTH = "llm_tokens_month"
    STORAGE_GB = "storage_gb"
    TEAM_MEMBERS = "team_members"
    TRANSCRIPTION_MINUTES_MONTH = "transcription_minutes_month"
    RAG_QUERIES_DAY = "rag_queries_day"
    CONCURRENT_JOBS = "concurrent_jobs"


class EnforcementAction(str, Enum):
    """Action to take when limit is approached/exceeded."""
    ALLOW = "allow"
    WARN = "warn"  # Allow but add warning header
    SOFT_BLOCK = "soft_block"  # Block with upgrade prompt
    HARD_BLOCK = "hard_block"  # Block completely


@dataclass
class LimitCheckResult:
    """Result of checking a limit."""
    category: str
    action: EnforcementAction
    current: int
    limit: int
    percent_used: float
    unlimited: bool = False
    message: Optional[str] = None
    retry_after: Optional[int] = None  # For rate limits

    @property
    def should_block(self) -> bool:
        return self.action in (EnforcementAction.SOFT_BLOCK, EnforcementAction.HARD_BLOCK)

    @property
    def should_warn(self) -> bool:
        return self.action == EnforcementAction.WARN


@dataclass
class UsageSummary:
    """Summary of current usage for an organization."""
    org_id: int
    api_calls_today: int = 0
    llm_tokens_month: int = 0
    storage_bytes: int = 0
    team_members: int = 0
    transcription_minutes_month: int = 0
    rag_queries_today: int = 0
    concurrent_jobs: int = 0


class BillingEnforcer:
    """
    Enforces billing limits by integrating with the subscription service
    and usage tracking systems.

    This class provides the bridge between:
    - Subscription limits (from billing service)
    - Current usage (from usage repos)
    - Enforcement decisions (allow/warn/block)
    """

    def __init__(
        self,
        *,
        soft_limit_percent: float = SOFT_LIMIT_PERCENT,
        grace_period_days: int = 3,
    ):
        self.soft_limit_percent = soft_limit_percent
        self.grace_period_days = grace_period_days
        self._usage_cache: Dict[int, Tuple[UsageSummary, float]] = {}
        self._limits_cache: Dict[int, Tuple[Dict[str, Any], float]] = {}
        self._cache_ttl = 60.0  # 1 minute cache

    async def get_org_limits(self, org_id: int) -> Dict[str, Any]:
        """Get subscription limits for an organization with caching."""
        import time
        now = time.time()

        # Check cache
        if org_id in self._limits_cache:
            cached, cached_at = self._limits_cache[org_id]
            if now - cached_at < self._cache_ttl:
                return cached

        # Fetch from service
        try:
            from tldw_Server_API.app.core.Billing.subscription_service import get_subscription_service
            service = await get_subscription_service()
            limits = await service.get_org_limits(org_id)
            self._limits_cache[org_id] = (limits, now)
            return limits
        except Exception as exc:
            logger.warning(f"Failed to get org limits for {org_id}: {exc}")
            # Return permissive defaults on failure
            return {
                "api_calls_day": 1000,
                "llm_tokens_month": 10_000_000,
                "storage_gb": 10,
                "team_members": -1,
                "transcription_minutes_month": 600,
                "rag_queries_day": 500,
                "concurrent_jobs": 5,
            }

    async def get_org_usage(self, org_id: int) -> UsageSummary:
        """
        Get current usage summary for an organization.

        Aggregates from various usage tracking sources.
        """
        import time
        now = time.time()

        # Check cache
        if org_id in self._usage_cache:
            cached, cached_at = self._usage_cache[org_id]
            if now - cached_at < self._cache_ttl:
                return cached

        summary = UsageSummary(org_id=org_id)

        try:
            # Get API call count for today
            summary.api_calls_today = await self._get_api_calls_today(org_id)

            # Get LLM token usage for this month
            summary.llm_tokens_month = await self._get_llm_tokens_month(org_id)

            # Get team member count
            summary.team_members = await self._get_team_member_count(org_id)

            # Get concurrent jobs
            summary.concurrent_jobs = await self._get_concurrent_jobs(org_id)

            # Cache the result
            self._usage_cache[org_id] = (summary, now)

        except Exception as exc:
            logger.warning(f"Failed to get org usage for {org_id}: {exc}")
            # Return zeros on failure (fail open)

        return summary

    async def _get_api_calls_today(self, org_id: int) -> int:
        """Get API call count for today from usage_daily table."""
        try:
            from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

            pool = await get_db_pool()
            today = datetime.now(timezone.utc).date().isoformat()

            async with pool.acquire() as conn:
                if hasattr(conn, "fetchval"):
                    # PostgreSQL
                    result = await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(request_count), 0)
                        FROM usage_daily
                        WHERE org_id = $1 AND day = $2
                        """,
                        org_id, today,
                    )
                else:
                    # SQLite
                    cur = await conn.execute(
                        """
                        SELECT COALESCE(SUM(request_count), 0)
                        FROM usage_daily
                        WHERE org_id = ? AND day = ?
                        """,
                        (org_id, today),
                    )
                    row = await cur.fetchone()
                    result = row[0] if row else 0

                return int(result or 0)
        except Exception as exc:
            logger.debug(f"Failed to get API calls for org {org_id}: {exc}")
            return 0

    async def _get_llm_tokens_month(self, org_id: int) -> int:
        """Get LLM token usage for current month."""
        try:
            from tldw_Server_API.app.core.AuthNZ.database import get_db_pool

            pool = await get_db_pool()
            now = datetime.now(timezone.utc)
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            async with pool.acquire() as conn:
                if hasattr(conn, "fetchval"):
                    # PostgreSQL
                    result = await conn.fetchval(
                        """
                        SELECT COALESCE(SUM(total_tokens), 0)
                        FROM llm_usage_log
                        WHERE org_id = $1 AND ts >= $2
                        """,
                        org_id, month_start,
                    )
                else:
                    # SQLite
                    cur = await conn.execute(
                        """
                        SELECT COALESCE(SUM(total_tokens), 0)
                        FROM llm_usage_log
                        WHERE org_id = ? AND ts >= ?
                        """,
                        (org_id, month_start.isoformat()),
                    )
                    row = await cur.fetchone()
                    result = row[0] if row else 0

                return int(result or 0)
        except Exception as exc:
            logger.debug(f"Failed to get LLM tokens for org {org_id}: {exc}")
            return 0

    async def _get_team_member_count(self, org_id: int) -> int:
        """Get current team member count for organization."""
        try:
            from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
            from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo

            pool = await get_db_pool()
            repo = AuthnzOrgsTeamsRepo(db_pool=pool)
            members = await repo.list_org_members(org_id=org_id, limit=1000)
            return len(members)
        except Exception as exc:
            logger.debug(f"Failed to get team members for org {org_id}: {exc}")
            return 0

    async def _get_concurrent_jobs(self, org_id: int) -> int:
        """Get count of currently running jobs for organization."""
        # This would integrate with a job tracking system
        # For now, return 0 (no jobs tracked)
        return 0

    async def check_limit(
        self,
        org_id: int,
        category: LimitCategory,
        *,
        requested_units: int = 1,
    ) -> LimitCheckResult:
        """
        Check if an operation is allowed given the org's limits.

        Args:
            org_id: Organization ID
            category: Limit category to check
            requested_units: Number of units the operation will consume

        Returns:
            LimitCheckResult with action to take
        """
        limits = await self.get_org_limits(org_id)
        usage = await self.get_org_usage(org_id)

        # Map category to current usage and limit
        usage_map = {
            LimitCategory.API_CALLS_DAY: usage.api_calls_today,
            LimitCategory.LLM_TOKENS_MONTH: usage.llm_tokens_month,
            LimitCategory.TEAM_MEMBERS: usage.team_members,
            LimitCategory.CONCURRENT_JOBS: usage.concurrent_jobs,
        }

        current = usage_map.get(category, 0)
        limit_value = limits.get(category.value, -1)

        # Unlimited (-1)
        if limit_value == -1:
            return LimitCheckResult(
                category=category.value,
                action=EnforcementAction.ALLOW,
                current=current,
                limit=limit_value,
                percent_used=0,
                unlimited=True,
            )

        # Calculate after operation
        after_operation = current + requested_units
        percent_used = (after_operation / limit_value * 100) if limit_value > 0 else 100

        # Determine action
        if after_operation > limit_value:
            # Would exceed limit
            return LimitCheckResult(
                category=category.value,
                action=EnforcementAction.SOFT_BLOCK,
                current=current,
                limit=limit_value,
                percent_used=percent_used,
                message=f"Limit exceeded for {category.value}. Current: {current}, Limit: {limit_value}",
            )
        elif percent_used >= self.soft_limit_percent:
            # Approaching limit - warn
            return LimitCheckResult(
                category=category.value,
                action=EnforcementAction.WARN,
                current=current,
                limit=limit_value,
                percent_used=percent_used,
                message=f"Approaching limit for {category.value}: {percent_used:.0f}% used",
            )
        else:
            # Well within limits
            return LimitCheckResult(
                category=category.value,
                action=EnforcementAction.ALLOW,
                current=current,
                limit=limit_value,
                percent_used=percent_used,
            )

    async def check_feature_access(
        self,
        org_id: int,
        feature: str,
    ) -> bool:
        """
        Check if an organization has access to a specific feature.

        Args:
            org_id: Organization ID
            feature: Feature name (e.g., "advanced_analytics", "sso_enabled")

        Returns:
            True if feature is enabled, False otherwise
        """
        limits = await self.get_org_limits(org_id)
        return bool(limits.get(feature, False))

    def invalidate_cache(self, org_id: Optional[int] = None) -> None:
        """Invalidate usage/limits cache for an org or all orgs."""
        if org_id is not None:
            self._usage_cache.pop(org_id, None)
            self._limits_cache.pop(org_id, None)
        else:
            self._usage_cache.clear()
            self._limits_cache.clear()


# Singleton instance
_billing_enforcer: Optional[BillingEnforcer] = None


def get_billing_enforcer() -> BillingEnforcer:
    """Get or create the billing enforcer singleton."""
    global _billing_enforcer
    if _billing_enforcer is None:
        _billing_enforcer = BillingEnforcer()
    return _billing_enforcer


# =============================================================================
# Resource Governor Integration
# =============================================================================

async def create_billing_rg_request(
    *,
    org_id: int,
    category: LimitCategory,
    units: int = 1,
    endpoint: Optional[str] = None,
) -> "RGRequest":
    """
    Create a Resource Governor request for billing enforcement.

    This allows billing limits to be enforced through the RG system.
    """
    try:
        from tldw_Server_API.app.core.Resource_Governance.governor import RGRequest
    except ImportError:
        raise RuntimeError("Resource Governor not available")

    return RGRequest(
        entity=f"org:{org_id}",
        categories={
            category.value: {"units": units},
        },
        tags={
            "org_id": str(org_id),
            "endpoint": endpoint or "unknown",
            "policy_id": f"billing.{category.value}",
        },
    )


async def check_billing_with_rg(
    org_id: int,
    category: LimitCategory,
    units: int = 1,
) -> bool:
    """
    Check billing limits using the Resource Governor if available.

    Falls back to direct enforcement if RG is not available.
    """
    try:
        from tldw_Server_API.app.core.Resource_Governance.governor import (
            ResourceGovernor,
            MemoryResourceGovernor,
        )

        # Try to get RG from app state (if we're in a request context)
        # Otherwise use a local instance
        enforcer = get_billing_enforcer()
        result = await enforcer.check_limit(org_id, category, requested_units=units)
        return not result.should_block

    except ImportError:
        # RG not available, use direct enforcement
        enforcer = get_billing_enforcer()
        result = await enforcer.check_limit(org_id, category, requested_units=units)
        return not result.should_block
    except Exception as exc:
        logger.warning(f"Billing RG check failed, allowing: {exc}")
        return True  # Fail open


# =============================================================================
# Utility Functions
# =============================================================================

def billing_enabled() -> bool:
    """Check if billing enforcement is enabled."""
    return os.environ.get("BILLING_ENABLED", "false").lower() == "true"


def enforcement_enabled() -> bool:
    """Check if limit enforcement is enabled (can be separate from billing)."""
    # Can have enforcement without Stripe billing (e.g., for usage caps)
    return os.environ.get("LIMIT_ENFORCEMENT_ENABLED", "true").lower() == "true"
