"""
billing.py

Billing and subscription management endpoints.
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.API_Deps.org_deps import (
    OrgContext,
    require_org_role,
    require_org_owner,
    get_active_org_id,
)
from tldw_Server_API.app.api.v1.schemas.billing_schemas import (
    PlanListResponse,
    SubscriptionPlanResponse,
    PlanLimitsResponse,
    OrgSubscriptionResponse,
    SubscriptionUsageResponse,
    CheckoutRequest,
    CheckoutResponse,
    PortalRequest,
    PortalResponse,
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    ResumeSubscriptionResponse,
    InvoiceListResponse,
    InvoiceResponse,
)
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Billing.subscription_service import get_subscription_service
from tldw_Server_API.app.core.Billing.stripe_client import is_billing_enabled


router = APIRouter(
    prefix="/billing",
    tags=["billing"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
    },
)


def _require_billing_enabled():
    """Raise error if billing is not enabled."""
    if not is_billing_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not enabled on this server",
        )


# =============================================================================
# Plans (Public)
# =============================================================================

@router.get(
    "/plans",
    response_model=PlanListResponse,
    summary="List available plans",
    description="List all publicly available subscription plans. No authentication required.",
)
async def list_plans():
    """List all available subscription plans."""
    service = await get_subscription_service()
    plans = await service.list_available_plans()

    return PlanListResponse(
        plans=[
            SubscriptionPlanResponse(
                id=p.get("id"),
                name=p["name"],
                display_name=p.get("display_name", p["name"].title()),
                description=p.get("description"),
                price_usd_monthly=p.get("price_usd_monthly", 0),
                price_usd_yearly=p.get("price_usd_yearly", 0),
                limits=PlanLimitsResponse(**p.get("limits", {})),
                is_active=p.get("is_active", True),
                is_public=p.get("is_public", True),
            )
            for p in plans
        ]
    )


# =============================================================================
# Subscription Status
# =============================================================================

@router.get(
    "/subscription",
    response_model=OrgSubscriptionResponse,
    summary="Get subscription status",
    description="Get the current subscription status for the organization.",
)
async def get_subscription(
    org_id: Optional[int] = Query(None, description="Organization ID (defaults to user's primary org)"),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Get the subscription status for an organization."""
    # Resolve org_id
    if org_id is None:
        from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
        user_orgs = await get_user_orgs(principal)
        if not user_orgs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not a member of any organization",
            )
        org_id = user_orgs[0]["org_id"]

    service = await get_subscription_service()
    sub = await service.get_subscription(org_id)

    return OrgSubscriptionResponse(
        org_id=org_id,
        plan_name=sub.plan_name,
        plan_display_name=sub.plan_display_name,
        status=sub.status,
        billing_cycle=sub.billing_cycle,
        current_period_end=sub.current_period_end,
        trial_end=sub.trial_end,
        cancel_at_period_end=sub.cancel_at_period_end,
        limits=sub.limits,
    )


@router.get(
    "/usage",
    response_model=SubscriptionUsageResponse,
    summary="Get usage vs limits",
    description="Get current usage compared to subscription limits.",
)
async def get_usage(
    org_id: Optional[int] = Query(None, description="Organization ID"),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Get current usage vs limits for an organization."""
    # Resolve org_id
    if org_id is None:
        from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
        user_orgs = await get_user_orgs(principal)
        if not user_orgs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not a member of any organization",
            )
        org_id = user_orgs[0]["org_id"]

    service = await get_subscription_service()

    # TODO: Get actual usage from usage tracking service
    # For now, return placeholder usage
    current_usage = {
        "api_calls_day": 0,
        "llm_tokens_month": 0,
        "storage_gb": 0,
        "team_members": 1,
    }

    usage_status = await service.check_usage(org_id, current_usage=current_usage)

    return SubscriptionUsageResponse(
        org_id=usage_status.org_id,
        plan_name=usage_status.plan_name,
        limits=usage_status.limits,
        usage=usage_status.usage,
        limit_checks=usage_status.limit_checks,
        has_warnings=usage_status.has_warnings,
        has_exceeded=usage_status.has_exceeded,
    )


# =============================================================================
# Checkout & Portal
# =============================================================================

@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Create checkout session",
    description="Create a Stripe checkout session to upgrade subscription.",
)
async def create_checkout(
    body: CheckoutRequest,
    org_id: Optional[int] = Query(None, description="Organization ID"),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Create a Stripe checkout session for subscription upgrade."""
    _require_billing_enabled()

    # Resolve org_id
    if org_id is None:
        from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
        user_orgs = await get_user_orgs(principal)
        if not user_orgs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not a member of any organization",
            )
        org_id = user_orgs[0]["org_id"]

    # Verify user has billing permissions (owner or admin)
    from tldw_Server_API.app.api.v1.API_Deps.org_deps import _get_user_org_membership
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners and admins can manage billing",
        )

    service = await get_subscription_service()

    try:
        session = await service.create_checkout_session(
            org_id=org_id,
            plan_name=body.plan_name,
            billing_cycle=body.billing_cycle,
            success_url=body.success_url,
            cancel_url=body.cancel_url,
            org_email=principal.email or f"user-{principal.user_id}@example.com",
            org_name=principal.username,
        )

        return CheckoutResponse(
            session_id=session.id,
            url=session.url,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Create billing portal session",
    description="Create a Stripe billing portal session for managing subscription.",
)
async def create_portal(
    body: PortalRequest,
    org_id: Optional[int] = Query(None, description="Organization ID"),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Create a Stripe billing portal session."""
    _require_billing_enabled()

    # Resolve org_id
    if org_id is None:
        from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
        user_orgs = await get_user_orgs(principal)
        if not user_orgs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not a member of any organization",
            )
        org_id = user_orgs[0]["org_id"]

    # Verify billing permissions
    from tldw_Server_API.app.api.v1.API_Deps.org_deps import _get_user_org_membership
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners and admins can access billing portal",
        )

    service = await get_subscription_service()

    try:
        session = await service.create_portal_session(
            org_id=org_id,
            return_url=body.return_url,
        )

        return PortalResponse(
            session_id=session.id,
            url=session.url,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


# =============================================================================
# Subscription Management
# =============================================================================

@router.post(
    "/subscription/cancel",
    response_model=CancelSubscriptionResponse,
    summary="Cancel subscription",
    description="Cancel the organization's subscription.",
)
async def cancel_subscription(
    body: CancelSubscriptionRequest,
    request: Request,
    org_id: Optional[int] = Query(None, description="Organization ID"),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Cancel the organization's subscription."""
    _require_billing_enabled()

    # Resolve org_id
    if org_id is None:
        from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
        user_orgs = await get_user_orgs(principal)
        if not user_orgs:
            raise HTTPException(status_code=404, detail="No organization found")
        org_id = user_orgs[0]["org_id"]

    # Verify owner role
    from tldw_Server_API.app.api.v1.API_Deps.org_deps import _get_user_org_membership
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can cancel subscriptions",
        )

    service = await get_subscription_service()

    try:
        ip_address = request.client.host if request.client else None
        result = await service.cancel_subscription(
            org_id,
            at_period_end=body.at_period_end,
            user_id=principal.user_id,
            ip_address=ip_address,
        )

        return CancelSubscriptionResponse(
            canceled=True,
            current_period_end=result.get("current_period_end"),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/subscription/resume",
    response_model=ResumeSubscriptionResponse,
    summary="Resume subscription",
    description="Resume a subscription that was set to cancel.",
)
async def resume_subscription(
    org_id: Optional[int] = Query(None, description="Organization ID"),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Resume a subscription that was set to cancel at period end."""
    _require_billing_enabled()

    # Resolve org_id
    if org_id is None:
        from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
        user_orgs = await get_user_orgs(principal)
        if not user_orgs:
            raise HTTPException(status_code=404, detail="No organization found")
        org_id = user_orgs[0]["org_id"]

    # Verify owner role
    from tldw_Server_API.app.api.v1.API_Deps.org_deps import _get_user_org_membership
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can resume subscriptions",
        )

    service = await get_subscription_service()

    try:
        await service.resume_subscription(org_id, user_id=principal.user_id)
        return ResumeSubscriptionResponse(resumed=True)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# Invoices
# =============================================================================

@router.get(
    "/invoices",
    response_model=InvoiceListResponse,
    summary="List invoices",
    description="List payment/invoice history for the organization.",
)
async def list_invoices(
    org_id: Optional[int] = Query(None, description="Organization ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """List invoice history for an organization."""
    # Resolve org_id
    if org_id is None:
        from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
        user_orgs = await get_user_orgs(principal)
        if not user_orgs:
            raise HTTPException(status_code=404, detail="No organization found")
        org_id = user_orgs[0]["org_id"]

    # Verify billing view permissions
    from tldw_Server_API.app.api.v1.API_Deps.org_deps import _get_user_org_membership
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners and admins can view invoices",
        )

    service = await get_subscription_service()
    invoices, total = await service.list_invoices(org_id, limit=limit, offset=offset)

    return InvoiceListResponse(
        items=[InvoiceResponse(**inv) for inv in invoices],
        total=total,
    )
