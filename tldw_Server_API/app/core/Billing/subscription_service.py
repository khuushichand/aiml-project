"""
subscription_service.py

Service for subscription and billing management.
Coordinates between the billing repository and Stripe client.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.billing_repo import AuthnzBillingRepo
from tldw_Server_API.app.core.Billing.stripe_client import (
    StripeClient,
    get_stripe_client,
    is_billing_enabled,
    CheckoutSession,
    PortalSession,
)
from tldw_Server_API.app.core.Billing.plan_limits import get_plan_limits, check_limit


@dataclass
class UsageStatus:
    """Current usage status for an organization."""
    org_id: int
    plan_name: str
    limits: Dict[str, Any]
    usage: Dict[str, int]
    limit_checks: Dict[str, Dict[str, Any]]
    has_warnings: bool
    has_exceeded: bool


@dataclass
class SubscriptionStatus:
    """Subscription status details."""
    org_id: int
    plan_name: str
    plan_display_name: str
    status: str
    billing_cycle: Optional[str]
    current_period_end: Optional[str]
    trial_end: Optional[str]
    cancel_at_period_end: bool
    limits: Dict[str, Any]


class SubscriptionService:
    """
    Service for subscription and billing management.

    Provides high-level operations for:
    - Listing available plans
    - Getting/creating subscriptions
    - Creating checkout and portal sessions
    - Checking usage against limits
    """

    def __init__(
        self,
        db_pool: Optional[DatabasePool] = None,
        billing_repo: Optional[AuthnzBillingRepo] = None,
        stripe_client: Optional[StripeClient] = None,
    ):
        self._db_pool = db_pool
        self._billing_repo = billing_repo
        self._stripe_client = stripe_client

    async def _get_db_pool(self) -> DatabasePool:
        if self._db_pool is None:
            self._db_pool = await get_db_pool()
        return self._db_pool

    async def _get_billing_repo(self) -> AuthnzBillingRepo:
        if self._billing_repo is None:
            pool = await self._get_db_pool()
            self._billing_repo = AuthnzBillingRepo(db_pool=pool)
        return self._billing_repo

    def _get_stripe_client(self) -> StripeClient:
        if self._stripe_client is None:
            self._stripe_client = get_stripe_client()
        return self._stripe_client

    # =========================================================================
    # Plans
    # =========================================================================

    async def list_available_plans(self) -> List[Dict[str, Any]]:
        """
        List all publicly available subscription plans.

        Returns plans from database, falling back to defaults if none exist.
        """
        repo = await self._get_billing_repo()
        plans = await repo.list_plans(active_only=True, public_only=True)

        if plans:
            return plans

        # Fallback to default plans
        return [
            {
                "name": "free",
                "display_name": "Free",
                "description": "Basic features for personal use",
                "price_usd_monthly": 0,
                "price_usd_yearly": 0,
                "limits": get_plan_limits("free"),
            },
            {
                "name": "pro",
                "display_name": "Pro",
                "description": "Advanced features for professionals",
                "price_usd_monthly": 29,
                "price_usd_yearly": 290,
                "limits": get_plan_limits("pro"),
            },
            {
                "name": "enterprise",
                "display_name": "Enterprise",
                "description": "Full features for organizations",
                "price_usd_monthly": 199,
                "price_usd_yearly": 1990,
                "limits": get_plan_limits("enterprise"),
            },
        ]

    async def get_plan(self, plan_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific plan by name."""
        repo = await self._get_billing_repo()
        plan = await repo.get_plan_by_name(plan_name)
        if plan:
            return plan
        # Fallback to defaults
        limits = get_plan_limits(plan_name)
        if limits:
            return {
                "name": plan_name,
                "display_name": plan_name.title(),
                "limits": limits,
            }
        return None

    # =========================================================================
    # Subscriptions
    # =========================================================================

    async def get_subscription(self, org_id: int) -> SubscriptionStatus:
        """
        Get the subscription status for an organization.

        Organizations without an explicit subscription are treated as being
        on the implicit free tier.
        """
        repo = await self._get_billing_repo()
        sub = await repo.get_org_subscription(org_id)

        if not sub:
            # Return implicit free tier status
            return SubscriptionStatus(
                org_id=org_id,
                plan_name="free",
                plan_display_name="Free",
                status="active",
                billing_cycle=None,
                current_period_end=None,
                trial_end=None,
                cancel_at_period_end=False,
                limits=get_plan_limits("free"),
            )

        return SubscriptionStatus(
            org_id=org_id,
            plan_name=sub.get("plan_name", "free"),
            plan_display_name=sub.get("plan_display_name", "Free"),
            status=sub.get("status", "active"),
            billing_cycle=sub.get("billing_cycle"),
            current_period_end=sub.get("current_period_end"),
            trial_end=sub.get("trial_end"),
            cancel_at_period_end=bool(sub.get("cancel_at_period_end")),
            limits=sub.get("effective_limits", get_plan_limits("free")),
        )

    async def create_subscription(
        self,
        *,
        org_id: int,
        plan_name: str,
        billing_cycle: str = "monthly",
        trial_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create or update a subscription for an organization.

        This creates the database record. For paid plans, a checkout session
        should be created separately.
        """
        repo = await self._get_billing_repo()

        # Get plan ID
        plan = await repo.get_plan_by_name(plan_name)
        if not plan:
            # Unknown plan names are treated as errors rather than silently
            # downgrading to the free tier. Callers should validate plan_name
            # against the available plans before invoking this method.
            raise ValueError(f"Plan '{plan_name}' not found")

        sub = await repo.create_org_subscription(
            org_id=org_id,
            plan_id=plan["id"],
            billing_cycle=billing_cycle,
            status="active" if plan_name == "free" else "pending",
            trial_days=trial_days,
        )

        # Log the action
        await repo.log_billing_action(
            org_id=org_id,
            action="subscription.created",
            details={
                "plan_name": plan_name,
                "billing_cycle": billing_cycle,
                "trial_days": trial_days,
            },
        )

        logger.info(f"Created subscription for org {org_id}: plan={plan_name}")
        return sub

    # =========================================================================
    # Stripe Integration
    # =========================================================================

    async def create_checkout_session(
        self,
        *,
        org_id: int,
        plan_name: str,
        billing_cycle: str = "monthly",
        success_url: str,
        cancel_url: str,
        org_email: str,
        org_name: Optional[str] = None,
    ) -> CheckoutSession:
        """
        Create a Stripe checkout session for a plan upgrade.

        Args:
            org_id: Organization ID
            plan_name: Target plan (pro, enterprise)
            billing_cycle: monthly or yearly
            success_url: Redirect URL on success
            cancel_url: Redirect URL on cancel
            org_email: Organization billing email
            org_name: Organization name for customer record

        Returns:
            CheckoutSession with id and url
        """
        if not is_billing_enabled():
            raise RuntimeError("Billing is not enabled")

        stripe = self._get_stripe_client()
        if not stripe.is_available:
            raise RuntimeError("Stripe is not configured")

        repo = await self._get_billing_repo()

        # Get or create Stripe customer
        sub = await repo.get_org_subscription(org_id)
        customer_id = sub.get("stripe_customer_id") if sub else None

        if not customer_id:
            # Create Stripe customer record first so we have a stable id for
            # downstream billing flows, then ensure the requested plan exists.
            customer_id = await stripe.create_customer(
                email=org_email,
                name=org_name,
                metadata={"org_id": str(org_id)},
            )
            # Save customer ID
            if sub:
                await repo.update_org_subscription(org_id, stripe_customer_id=customer_id)
            else:
                # Create pending subscription; unknown plans are treated as an
                # error rather than silently defaulting to an arbitrary plan.
                plan = await repo.get_plan_by_name(plan_name)
                if not plan:
                    raise ValueError(f"Plan '{plan_name}' not found")
                await repo.create_org_subscription(
                    org_id=org_id,
                    plan_id=plan["id"],
                    stripe_customer_id=customer_id,
                    billing_cycle=billing_cycle,
                    status="pending",
                )

        # Get price ID
        normalized_cycle = billing_cycle.lower()
        price_id = stripe.get_price_id(plan_name, normalized_cycle)
        if not price_id:
            # Try to get from database plan
            plan = await repo.get_plan_by_name(plan_name)
            if plan:
                if normalized_cycle == "yearly":
                    price_id = plan.get("stripe_price_id_yearly")
                else:
                    price_id = plan.get("stripe_price_id")

        if not price_id:
            raise ValueError(f"No Stripe price configured for plan '{plan_name}'")

        # Create checkout session
        session = await stripe.create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "org_id": str(org_id),
                "plan_name": plan_name,
                "billing_cycle": billing_cycle,
            },
        )

        # Log the action
        await repo.log_billing_action(
            org_id=org_id,
            action="checkout.initiated",
            details={
                "plan_name": plan_name,
                "billing_cycle": billing_cycle,
                "checkout_session_id": session.id,
            },
        )

        return session

    async def create_portal_session(
        self,
        *,
        org_id: int,
        return_url: str,
    ) -> PortalSession:
        """
        Create a Stripe billing portal session.

        Allows customers to manage their subscription, payment methods, etc.
        """
        if not is_billing_enabled():
            raise RuntimeError("Billing is not enabled")

        stripe = self._get_stripe_client()
        if not stripe.is_available:
            raise RuntimeError("Stripe is not configured")

        repo = await self._get_billing_repo()
        sub = await repo.get_org_subscription(org_id)

        if not sub or not sub.get("stripe_customer_id"):
            raise ValueError("Organization does not have a billing account")

        session = await stripe.create_portal_session(
            customer_id=sub["stripe_customer_id"],
            return_url=return_url,
        )

        return session

    async def cancel_subscription(
        self,
        org_id: int,
        *,
        at_period_end: bool = True,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel an organization's subscription."""
        repo = await self._get_billing_repo()
        sub = await repo.get_org_subscription(org_id)

        if not sub:
            raise ValueError("Organization does not have an active subscription")

        result = {"canceled": True}

        # Cancel in Stripe if applicable
        if sub.get("stripe_subscription_id") and is_billing_enabled():
            stripe = self._get_stripe_client()
            if stripe.is_available:
                result = await stripe.cancel_subscription(
                    sub["stripe_subscription_id"],
                    at_period_end=at_period_end,
                )

        # Update local status to mirror Stripe semantics:
        # - at_period_end=True  -> keep status "active", set cancel_at_period_end=True
        # - at_period_end=False -> set status "canceled", cancel_at_period_end=False
        if at_period_end:
            await repo.update_org_subscription(
                org_id,
                cancel_at_period_end=True,
            )
        else:
            await repo.update_org_subscription(
                org_id,
                status="canceled",
                cancel_at_period_end=False,
            )

        # Log the action
        await repo.log_billing_action(
            org_id=org_id,
            user_id=user_id,
            action="subscription.canceled",
            details={
                "at_period_end": at_period_end,
                "previous_status": sub.get("status"),
            },
            ip_address=ip_address,
        )

        logger.info(f"Canceled subscription for org {org_id} (at_period_end={at_period_end})")
        return result

    async def resume_subscription(
        self,
        org_id: int,
        *,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Resume a subscription that was set to cancel."""
        repo = await self._get_billing_repo()
        sub = await repo.get_org_subscription(org_id)

        if not sub:
            raise ValueError("Organization does not have a subscription")

        result = {"resumed": True}

        # Resume in Stripe if applicable
        if sub.get("stripe_subscription_id") and is_billing_enabled():
            stripe = self._get_stripe_client()
            if stripe.is_available:
                result = await stripe.resume_subscription(sub["stripe_subscription_id"])

        # Update local status
        await repo.update_org_subscription(org_id, status="active", cancel_at_period_end=False)

        # Log the action
        await repo.log_billing_action(
            org_id=org_id,
            user_id=user_id,
            action="subscription.resumed",
        )

        logger.info(f"Resumed subscription for org {org_id}")
        return result

    # =========================================================================
    # Usage & Limits
    # =========================================================================

    async def get_org_limits(self, org_id: int) -> Dict[str, Any]:
        """Get the effective limits for an organization."""
        repo = await self._get_billing_repo()
        return await repo.get_org_limits(org_id)

    async def check_usage(
        self,
        org_id: int,
        *,
        current_usage: Dict[str, int],
    ) -> UsageStatus:
        """
        Check current usage against limits.

        Args:
            org_id: Organization ID
            current_usage: Dict of current usage values by limit name

        Returns:
            UsageStatus with warnings and exceeded flags
        """
        limits = await self.get_org_limits(org_id)
        sub = await self.get_subscription(org_id)

        limit_checks = {}
        has_warnings = False
        has_exceeded = False

        # Check each provided usage value
        for limit_name, current_value in current_usage.items():
            limit_value = limits.get(limit_name)
            if limit_value is not None:
                check = check_limit(current_value, limit_value, limit_name)
                limit_checks[limit_name] = check
                if check["warning"]:
                    has_warnings = True
                if check["exceeded"]:
                    has_exceeded = True

        return UsageStatus(
            org_id=org_id,
            plan_name=sub.plan_name,
            limits=limits,
            usage=current_usage,
            limit_checks=limit_checks,
            has_warnings=has_warnings,
            has_exceeded=has_exceeded,
        )

    # =========================================================================
    # Webhook Handling
    # =========================================================================

    async def handle_webhook_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle a Stripe webhook event.

        Args:
            event_type: Stripe event type
            event_data: Event payload

        Returns:
            Processing result
        """
        repo = await self._get_billing_repo()

        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.created": self._handle_subscription_updated,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            return await handler(event_data, repo)

        logger.debug(f"Unhandled webhook event type: {event_type}")
        return {"handled": False, "event_type": event_type}

    async def _handle_checkout_completed(
        self,
        event_data: Dict[str, Any],
        repo: AuthnzBillingRepo,
    ) -> Dict[str, Any]:
        """Handle checkout.session.completed event."""
        session = event_data.get("object", {})
        metadata = session.get("metadata", {})
        org_id_str = metadata.get("org_id")

        if not org_id_str:
            logger.warning("Checkout completed without org_id in metadata")
            return {"handled": False, "reason": "missing_org_id"}

        try:
            org_id = int(org_id_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Checkout completed with invalid org_id '{org_id_str}': {e}")
            return {"handled": False, "reason": "invalid_org_id"}
        subscription_id = session.get("subscription")
        customer_id = session.get("customer")

        plan_updates: Dict[str, Any] = {}
        plan_name = metadata.get("plan_name")
        if plan_name:
            try:
                plan = await repo.get_plan_by_name(str(plan_name))
                if plan:
                    plan_updates["plan_id"] = plan["id"]
                else:
                    logger.warning(f"Checkout completed with unknown plan_name: {plan_name}")
            except Exception as exc:
                logger.warning(
                    f"Checkout completed: failed to resolve plan_name {plan_name}: {exc}"
                )

        billing_cycle = metadata.get("billing_cycle")
        if billing_cycle:
            cycle_norm = str(billing_cycle).strip().lower()
            if cycle_norm in {"monthly", "yearly"}:
                plan_updates["billing_cycle"] = cycle_norm

        # Update subscription record
        await repo.update_org_subscription(
            org_id,
            stripe_subscription_id=subscription_id,
            stripe_customer_id=customer_id,
            status="active",
            **plan_updates,
        )

        await repo.log_billing_action(
            org_id=org_id,
            action="checkout.completed",
            details={
                "subscription_id": subscription_id,
                "session_id": session.get("id"),
            },
        )

        logger.info(f"Checkout completed for org {org_id}")
        return {"handled": True, "org_id": org_id}

    async def _handle_subscription_updated(
        self,
        event_data: Dict[str, Any],
        repo: AuthnzBillingRepo,
    ) -> Dict[str, Any]:
        """Handle customer.subscription.updated event."""
        subscription = event_data.get("object", {})
        customer_id = subscription.get("customer")

        sub = await repo.get_subscription_by_stripe_customer(customer_id)
        if not sub:
            logger.warning(f"Subscription update for unknown customer {customer_id}")
            return {"handled": False, "reason": "unknown_customer"}

        org_id = sub["org_id"]

        # Try to determine the active plan from the subscription items so that
        # local plan_id / limits stay in sync with Stripe when upgrades or
        # downgrades are initiated from the Billing Portal.
        plan_updates: Dict[str, Any] = {}
        items = (subscription.get("items") or {}).get("data") or []
        if items:
            item0 = items[0] or {}
            price_obj = item0.get("price") or {}
            plan_obj = item0.get("plan") or {}

            price_id = price_obj.get("id") or item0.get("price_id")
            product_id = price_obj.get("product") or plan_obj.get("product")
            recurring = price_obj.get("recurring") or {}
            interval = recurring.get("interval") or plan_obj.get("interval")

            new_plan: Optional[Dict[str, Any]] = None
            if price_id:
                new_plan = await repo.get_plan_by_stripe_price_id(price_id)
            if not new_plan and product_id:
                new_plan = await repo.get_plan_by_stripe_product_id(product_id)

            if new_plan:
                plan_updates["plan_id"] = new_plan["id"]

            if interval == "year":
                plan_updates["billing_cycle"] = "yearly"
            elif interval == "month":
                plan_updates["billing_cycle"] = "monthly"

        # Always update status and period timestamps; merge any plan updates.
        stripe_status = subscription.get("status")
        update_fields: Dict[str, Any] = {
            "stripe_subscription_status": stripe_status,
            "current_period_start": datetime.fromtimestamp(
                subscription.get("current_period_start", 0),
                tz=timezone.utc,
            ).isoformat() if subscription.get("current_period_start") else None,
            "current_period_end": datetime.fromtimestamp(
                subscription.get("current_period_end", 0),
                tz=timezone.utc,
            ).isoformat() if subscription.get("current_period_end") else None,
            "trial_end": datetime.fromtimestamp(
                subscription.get("trial_end", 0),
                tz=timezone.utc,
            ).isoformat() if subscription.get("trial_end") else None,
            **plan_updates,
        }
        if stripe_status is not None:
            update_fields["status"] = stripe_status
        if subscription.get("cancel_at_period_end") is not None:
            update_fields["cancel_at_period_end"] = bool(subscription.get("cancel_at_period_end"))

        await repo.update_org_subscription(org_id, **update_fields)

        logger.info(
            "Subscription updated for org %s: status=%s, plan_updated=%s",
            org_id,
            subscription.get("status"),
            bool(plan_updates),
        )
        return {"handled": True, "org_id": org_id}

    async def _handle_subscription_deleted(
        self,
        event_data: Dict[str, Any],
        repo: AuthnzBillingRepo,
    ) -> Dict[str, Any]:
        """Handle customer.subscription.deleted event."""
        subscription = event_data.get("object", {})
        customer_id = subscription.get("customer")

        sub = await repo.get_subscription_by_stripe_customer(customer_id)
        if not sub:
            return {"handled": False, "reason": "unknown_customer"}

        org_id = sub["org_id"]

        # Downgrade to free plan
        free_plan = await repo.get_plan_by_name("free")
        await repo.update_org_subscription(
            org_id,
            plan_id=free_plan["id"] if free_plan else 1,
            status="active",
            stripe_subscription_id=None,
            stripe_subscription_status=None,
        )

        await repo.log_billing_action(
            org_id=org_id,
            action="subscription.deleted",
            details={"downgraded_to": "free"},
        )

        logger.info(f"Subscription deleted for org {org_id}, downgraded to free")
        return {"handled": True, "org_id": org_id}

    async def _handle_invoice_paid(
        self,
        event_data: Dict[str, Any],
        repo: AuthnzBillingRepo,
    ) -> Dict[str, Any]:
        """Handle invoice.paid event."""
        invoice = event_data.get("object", {})
        customer_id = invoice.get("customer")

        sub = await repo.get_subscription_by_stripe_customer(customer_id)
        if not sub:
            return {"handled": False, "reason": "unknown_customer"}

        org_id = sub["org_id"]

        # Record payment
        await repo.add_payment(
            org_id=org_id,
            stripe_invoice_id=invoice.get("id"),
            amount_cents=invoice.get("amount_paid", 0),
            currency=invoice.get("currency", "usd"),
            status="succeeded",
            description=invoice.get("description"),
            invoice_pdf_url=invoice.get("invoice_pdf"),
        )

        logger.info(f"Invoice paid for org {org_id}: ${invoice.get('amount_paid', 0) / 100:.2f}")
        return {"handled": True, "org_id": org_id}

    async def _handle_payment_failed(
        self,
        event_data: Dict[str, Any],
        repo: AuthnzBillingRepo,
    ) -> Dict[str, Any]:
        """Handle invoice.payment_failed event."""
        invoice = event_data.get("object", {})
        customer_id = invoice.get("customer")

        sub = await repo.get_subscription_by_stripe_customer(customer_id)
        if not sub:
            return {"handled": False, "reason": "unknown_customer"}

        org_id = sub["org_id"]

        # Record failed payment
        await repo.add_payment(
            org_id=org_id,
            stripe_invoice_id=invoice.get("id"),
            amount_cents=invoice.get("amount_due", 0),
            currency=invoice.get("currency", "usd"),
            status="failed",
            description="Payment failed",
            invoice_pdf_url=invoice.get("invoice_pdf"),
        )

        # Update subscription status to past_due
        await repo.update_org_subscription(org_id, status="past_due")

        await repo.log_billing_action(
            org_id=org_id,
            action="payment.failed",
            details={
                "invoice_id": invoice.get("id"),
                "amount_due": invoice.get("amount_due", 0),
            },
        )

        logger.warning(f"Payment failed for org {org_id}")
        return {"handled": True, "org_id": org_id}

    # =========================================================================
    # Payment History
    # =========================================================================

    async def list_invoices(
        self,
        org_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List payment/invoice history for an organization."""
        repo = await self._get_billing_repo()
        return await repo.list_payments(org_id, limit=limit, offset=offset)


# Singleton instance with async-safe initialization
_subscription_service: Optional[SubscriptionService] = None
_subscription_service_lock = asyncio.Lock()


async def get_subscription_service() -> SubscriptionService:
    """Get or create the subscription service singleton (async-safe)."""
    global _subscription_service
    if _subscription_service is None:
        async with _subscription_service_lock:
            # Double-check pattern for async safety
            if _subscription_service is None:
                _subscription_service = SubscriptionService()
    return _subscription_service


async def reset_subscription_service() -> None:
    """Reset the subscription service singleton (primarily for tests)."""
    global _subscription_service
    _subscription_service = None
