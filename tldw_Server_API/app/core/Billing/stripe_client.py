"""
stripe_client.py

Stripe API wrapper for billing operations.
Handles customer creation, checkout sessions, billing portal, and subscription management.
"""
from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from typing import Any

from loguru import logger

# Stripe import is optional - will be None if not installed
try:
    import stripe
    import stripe.error  # Import error module for specific exception types
    STRIPE_AVAILABLE = True
except ImportError:
    stripe = None
    STRIPE_AVAILABLE = False

# Error handling strategy:
# - Most methods catch stripe.StripeError (base class) to log and re-raise
# - get_subscription catches stripe.error.InvalidRequestError for "not found" (returns None)
# - construct_webhook_event catches stripe.error.SignatureVerificationError for invalid signatures


@dataclass
class CheckoutSession:
    """Checkout session result."""
    id: str
    url: str


@dataclass
class PortalSession:
    """Billing portal session result."""
    id: str
    url: str


@dataclass
class StripeConfig:
    """Stripe configuration."""
    api_key: str
    webhook_secret: str | None = None
    # Default product/price IDs (can be overridden per plan in DB)
    price_pro_monthly: str | None = None
    price_pro_yearly: str | None = None
    price_enterprise_monthly: str | None = None
    price_enterprise_yearly: str | None = None


def get_stripe_config() -> StripeConfig | None:
    """Load Stripe configuration from environment."""
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        return None

    return StripeConfig(
        api_key=api_key,
        webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET"),
        price_pro_monthly=os.environ.get("STRIPE_PRICE_PRO_MONTHLY"),
        price_pro_yearly=os.environ.get("STRIPE_PRICE_PRO_YEARLY"),
        price_enterprise_monthly=os.environ.get("STRIPE_PRICE_ENTERPRISE_MONTHLY"),
        price_enterprise_yearly=os.environ.get("STRIPE_PRICE_ENTERPRISE_YEARLY"),
    )


class StripeClient:
    """
    Client for Stripe API operations.

    This class wraps the Stripe SDK and provides higher-level operations
    for subscription management.
    """

    def __init__(self, config: StripeConfig | None = None):
        self.config = config or get_stripe_config()
        self._initialized = False

        if self.config and STRIPE_AVAILABLE:
            stripe.api_key = self.config.api_key
            self._initialized = True

    @property
    def is_available(self) -> bool:
        """Check if Stripe is configured and available."""
        return self._initialized and STRIPE_AVAILABLE

    def _require_stripe(self) -> None:
        """Raise error if Stripe is not available."""
        if not STRIPE_AVAILABLE:
            raise RuntimeError("Stripe SDK is not installed. Install with: pip install stripe")
        if not self._initialized:
            raise RuntimeError("Stripe is not configured. Set STRIPE_API_KEY environment variable.")

    async def create_customer(
        self,
        *,
        email: str,
        name: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Create a Stripe customer.

        Args:
            email: Customer email
            name: Customer name
            metadata: Additional metadata (e.g., org_id)

        Returns:
            Stripe customer ID
        """
        self._require_stripe()

        try:
            customer = await asyncio.to_thread(
                stripe.Customer.create,
                email=email,
                name=name,
                metadata=metadata or {},
            )
            logger.info(f"Created Stripe customer {customer.id} for {email}")
            return customer.id
        except stripe.StripeError as e:
            logger.error(f"Failed to create Stripe customer: {e}")
            raise

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_days: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> CheckoutSession:
        """
        Create a Stripe Checkout session for subscription.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            trial_days: Optional trial period
            metadata: Additional metadata

        Returns:
            CheckoutSession with id and url
        """
        self._require_stripe()

        try:
            params: dict[str, Any] = {
                "customer": customer_id,
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
            }

            if trial_days:
                params["subscription_data"] = {
                    "trial_period_days": trial_days,
                }

            session = await asyncio.to_thread(stripe.checkout.Session.create, **params)
            logger.info(f"Created checkout session {session.id} for customer {customer_id}")
            return CheckoutSession(id=session.id, url=session.url)
        except stripe.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise

    async def create_portal_session(
        self,
        *,
        customer_id: str,
        return_url: str,
    ) -> PortalSession:
        """
        Create a Stripe Billing Portal session.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to return to after portal

        Returns:
            PortalSession with id and url
        """
        self._require_stripe()

        try:
            session = await asyncio.to_thread(
                stripe.billing_portal.Session.create,
                customer=customer_id,
                return_url=return_url,
            )
            logger.info(f"Created portal session for customer {customer_id}")
            return PortalSession(id=session.id, url=session.url)
        except stripe.StripeError as e:
            logger.error(f"Failed to create portal session: {e}")
            raise

    async def cancel_subscription(
        self,
        subscription_id: str,
        *,
        at_period_end: bool = True,
    ) -> dict[str, Any]:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            at_period_end: If True, cancel at end of current period

        Returns:
            Updated subscription data
        """
        self._require_stripe()

        try:
            if at_period_end:
                subscription = await asyncio.to_thread(
                    stripe.Subscription.modify,
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                subscription = await asyncio.to_thread(
                    stripe.Subscription.cancel,
                    subscription_id,
                )

            logger.info(f"Cancelled subscription {subscription_id} (at_period_end={at_period_end})")
            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "current_period_end": subscription.current_period_end,
            }
        except stripe.StripeError as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise

    async def resume_subscription(self, subscription_id: str) -> dict[str, Any]:
        """
        Resume a subscription that was set to cancel at period end.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Updated subscription data
        """
        self._require_stripe()

        try:
            subscription = await asyncio.to_thread(
                stripe.Subscription.modify,
                subscription_id,
                cancel_at_period_end=False,
            )
            logger.info(f"Resumed subscription {subscription_id}")
            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }
        except stripe.StripeError as e:
            logger.error(f"Failed to resume subscription: {e}")
            raise

    async def get_subscription(self, subscription_id: str) -> dict[str, Any] | None:
        """
        Get subscription details from Stripe.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription data or None if not found
        """
        self._require_stripe()

        try:
            subscription = await asyncio.to_thread(
                stripe.Subscription.retrieve,
                subscription_id,
            )
            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "trial_end": subscription.trial_end,
                "items": [
                    {
                        "price_id": item.price.id,
                        "product_id": item.price.product,
                    }
                    for item in (subscription.items.data if subscription.items else [])
                ],
            }
        except stripe.error.InvalidRequestError:
            return None
        except stripe.StripeError as e:
            logger.error(f"Failed to get subscription: {e}")
            raise

    def construct_webhook_event(
        self,
        payload: bytes | str,
        signature: str,
    ) -> Any:
        """
        Construct and verify a webhook event from Stripe.

        Args:
            payload: Raw request body (bytes or string)
            signature: Stripe-Signature header

        Returns:
            Verified Stripe event

        Raises:
            ValueError: If signature verification fails or payload cannot be decoded
        """
        self._require_stripe()

        if not self.config or not self.config.webhook_secret:
            raise RuntimeError("Stripe webhook secret not configured")

        if isinstance(payload, bytes):
            try:
                payload_str = payload.decode("utf-8")
            except UnicodeDecodeError as e:
                logger.warning(f"Webhook payload decode failed: {e}")
                raise ValueError("Invalid webhook payload")
        else:
            payload_str = payload

        try:
            return stripe.Webhook.construct_event(
                payload_str,
                signature,
                self.config.webhook_secret,
            )
        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Webhook signature verification failed: {e}")
            raise ValueError("Invalid webhook signature")

    def get_price_id(self, plan_name: str, billing_cycle: str = "monthly") -> str | None:
        """
        Get the Stripe price ID for a plan.

        Args:
            plan_name: Plan name (pro, enterprise)
            billing_cycle: monthly or yearly

        Returns:
            Stripe price ID or None
        """
        if not self.config:
            return None

        price_map = {
            ("pro", "monthly"): self.config.price_pro_monthly,
            ("pro", "yearly"): self.config.price_pro_yearly,
            ("enterprise", "monthly"): self.config.price_enterprise_monthly,
            ("enterprise", "yearly"): self.config.price_enterprise_yearly,
        }

        return price_map.get((plan_name.lower(), billing_cycle.lower()))


# Singleton instance with thread-safe initialization
_stripe_client: StripeClient | None = None
_stripe_client_lock = threading.Lock()


def get_stripe_client() -> StripeClient:
    """Get or create the Stripe client singleton (thread-safe)."""
    global _stripe_client
    if _stripe_client is None:
        with _stripe_client_lock:
            # Double-check pattern for thread safety
            if _stripe_client is None:
                _stripe_client = StripeClient()
    return _stripe_client


def is_billing_enabled() -> bool:
    """Check if billing is enabled."""
    return os.environ.get("BILLING_ENABLED", "false").lower() == "true"
