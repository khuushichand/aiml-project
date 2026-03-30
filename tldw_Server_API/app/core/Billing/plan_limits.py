"""Neutral OSS/self-host limit definitions.

The public repository only exposes a free/self-host default tier. Commercial
plan naming and fallback pricing are intentionally excluded from OSS.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class PlanTier(str, Enum):
    """Available OSS tier names."""
    FREE = "free"


VALID_PLAN_NAMES = [PlanTier.FREE.value]


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


# Default limits for the OSS/self-host tier.
DEFAULT_LIMITS: dict[PlanTier, PlanLimits] = {
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
}


def get_plan_limits(plan_name: str) -> dict[str, Any]:
    """
    Get OSS/self-host limits.

    Args:
        plan_name: Retained for compatibility. Commercial plan names are ignored.

    Returns:
        Dict of neutral OSS/self-host limit values.
    """
    _ = plan_name
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
) -> dict[str, Any]:
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
