"""
billing.py

Billing and subscription management endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_auth_principal
from tldw_Server_API.app.api.v1.API_Deps.org_deps import (
    _get_user_org_membership,
    get_active_org_id,
)
from tldw_Server_API.app.api.v1.schemas.billing_schemas import (
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    CheckoutRequest,
    CheckoutResponse,
    InvoiceListResponse,
    InvoiceResponse,
    OrgSubscriptionResponse,
    PlanLimitsResponse,
    PlanListResponse,
    PortalRequest,
    PortalResponse,
    RagUsageDebugResponse,
    ResumeSubscriptionResponse,
    SubscriptionPlanResponse,
    SubscriptionUsageResponse,
)
from tldw_Server_API.app.core.AuthNZ.input_validation import validate_email
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal
from tldw_Server_API.app.core.Billing.enforcement import get_billing_enforcer
from tldw_Server_API.app.core.Billing.stripe_client import is_billing_enabled
from tldw_Server_API.app.core.Billing.subscription_service import get_subscription_service

router = APIRouter(
    prefix="/billing",
    tags=["billing"],
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
    },
)


async def _require_billing_enabled():
    """Raise error if billing is not enabled."""
    if not is_billing_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not enabled on this server",
        )


async def _resolve_org_id(principal: AuthPrincipal, org_id: int | None) -> int:
    """
    Resolve org_id from parameter or user's primary organization.

    Args:
        principal: Authenticated user
        org_id: Optional explicit org_id

    Returns:
        Resolved org_id

    Raises:
        HTTPException: If user has no organizations

    Notes:
        When org_id is omitted, the first organization in the user's membership list is used.
        Multi-org users should pass org_id explicitly to avoid ambiguity.
    """
    if org_id is not None:
        return org_id

    from tldw_Server_API.app.api.v1.API_Deps.org_deps import get_user_orgs
    user_orgs = await get_user_orgs(principal)
    if not user_orgs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of any organization",
        )
    return user_orgs[0]["org_id"]


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
    description=(
        "Get the current subscription status for the organization. "
        "Uses X-TLDW-Org-Id when provided; otherwise defaults to the first organization in your membership list."
    ),
)
async def get_subscription(
    org_id: int | None = Depends(get_active_org_id),
):
    """Get the subscription status for an organization."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of any organization",
        )

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
    description=(
        "Get current usage compared to subscription limits. "
        "Uses X-TLDW-Org-Id when provided; otherwise defaults to the first organization in your membership list."
    ),
)
async def get_usage(
    org_id: int | None = Depends(get_active_org_id),
):
    """Get current usage vs limits for an organization."""
    if org_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of any organization",
        )

    service = await get_subscription_service()

    enforcer = get_billing_enforcer()
    usage_summary = await enforcer.get_org_usage(org_id)

    current_usage = {
        "api_calls_day": usage_summary.api_calls_today,
        "llm_tokens_month": usage_summary.llm_tokens_month,
        "storage_mb": round(usage_summary.storage_bytes / (1024 ** 2), 2),  # Convert bytes to MB
        "team_members": usage_summary.team_members,
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


@router.get(
    "/usage/rag",
    response_model=RagUsageDebugResponse,
    summary="Get RAG usage (debug)",
    description="Debug endpoint: current day's RAG queries vs plan limit for the organization.",
)
async def get_rag_usage_debug(
    org_id: int | None = Query(
        None,
        description="Organization ID (defaults to the first organization in your membership list)",
    ),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Debug view of RAG usage vs daily limit for an organization."""
    org_id = await _resolve_org_id(principal, org_id)

    # Verify billing view permissions
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners and admins can view RAG usage",
        )

    enforcer = get_billing_enforcer()
    usage_summary = await enforcer.get_org_usage(org_id)
    limits = await enforcer.get_org_limits(org_id)

    return RagUsageDebugResponse(
        org_id=org_id,
        rag_queries_today=usage_summary.rag_queries_today,
        rag_queries_day_limit=limits.get("rag_queries_day"),
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
    org_id: int | None = Query(
        None,
        description="Organization ID (defaults to the first organization in your membership list)",
    ),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Create a Stripe checkout session for subscription upgrade."""
    await _require_billing_enabled()
    org_id = await _resolve_org_id(principal, org_id)

    # Verify user has billing permissions (owner or admin)
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners and admins can manage billing",
        )

    service = await get_subscription_service()
    if not await service.get_plan_for_checkout(body.plan_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unknown or inactive plan. Ensure the plan exists in subscription_plans.",
        )

    try:
        principal_email = getattr(principal, "email", None)
        if not principal_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Billing requires a valid email address for the authenticated user.",
            )
        principal_email_str = str(principal_email).strip()
        is_valid_email, email_error = validate_email(principal_email_str)
        if not is_valid_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Billing requires a valid email address: {email_error or 'invalid email'}",
            )
        logger.info(f"Creating checkout session: org_id={org_id}, plan={body.plan_name}, user_id={principal.user_id}")
        session = await service.create_checkout_session(
            org_id=org_id,
            plan_name=body.plan_name,
            billing_cycle=body.billing_cycle,
            success_url=str(body.success_url),
            cancel_url=str(body.cancel_url),
            org_email=principal_email_str,
            org_name=principal.username,
        )

        logger.info(f"Checkout session created: session_id={session.id}, org_id={org_id}")
        return CheckoutResponse(
            session_id=session.id,
            url=session.url,
        )
    except ValueError as e:
        logger.warning(f"Checkout failed for org_id={org_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        logger.error(f"Checkout service error for org_id={org_id}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e


@router.post(
    "/portal",
    response_model=PortalResponse,
    summary="Create billing portal session",
    description="Create a Stripe billing portal session for managing subscription.",
)
async def create_portal(
    body: PortalRequest,
    org_id: int | None = Query(
        None,
        description="Organization ID (defaults to the first organization in your membership list)",
    ),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Create a Stripe billing portal session."""
    await _require_billing_enabled()
    org_id = await _resolve_org_id(principal, org_id)

    # Verify billing permissions
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners and admins can access billing portal",
        )

    service = await get_subscription_service()

    try:
        logger.info(f"Creating portal session: org_id={org_id}, user_id={principal.user_id}")
        session = await service.create_portal_session(
            org_id=org_id,
            return_url=str(body.return_url),
        )

        logger.info(f"Portal session created: session_id={session.id}, org_id={org_id}")
        return PortalResponse(
            session_id=session.id,
            url=session.url,
        )
    except ValueError as e:
        logger.warning(f"Portal session failed for org_id={org_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except RuntimeError as e:
        logger.error(f"Portal service error for org_id={org_id}: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e


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
    org_id: int | None = Query(
        None,
        description="Organization ID (defaults to the first organization in your membership list)",
    ),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Cancel the organization's subscription."""
    await _require_billing_enabled()
    org_id = await _resolve_org_id(principal, org_id)

    # Verify owner role
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can cancel subscriptions",
        )

    service = await get_subscription_service()

    try:
        ip_address = request.client.host if request.client else None
        logger.info(f"Canceling subscription: org_id={org_id}, at_period_end={body.at_period_end}, user_id={principal.user_id}")
        result = await service.cancel_subscription(
            org_id,
            at_period_end=body.at_period_end,
            user_id=principal.user_id,
            ip_address=ip_address,
        )

        logger.info(f"Subscription canceled: org_id={org_id}")
        return CancelSubscriptionResponse(
            canceled=True,
            current_period_end=result.get("current_period_end"),
        )
    except ValueError as e:
        logger.warning(f"Cancel subscription failed for org_id={org_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/subscription/resume",
    response_model=ResumeSubscriptionResponse,
    summary="Resume subscription",
    description="Resume a subscription that was set to cancel.",
)
async def resume_subscription(
    org_id: int | None = Query(
        None,
        description="Organization ID (defaults to the first organization in your membership list)",
    ),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """Resume a subscription that was set to cancel at period end."""
    await _require_billing_enabled()
    org_id = await _resolve_org_id(principal, org_id)

    # Verify owner role
    membership = await _get_user_org_membership(principal.user_id, org_id)
    if not membership or membership.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can resume subscriptions",
        )

    service = await get_subscription_service()

    try:
        logger.info(f"Resuming subscription: org_id={org_id}, user_id={principal.user_id}")
        await service.resume_subscription(org_id, user_id=principal.user_id)
        logger.info(f"Subscription resumed: org_id={org_id}")
        return ResumeSubscriptionResponse(resumed=True)
    except ValueError as e:
        logger.warning(f"Resume subscription failed for org_id={org_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


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
    org_id: int | None = Query(
        None,
        description="Organization ID (defaults to the first organization in your membership list)",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    principal: AuthPrincipal = Depends(get_auth_principal),
):
    """List invoice history for an organization."""
    org_id = await _resolve_org_id(principal, org_id)
    await _require_billing_enabled()

    # Verify billing view permissions
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
