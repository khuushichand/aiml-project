"""
billing_webhooks.py

Stripe webhook handler endpoint.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Request, status
from loguru import logger

from tldw_Server_API.app.api.v1.schemas.billing_schemas import WebhookResponse
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.billing_repo import AuthnzBillingRepo
from tldw_Server_API.app.core.Billing.stripe_client import (
    StripeClient,
    get_stripe_client,
    is_billing_enabled,
)
from tldw_Server_API.app.core.Billing.subscription_service import get_subscription_service

router = APIRouter(
    prefix="/billing/webhooks",
    tags=["billing-webhooks"],
)


def _get_processing_timeout_seconds() -> int:
    """Get stale processing timeout for webhook claim recovery."""
    raw = os.environ.get("BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS", "300")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        logger.warning(
            "Invalid BILLING_WEBHOOK_PROCESSING_TIMEOUT_SECONDS value {!r}; using default 300",
            raw,
        )
        return 300


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

    # Ensure webhook secret is configured for real StripeClient instances.
    # Test doubles used in unit tests may not define a config attribute.
    if isinstance(stripe_client, StripeClient):
        config = getattr(stripe_client, "config", None)
        webhook_secret = getattr(config, "webhook_secret", None) if config else None
        if not webhook_secret:
            logger.error("Stripe webhook secret not configured for billing webhooks")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe webhook secret not configured",
            )

    try:
        event = stripe_client.construct_webhook_event(body, stripe_signature)
    except ValueError as e:
        logger.warning(f"Invalid Stripe webhook signature: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        ) from e

    event_id = event.get("id")
    event_type = event.get("type")
    event_data = event.get("data", {})

    if not event_id or not event_type:
        logger.error(
            f"Stripe webhook missing required fields: id={event_id!r}, type={event_type!r}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed webhook event",
        )

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
        event_status = await billing_repo.get_webhook_event_status(event_id)
        if event_status == "processed":
            # Already processed this event.
            logger.debug(f"Webhook event {event_id} already handled (status={event_status})")
            return WebhookResponse(
                received=True,
                event_type=event_type,
                handled=True,
            )

    # Atomically claim the event to prevent race conditions. Stale 'processing'
    # events can be reclaimed after a timeout to recover from worker crashes.
    # This handles edge cases where multiple webhook deliveries arrive simultaneously
    processing_timeout_seconds = _get_processing_timeout_seconds()
    claimed = await billing_repo.try_claim_webhook_event(
        event_id,
        processing_timeout_seconds=processing_timeout_seconds,
    )
    if not claimed:
        latest_status = await billing_repo.get_webhook_event_status(event_id)
        if latest_status == "processed":
            logger.debug(f"Webhook event {event_id} already handled (status={latest_status})")
            return WebhookResponse(
                received=True,
                event_type=event_type,
                handled=True,
            )
        logger.warning(
            "Webhook event {} not claimable (status={}); returning 503 for retry",
            event_id,
            latest_status,
        )
        # Return a retryable status for in-flight/non-terminal events so Stripe
        # redelivers if the active worker crashes before completion.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook event is still being processed",
        )

    # Process the event
    try:
        service = await get_subscription_service()
        result = await service.handle_webhook_event(event_type, event_data)
        handled = bool(result.get("handled", False))

        if not handled:
            reason = str(result.get("reason", "not_handled"))
            retryable = bool(result.get("retryable", True))
            if retryable:
                await billing_repo.mark_webhook_processed(
                    event_id,
                    error_message=f"Webhook event not handled: {reason}",
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Webhook processing failed",
                )
            await billing_repo.mark_webhook_processed(event_id)
            return WebhookResponse(
                received=True,
                event_type=event_type,
                handled=False,
            )

        # Mark as processed
        await billing_repo.mark_webhook_processed(event_id)

        return WebhookResponse(
            received=True,
            event_type=event_type,
            handled=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing webhook {event_id}: {e}")
        # Mark as failed
        await billing_repo.mark_webhook_processed(event_id, error_message=str(e))

        # Return 5xx so Stripe retries delivery after transient failures.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed",
        ) from e
