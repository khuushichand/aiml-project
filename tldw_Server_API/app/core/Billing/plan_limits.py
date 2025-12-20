"""
plan_limits.py

Plan tier definitions and default limits.
These are used as fallbacks when database plans are not configured.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class PlanTier(str, Enum):
    """Available subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


VALID_PLAN_NAMES = [tier.value for tier in PlanTier if tier != PlanTier.FREE]


@dataclass(frozen=True)
class PlanLimits:
    """Limit definitions for a plan tier."""
    storage_mb: int
    api_calls_day: int
    llm_tokens_month: int
    team_members: int
    transcription_minutes_month: int
    rag_queries_day: int
    concurrent_jobs: int
    # Feature flags
    advanced_analytics: bool = False
    priority_support: bool = False
    custom_models: bool = False
    api_access: bool = True
    sso_enabled: bool = False
    audit_logs: bool = False


# Default limits for each tier
DEFAULT_LIMITS: Dict[PlanTier, PlanLimits] = {
    PlanTier.FREE: PlanLimits(
        storage_mb=1024,
        api_calls_day=100,
        llm_tokens_month=300_000,
        team_members=1,
        transcription_minutes_month=60,
        rag_queries_day=50,
        concurrent_jobs=1,
        advanced_analytics=False,
        priority_support=False,
        custom_models=False,
        api_access=True,
        sso_enabled=False,
        audit_logs=False,
    ),
    PlanTier.PRO: PlanLimits(
        storage_mb=10240,
        api_calls_day=5_000,
        llm_tokens_month=15_000_000,
        team_members=5,
        transcription_minutes_month=600,
        rag_queries_day=500,
        concurrent_jobs=5,
        advanced_analytics=True,
        priority_support=False,
        custom_models=True,
        api_access=True,
        sso_enabled=False,
        audit_logs=True,
    ),
    PlanTier.ENTERPRISE: PlanLimits(
        storage_mb=102400,
        api_calls_day=50_000,
        llm_tokens_month=150_000_000,
        team_members=-1,  # -1 means unlimited
        transcription_minutes_month=6000,
        rag_queries_day=5000,
        concurrent_jobs=20,
        advanced_analytics=True,
        priority_support=True,
        custom_models=True,
        api_access=True,
        sso_enabled=True,
        audit_logs=True,
    ),
}


def get_plan_limits(plan_name: str) -> Dict[str, Any]:
    """
    Get limits for a plan by name.

    Args:
        plan_name: Plan name (free, pro, enterprise)

    Returns:
        Dict of limit values
    """
    try:
        tier = PlanTier(plan_name.lower())
        limits = DEFAULT_LIMITS.get(tier, DEFAULT_LIMITS[PlanTier.FREE])
    except ValueError:
        limits = DEFAULT_LIMITS[PlanTier.FREE]

    return {
        "storage_mb": limits.storage_mb,
        "api_calls_day": limits.api_calls_day,
        "llm_tokens_month": limits.llm_tokens_month,
        "team_members": limits.team_members,
        "transcription_minutes_month": limits.transcription_minutes_month,
        "rag_queries_day": limits.rag_queries_day,
        "concurrent_jobs": limits.concurrent_jobs,
        "advanced_analytics": limits.advanced_analytics,
        "priority_support": limits.priority_support,
        "custom_models": limits.custom_models,
        "api_access": limits.api_access,
        "sso_enabled": limits.sso_enabled,
        "audit_logs": limits.audit_logs,
    }


def limits_to_json(limits: PlanLimits) -> str:
    """Convert PlanLimits to JSON string for storage."""
    import json
    return json.dumps({
        "storage_mb": limits.storage_mb,
        "api_calls_day": limits.api_calls_day,
        "llm_tokens_month": limits.llm_tokens_month,
        "team_members": limits.team_members,
        "transcription_minutes_month": limits.transcription_minutes_month,
        "rag_queries_day": limits.rag_queries_day,
        "concurrent_jobs": limits.concurrent_jobs,
        "advanced_analytics": limits.advanced_analytics,
        "priority_support": limits.priority_support,
        "custom_models": limits.custom_models,
        "api_access": limits.api_access,
        "sso_enabled": limits.sso_enabled,
        "audit_logs": limits.audit_logs,
    })


# Soft limit threshold (percentage of hard limit at which warnings are issued)
SOFT_LIMIT_PERCENT = 80

# Grace period for payment failures (days)
PAYMENT_GRACE_PERIOD_DAYS = 3


def check_limit(
    current_value: int,
    limit_value: int,
    limit_name: str,
) -> Dict[str, Any]:
    """
    Check a usage value against its limit.

    Args:
        current_value: Current usage
        limit_value: Maximum allowed (-1 for unlimited)
        limit_name: Name of the limit for messaging

    Returns:
        Dict with status, warning, and details
    """
    if limit_value == -1:
        # Unlimited
        return {
            "limit_name": limit_name,
            "current": current_value,
            "limit": None,
            "unlimited": True,
            "exceeded": False,
            "warning": False,
            "percent_used": 0,
        }

    percent_used = (current_value / limit_value * 100) if limit_value > 0 else 100
    exceeded = current_value >= limit_value
    warning = not exceeded and percent_used >= SOFT_LIMIT_PERCENT

    return {
        "limit_name": limit_name,
        "current": current_value,
        "limit": limit_value,
        "unlimited": False,
        "exceeded": exceeded,
        "warning": warning,
        "percent_used": round(percent_used, 1),
    }
