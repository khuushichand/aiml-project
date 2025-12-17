"""
billing_webhooks.py

Stripe webhook handler endpoint.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.billing_schemas import WebhookResponse
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.billing_repo import AuthnzBillingRepo
from tldw_Server_API.app.core.Billing.subscription_service import get_subscription_service
from tldw_Server_API.app.core.Billing.stripe_client import get_stripe_client, is_billing_enabled


router = APIRouter(
    prefix="/billing/webhooks",
    tags=["billing-webhooks"],
)


@router.post(
    "/stripe",
    response_model=WebhookResponse,
    summary="Stripe webhook handler",
    description="Handle incoming Stripe webhook events. This endpoint verifies the webhook signature.",
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
):
    """
    Handle Stripe webhook events.

    This endpoint:
    1. Verifies the webhook signature
    2. Records the event for idempotency
    3. Processes the event (checkout completed, subscription updated, etc.)
    """
    if not is_billing_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not enabled",
        )

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature and construct event
    stripe_client = get_stripe_client()
    if not stripe_client.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    try:
        event = stripe_client.construct_webhook_event(body, stripe_signature)
    except ValueError as e:
        logger.warning(f"Invalid Stripe webhook signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    event_id = event.get("id")
    event_type = event.get("type")
    event_data = event.get("data", {})

    logger.info(f"Received Stripe webhook: {event_type} ({event_id})")

    # Record event for idempotency
    db_pool = await get_db_pool()
    billing_repo = AuthnzBillingRepo(db_pool=db_pool)

    is_new = await billing_repo.record_webhook_event(
        stripe_event_id=event_id,
        event_type=event_type,
        event_data=event_data,
    )

    if not is_new:
        # Already processed this event
        logger.debug(f"Webhook event {event_id} already processed")
        return WebhookResponse(
            received=True,
            event_type=event_type,
            handled=True,
        )

    # Process the event
    try:
        service = await get_subscription_service()
        result = await service.handle_webhook_event(event_type, event_data)

        # Mark as processed
        await billing_repo.mark_webhook_processed(event_id)

        return WebhookResponse(
            received=True,
            event_type=event_type,
            handled=result.get("handled", False),
        )
    except Exception as e:
        logger.error(f"Error processing webhook {event_id}: {e}")
        # Mark as failed
        await billing_repo.mark_webhook_processed(event_id, error_message=str(e))

        # Still return 200 to Stripe to prevent retries
        # (we've recorded the failure for manual review)
        return WebhookResponse(
            received=True,
            event_type=event_type,
            handled=False,
        )
