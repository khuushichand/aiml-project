"""
admin_billing.py

Admin endpoints for managing billing and subscriptions.
All endpoints require admin role (enforced by the parent admin router).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field

from tldw_Server_API.app.core.Billing.stripe_client import is_billing_enabled
from tldw_Server_API.app.services import admin_billing_service

router = APIRouter(prefix="/billing", tags=["admin-billing"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PlanOverrideRequest(BaseModel):
    """Request body for overriding a user's plan."""
    plan_id: str = Field(..., description="Plan name to assign (e.g. 'free', 'pro', 'enterprise')")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for the override")


class GrantCreditsRequest(BaseModel):
    """Request body for granting credits to a user."""
    amount: int = Field(..., gt=0, description="Number of credits to grant")
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for granting credits")
    expires_at: str | None = Field(None, description="Optional expiration date (ISO 8601)")


class SubscriptionItem(BaseModel):
    """Subscription summary for admin listing."""
    org_id: int
    plan_name: str | None = None
    plan_display_name: str | None = None
    status: str | None = None
    billing_cycle: str | None = None
    cancel_at_period_end: bool | None = None
    created_at: str | None = None


class SubscriptionListResponse(BaseModel):
    """Response for listing all subscriptions."""
    items: list[dict[str, Any]]
    total: int


class BillingOverviewResponse(BaseModel):
    """Response for billing overview."""
    billing_enabled: bool
    total_subscriptions: int
    active_subscriptions: int
    canceled_subscriptions: int
    past_due_subscriptions: int
    plan_distribution: dict[str, int]
    mrr_estimate_usd: float | int


class BillingEventsResponse(BaseModel):
    """Response for billing events."""
    items: list[dict[str, Any]]
    total: int


class GrantCreditsResponse(BaseModel):
    """Response for granting credits."""
    user_id: int
    credits_granted: int
    reason: str
    expires_at: str | None = None
    logged_at: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/overview",
    response_model=BillingOverviewResponse,
    summary="Get billing overview",
    description="Get billing overview: total MRR, active subs, churn rate.",
)
async def get_billing_overview():
    """Get billing overview statistics."""
    try:
        overview = await admin_billing_service.get_billing_overview()
        return BillingOverviewResponse(**overview)
    except Exception as exc:
        logger.error("Admin billing overview failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve billing overview",
        ) from exc


@router.get(
    "/subscriptions",
    response_model=SubscriptionListResponse,
    summary="List all subscriptions",
    description="List all user subscriptions with filtering.",
)
async def list_all_subscriptions(
    status_filter: str | None = Query(
        None,
        alias="status",
        description="Filter by status: active, canceled, past_due",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all user subscriptions with optional status filtering."""
    try:
        result = await admin_billing_service.list_all_subscriptions(
            status_filter=status_filter,
            limit=limit,
            offset=offset,
        )
        return SubscriptionListResponse(**result)
    except Exception as exc:
        logger.error("Admin list subscriptions failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list subscriptions",
        ) from exc


@router.get(
    "/subscriptions/{user_id}",
    summary="Get user subscription details",
    description="Get detailed subscription info for a specific user.",
)
async def get_user_subscription(user_id: int):
    """Get detailed subscription info for a specific user."""
    try:
        sub = await admin_billing_service.get_user_subscription_details(user_id)
        if sub is None:
            return {
                "org_id": user_id,
                "plan_name": "free",
                "status": "active",
                "detail": "No explicit subscription found; implicit free tier.",
            }
        return sub
    except Exception as exc:
        logger.error("Admin get user subscription failed for user_id={}: {}", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user subscription",
        ) from exc


@router.post(
    "/subscriptions/{user_id}/override",
    summary="Override user plan",
    description="Override a user's subscription plan (admin action).",
)
async def override_user_plan(
    user_id: int,
    payload: PlanOverrideRequest,
):
    """Override a user's subscription plan."""
    try:
        result = await admin_billing_service.override_user_plan(
            user_id,
            plan_id=payload.plan_id,
            reason=payload.reason,
        )
        return result
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Admin override plan failed for user_id={}: {}", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to override user plan",
        ) from exc


@router.post(
    "/subscriptions/{user_id}/credits",
    response_model=GrantCreditsResponse,
    summary="Grant credits to user",
    description="Grant usage credits to a user.",
)
async def grant_credits(
    user_id: int,
    payload: GrantCreditsRequest,
):
    """Grant usage credits to a user."""
    try:
        result = await admin_billing_service.grant_credits(
            user_id,
            amount=payload.amount,
            reason=payload.reason,
            expires_at=payload.expires_at,
        )
        return GrantCreditsResponse(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Admin grant credits failed for user_id={}: {}", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to grant credits",
        ) from exc


@router.get(
    "/events",
    response_model=BillingEventsResponse,
    summary="List billing events",
    description="List recent billing-related events.",
)
async def list_billing_events(
    limit: int = Query(50, ge=1, le=200),
):
    """List recent billing audit log events."""
    try:
        result = await admin_billing_service.list_billing_events(limit=limit)
        return BillingEventsResponse(**result)
    except Exception as exc:
        logger.error("Admin list billing events failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list billing events",
        ) from exc
