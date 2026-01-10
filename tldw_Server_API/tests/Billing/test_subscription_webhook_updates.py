"""
Unit tests for subscription webhook update handling.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.Billing.subscription_service import SubscriptionService


class _FakeBillingRepo:
    def __init__(self) -> None:
             self.updated: dict | None = None

    async def get_subscription_by_stripe_customer(self, customer_id: str):
        return {"org_id": 123}

    async def get_plan_by_stripe_price_id(self, price_id: str):
        return None

    async def get_plan_by_stripe_product_id(self, product_id: str):
        return None

    async def update_org_subscription(self, org_id: int, **updates):
        self.updated = {"org_id": org_id, **updates}


@pytest.mark.asyncio
async def test_handle_subscription_updated_syncs_status_and_utc_timestamps() -> None:
    service = SubscriptionService()
    repo = _FakeBillingRepo()

    start_ts = 1_700_000_000
    end_ts = 1_700_003_600

    event_data = {
        "object": {
            "customer": "cus_test",
            "status": "past_due",
            "current_period_start": start_ts,
            "current_period_end": end_ts,
            "items": {"data": []},
        }
    }

    result = await service._handle_subscription_updated(event_data, repo)

    assert result["handled"] is True
    assert repo.updated is not None
    assert repo.updated["org_id"] == 123
    assert repo.updated["status"] == "past_due"
    assert repo.updated["stripe_subscription_status"] == "past_due"
    assert repo.updated["current_period_start"] == datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()
    assert repo.updated["current_period_end"] == datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat()
