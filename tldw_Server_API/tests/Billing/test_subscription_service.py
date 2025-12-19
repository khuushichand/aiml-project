"""
Unit tests for SubscriptionService.

These tests focus on subscription creation semantics, specifically:
- Unknown plan names should raise a ValueError rather than silently
  downgrading to the free tier.
- Valid plan names should delegate to the billing repo with the expected
  arguments and status values.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pytest

from tldw_Server_API.app.core.Billing.subscription_service import SubscriptionService
from tldw_Server_API.app.core.AuthNZ.repos.billing_repo import AuthnzBillingRepo


class _FakeBillingRepo:
    def __init__(self) -> None:
        self.last_create_args: Optional[Dict[str, Any]] = None
        self.last_log_action: Optional[Dict[str, Any]] = None
        self.last_updated_subscription: Optional[Dict[str, Any]] = None
        self.last_payment: Optional[Dict[str, Any]] = None

    async def get_plan_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        if name == "free":
            return {"id": 1, "name": "free"}
        if name == "pro":
            return {"id": 2, "name": "pro"}
        return None

    async def create_org_subscription(
        self,
        *,
        org_id: int,
        plan_id: int,
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        billing_cycle: str = "monthly",
        status: str = "active",
        trial_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.last_create_args = {
            "org_id": org_id,
            "plan_id": plan_id,
            "billing_cycle": billing_cycle,
            "status": status,
            "trial_days": trial_days,
        }
        return {
            "org_id": org_id,
            "plan_id": plan_id,
            "billing_cycle": billing_cycle,
            "status": status,
        }

    async def log_billing_action(
        self,
        *,
        org_id: int,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.last_log_action = {
            "org_id": org_id,
            "action": action,
            "details": details,
        }
        return {
            "org_id": org_id,
            "action": action,
            "details": details,
        }

    # Checkout-specific helpers ------------------------------------------------

    async def get_org_subscription(self, org_id: int) -> Optional[Dict[str, Any]]:
        # In checkout tests we want the "no existing subscription" branch.
        return None

    async def update_org_subscription(self, org_id: int, **updates: Any) -> None:  # pragma: no cover - defensive
        # For checkout/creation tests we do not expect this to be called.
        raise AssertionError("update_org_subscription should not be called in these tests")

    # Webhook-related helpers --------------------------------------------------

    async def get_subscription_by_stripe_customer(self, stripe_customer_id: str) -> Optional[Dict[str, Any]]:
        # Default: pretend we have a pro subscription for org 1
        if stripe_customer_id == "cus_pro_1":
            return {
                "org_id": 1,
                "plan_id": 2,
                "plan_name": "pro",
                "plan_display_name": "Pro",
                "plan_limits_json": '{"api_calls_day": 5000}',
                "custom_limits_json": None,
            }
        return None

    async def get_plan_by_stripe_price_id(self, price_id: str) -> Optional[Dict[str, Any]]:
        if price_id == "price_pro":
            return {"id": 2, "name": "pro"}
        if price_id == "price_enterprise":
            return {"id": 3, "name": "enterprise"}
        return None

    async def get_plan_by_stripe_product_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        if product_id == "prod_pro":
            return {"id": 2, "name": "pro"}
        if product_id == "prod_enterprise":
            return {"id": 3, "name": "enterprise"}
        return None

    async def update_org_subscription(self, org_id: int, **updates: Any) -> None:
        # Record last update for assertions in webhook tests.
        self.last_updated_subscription = {"org_id": org_id, **updates}

    async def add_payment(
        self,
        *,
        org_id: int,
        stripe_invoice_id: Optional[str] = None,
        amount_cents: int,
        currency: str = "usd",
        status: str = "succeeded",
        description: Optional[str] = None,
        invoice_pdf_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.last_payment = {
            "org_id": org_id,
            "stripe_invoice_id": stripe_invoice_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "status": status,
            "description": description,
            "invoice_pdf_url": invoice_pdf_url,
        }
        return dict(self.last_payment)


class _FakeStripeClient:
    """Minimal Stripe client stub for checkout tests."""

    def __init__(self) -> None:
        self.is_available = True

    async def create_customer(self, *, email: str, name: Optional[str] = None, metadata: Optional[Dict[str, str]] = None) -> str:
        return "cus_test_123"

    def get_price_id(self, plan_name: str, billing_cycle: str = "monthly") -> Optional[str]:
        # Price lookup should never be reached in the unknown-plan test.
        return "price_test_123"

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, str]] = None,
    ):
        from tldw_Server_API.app.core.Billing.stripe_client import CheckoutSession

        return CheckoutSession(id="sess_test_123", url="https://example.com/checkout")


@pytest.mark.asyncio
async def test_create_subscription_unknown_plan_raises_value_error() -> None:
    """create_subscription should raise when plan_name is unknown."""
    repo = _FakeBillingRepo()
    service = SubscriptionService(billing_repo=repo)

    with pytest.raises(ValueError) as exc_info:
        await service.create_subscription(org_id=42, plan_name="unknown_plan")

    assert "unknown_plan" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_subscription_for_known_plan_uses_repo_and_logs() -> None:
    """create_subscription should delegate to billing repo for known plans."""
    repo = _FakeBillingRepo()
    service = SubscriptionService(billing_repo=repo)

    result = await service.create_subscription(
        org_id=7,
        plan_name="pro",
        billing_cycle="yearly",
        trial_days=14,
    )

    # Repo create call should reflect the requested plan and parameters.
    assert repo.last_create_args is not None
    assert repo.last_create_args["org_id"] == 7
    assert repo.last_create_args["plan_id"] == 2  # pro plan
    assert repo.last_create_args["billing_cycle"] == "yearly"
    # Non-free plans start as pending
    assert repo.last_create_args["status"] == "pending"
    assert repo.last_create_args["trial_days"] == 14

    # Returned subscription mirrors repo output.
    assert result["org_id"] == 7
    assert result["plan_id"] == 2
    assert result["billing_cycle"] == "yearly"
    assert result["status"] == "pending"

    # Billing action should be logged.
    assert repo.last_log_action is not None
    assert repo.last_log_action["org_id"] == 7
    assert repo.last_log_action["action"] == "subscription.created"
    details = repo.last_log_action["details"] or {}
    assert details.get("plan_name") == "pro"
    assert details.get("billing_cycle") == "yearly"
    assert details.get("trial_days") == 14


@pytest.mark.asyncio
async def test_create_checkout_session_unknown_plan_raises_value_error(monkeypatch) -> None:
    """create_checkout_session should raise when the requested plan does not exist."""

    # Ensure billing checks pass for the unit test.
    monkeypatch.setattr(
        "tldw_Server_API.app.core.Billing.subscription_service.is_billing_enabled",
        lambda: True,
    )

    class _RepoNoPlan(_FakeBillingRepo):
        async def get_plan_by_name(self, name: str) -> Optional[Dict[str, Any]]:
            # Simulate missing plan in DB for all names.
            return None

    repo = _RepoNoPlan()
    stripe_client = _FakeStripeClient()
    service = SubscriptionService(billing_repo=repo, stripe_client=stripe_client)

    with pytest.raises(ValueError) as exc_info:
        await service.create_checkout_session(
            org_id=42,
            plan_name="pro",
            billing_cycle="monthly",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            org_email="owner@example.com",
            org_name="Example Org",
        )

    msg = str(exc_info.value)
    assert "Plan 'pro' not found" in msg


@pytest.mark.asyncio
async def test_handle_subscription_updated_updates_plan_from_price(monkeypatch) -> None:
    """_handle_subscription_updated should update plan_id when price_id maps to a new plan."""

    repo = _FakeBillingRepo()
    service = SubscriptionService(billing_repo=repo)

    event_data = {
        "object": {
            "customer": "cus_pro_1",
            "status": "active",
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "items": {
                "data": [
                    {
                        "price": {
                            "id": "price_enterprise",
                            "product": "prod_enterprise",
                        }
                    }
                ]
            },
        }
    }

    result = await service._handle_subscription_updated(event_data, repo)  # type: ignore[attr-defined]

    assert result["handled"] is True
    assert repo.last_updated_subscription is not None
    assert repo.last_updated_subscription["org_id"] == 1
    # Plan should be updated to enterprise plan (id=3 in fake repo)
    assert repo.last_updated_subscription["plan_id"] == 3
    assert repo.last_updated_subscription["stripe_subscription_status"] == "active"


@pytest.mark.asyncio
async def test_handle_subscription_updated_updates_status_when_plan_unknown(monkeypatch) -> None:
    """_handle_subscription_updated should still update status even when plan cannot be resolved."""

    class _RepoNoPlanMapping(_FakeBillingRepo):
        async def get_plan_by_stripe_price_id(self, price_id: str) -> Optional[Dict[str, Any]]:
            return None

        async def get_plan_by_stripe_product_id(self, product_id: str) -> Optional[Dict[str, Any]]:
            return None

    repo = _RepoNoPlanMapping()
    service = SubscriptionService(billing_repo=repo)

    event_data = {
        "object": {
            "customer": "cus_pro_1",
            "status": "past_due",
            "current_period_start": 1700000000,
            "current_period_end": 1702592000,
            "items": {
                "data": [
                    {
                        "price": {
                            "id": "price_unknown",
                            "product": "prod_unknown",
                        }
                    }
                ]
            },
        }
    }

    result = await service._handle_subscription_updated(event_data, repo)  # type: ignore[attr-defined]

    assert result["handled"] is True
    assert repo.last_updated_subscription is not None
    assert repo.last_updated_subscription["org_id"] == 1
    # Plan_id should not be present when mapping fails
    assert "plan_id" not in repo.last_updated_subscription
    assert repo.last_updated_subscription["stripe_subscription_status"] == "past_due"


@pytest.mark.asyncio
async def test_handle_payment_failed_records_currency_and_pdf(monkeypatch) -> None:
    """_handle_payment_failed should record invoice currency and PDF URL and mark subscription past_due."""

    repo = _FakeBillingRepo()
    service = SubscriptionService(billing_repo=repo)

    event_data = {
        "object": {
            "customer": "cus_pro_1",
            "id": "in_test_123",
            "amount_due": 4321,
            "currency": "eur",
            "invoice_pdf": "https://example.com/invoice.pdf",
        }
    }

    result = await service._handle_payment_failed(event_data, repo)  # type: ignore[attr-defined]

    assert result["handled"] is True

    # Payment record should reflect invoice fields.
    assert repo.last_payment is not None
    assert repo.last_payment["org_id"] == 1
    assert repo.last_payment["stripe_invoice_id"] == "in_test_123"
    assert repo.last_payment["amount_cents"] == 4321
    assert repo.last_payment["currency"] == "eur"
    assert repo.last_payment["status"] == "failed"
    assert repo.last_payment["description"] == "Payment failed"
    assert repo.last_payment["invoice_pdf_url"] == "https://example.com/invoice.pdf"

    # Subscription should be marked past_due.
    assert repo.last_updated_subscription is not None
    assert repo.last_updated_subscription["org_id"] == 1
    assert repo.last_updated_subscription["status"] == "past_due"


@pytest.mark.asyncio
async def test_handle_payment_failed_uses_default_currency_when_missing(monkeypatch) -> None:
    """_handle_payment_failed should default currency to usd when invoice currency is missing."""

    repo = _FakeBillingRepo()
    service = SubscriptionService(billing_repo=repo)

    event_data = {
        "object": {
            "customer": "cus_pro_1",
            "id": "in_test_456",
            "amount_due": 1000,
            # no currency field
            # no invoice_pdf field
        }
    }

    result = await service._handle_payment_failed(event_data, repo)  # type: ignore[attr-defined]

    assert result["handled"] is True

    assert repo.last_payment is not None
    assert repo.last_payment["currency"] == "usd"
    assert repo.last_payment["invoice_pdf_url"] is None
