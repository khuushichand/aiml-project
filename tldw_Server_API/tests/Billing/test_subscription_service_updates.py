"""
Unit tests for subscription service billing updates.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.Billing.subscription_service import CheckoutSession, SubscriptionService


class _FakeStripeClient:
    def __init__(self) -> None:
        self.is_available = True
        self.last_price_id: str | None = None

    def get_price_id(self, plan_name: str, billing_cycle: str = "monthly") -> str | None:
        return None

    async def create_checkout_session(
        self,
        *,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str] | None = None,
    ) -> CheckoutSession:
        self.last_price_id = price_id
        return CheckoutSession(id="cs_test", url="https://example.test/checkout")

    async def create_customer(self, *, email: str, name: str | None = None, metadata: dict[str, str] | None = None) -> str:
        return "cus_test"


class _FakeBillingRepo:
    async def get_org_subscription(self, org_id: int):
        return {"stripe_customer_id": "cus_test"}

    async def get_plan_by_name(self, plan_name: str):
        return {
            "id": 1,
            "stripe_price_id": "price_month",
            "stripe_price_id_yearly": "price_year",
        }

    async def log_billing_action(self, **kwargs):
        return {}


@pytest.mark.asyncio
async def test_checkout_session_uses_yearly_price_from_db(monkeypatch) -> None:
    """Yearly checkouts should use stripe_price_id_yearly when config is missing."""
    from tldw_Server_API.app.core.Billing import subscription_service as subscription_module

    monkeypatch.setattr(subscription_module, "is_billing_enabled", lambda: True, raising=False)

    fake_repo = _FakeBillingRepo()
    fake_stripe = _FakeStripeClient()
    service = SubscriptionService(billing_repo=fake_repo, stripe_client=fake_stripe)

    session = await service.create_checkout_session(
        org_id=1,
        plan_name="pro",
        billing_cycle="yearly",
        success_url="https://example.test/success",
        cancel_url="https://example.test/cancel",
        org_email="billing@example.test",
        org_name="Example Org",
    )

    assert session.id == "cs_test"
    assert fake_stripe.last_price_id == "price_year"


class _FakeRepoForWebhook:
    def __init__(self) -> None:
        self.updated: dict[str, object] | None = None

    async def get_subscription_by_stripe_customer(self, customer_id: str):
        return {"org_id": 123}

    async def get_plan_by_stripe_price_id(self, price_id: str):
        return {"id": 77}

    async def get_plan_by_stripe_product_id(self, product_id: str):
        return None

    async def update_org_subscription(self, org_id: int, **updates):
        self.updated = updates
        return {}


@pytest.mark.asyncio
async def test_subscription_updated_persists_cycle_trial_and_cancel() -> None:
    """Webhook updates should persist billing_cycle, trial_end, and cancel_at_period_end."""
    repo = _FakeRepoForWebhook()
    service = SubscriptionService(billing_repo=repo)

    event_data = {
        "object": {
            "customer": "cus_test",
            "status": "active",
            "current_period_start": 100,
            "current_period_end": 200,
            "trial_end": 300,
            "cancel_at_period_end": True,
            "items": {
                "data": [
                    {
                        "price": {
                            "id": "price_year",
                            "product": "prod_1",
                            "recurring": {"interval": "year"},
                        }
                    }
                ]
            },
        }
    }

    await service._handle_subscription_updated(event_data, repo)

    assert repo.updated is not None
    assert repo.updated.get("plan_id") == 77
    assert repo.updated.get("billing_cycle") == "yearly"
    assert repo.updated.get("cancel_at_period_end") is True
    assert repo.updated.get("status") == "active"
    assert repo.updated.get("stripe_subscription_status") == "active"
    assert repo.updated.get("trial_end") == datetime.fromtimestamp(300, tz=timezone.utc).isoformat()
    assert repo.updated.get("current_period_start") == datetime.fromtimestamp(100, tz=timezone.utc).isoformat()
    assert repo.updated.get("current_period_end") == datetime.fromtimestamp(200, tz=timezone.utc).isoformat()
