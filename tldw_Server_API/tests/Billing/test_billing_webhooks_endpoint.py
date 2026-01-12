"""
Unit tests for the /billing/webhooks/stripe endpoint wiring.

These tests verify:
- 400 response on invalid signatures/payloads (ValueError from StripeClient)
- 200 response on valid events with minimal mocking
"""
from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.billing_webhooks import router as webhooks_router


class _FakeStripeClientForWebhooks:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.is_available = True

    def construct_webhook_event(self, payload: Any, signature: str) -> Dict[str, Any]:
        if self.should_fail:
            raise ValueError("Invalid webhook signature")
        return {"id": "evt_test_123", "type": "test.event", "data": {}}


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    app.include_router(webhooks_router, prefix="/api/v1")
    return app


@pytest.mark.parametrize("should_fail,expected_status", [(True, 400), (False, 200)])
def test_stripe_webhook_signature_handling(monkeypatch, app: FastAPI, should_fail: bool, expected_status: int) -> None:
    """Stripe webhook endpoint should return 400 on invalid signature and 200 on success."""

    # Billing must be enabled for the endpoint to process requests.
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.is_billing_enabled",
        lambda: True,
        raising=False,
    )

    # Patch Stripe client factory to return our fake implementation.
    fake_client = _FakeStripeClientForWebhooks(should_fail=should_fail)

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_stripe_client",
        lambda: fake_client,
        raising=False,
    )

    # Avoid touching the real database or subscription service.
    class _FakeBillingRepo:
        async def record_webhook_event(self, *args, **kwargs):
            return True

        async def try_claim_webhook_event(self, *args, **kwargs):
            return True

        async def mark_webhook_processed(self, *args, **kwargs):
            return None

    async def _fake_get_db_pool():
        class _Pool:
            async def acquire(self):
                return None

            async def transaction(self):
                class _Tx:
                    async def __aenter__(self_inner):
                        return None

                    async def __aexit__(self_inner, exc_type, exc, tb):
                        return False

                return _Tx()

        return _Pool()

    async def _fake_get_subscription_service():
        class _Service:
            async def handle_webhook_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
                return {"handled": True}

        return _Service()

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_db_pool",
        _fake_get_db_pool,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.AuthnzBillingRepo",
        lambda db_pool: _FakeBillingRepo(),
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_subscription_service",
        _fake_get_subscription_service,
        raising=False,
    )

    client = TestClient(app)

    response = client.post(
        "/api/v1/billing/webhooks/stripe",
        data=b"{}",
        headers={"Stripe-Signature": "sig_test"},
    )

    assert response.status_code == expected_status


def test_stripe_webhook_retries_failed_event(monkeypatch, app: FastAPI) -> None:
    """Existing failed events should be re-claimable for manual retry."""

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.is_billing_enabled",
        lambda: True,
        raising=False,
    )

    fake_client = _FakeStripeClientForWebhooks(should_fail=False)
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_stripe_client",
        lambda: fake_client,
        raising=False,
    )

    class _RetryingBillingRepo:
        def __init__(self):
            self.processed = False

        async def record_webhook_event(self, *args, **kwargs):
            return False

        async def get_webhook_event_status(self, *args, **kwargs):
            return "failed"

        async def try_claim_webhook_event(self, *args, **kwargs):
            return True

        async def mark_webhook_processed(self, *args, **kwargs):
            self.processed = True

    async def _fake_get_db_pool():
        class _Pool:
            async def acquire(self):
                return None

            async def transaction(self):
                class _Tx:
                    async def __aenter__(self_inner):
                        return None

                    async def __aexit__(self_inner, exc_type, exc, tb):
                        return False

                return _Tx()

        return _Pool()

    async def _fake_get_subscription_service():
        class _Service:
            async def handle_webhook_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
                return {"handled": True}

        return _Service()

    retry_repo = _RetryingBillingRepo()

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_db_pool",
        _fake_get_db_pool,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.AuthnzBillingRepo",
        lambda db_pool: retry_repo,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_subscription_service",
        _fake_get_subscription_service,
        raising=False,
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/billing/webhooks/stripe",
        data=b"{}",
        headers={"Stripe-Signature": "sig_test"},
    )

    assert response.status_code == 200
    assert retry_repo.processed is True


def test_stripe_webhook_processing_failure_returns_500(monkeypatch, app: FastAPI) -> None:
    """Webhook processing errors should surface as 500 so Stripe retries."""

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.is_billing_enabled",
        lambda: True,
        raising=False,
    )

    fake_client = _FakeStripeClientForWebhooks(should_fail=False)
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_stripe_client",
        lambda: fake_client,
        raising=False,
    )

    class _FailingBillingRepo:
        def __init__(self):
            self.failed = False

        async def record_webhook_event(self, *args, **kwargs):
            return True

        async def try_claim_webhook_event(self, *args, **kwargs):
            return True

        async def mark_webhook_processed(self, *args, **kwargs):
            self.failed = True

    async def _fake_get_db_pool():
        class _Pool:
            async def acquire(self):
                return None

            async def transaction(self):
                class _Tx:
                    async def __aenter__(self_inner):
                        return None

                    async def __aexit__(self_inner, exc_type, exc, tb):
                        return False

                return _Tx()

        return _Pool()

    async def _fake_get_subscription_service():
        class _Service:
            async def handle_webhook_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
                raise RuntimeError("boom")

        return _Service()

    failing_repo = _FailingBillingRepo()

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_db_pool",
        _fake_get_db_pool,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.AuthnzBillingRepo",
        lambda db_pool: failing_repo,
        raising=False,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.get_subscription_service",
        _fake_get_subscription_service,
        raising=False,
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/billing/webhooks/stripe",
        data=b"{}",
        headers={"Stripe-Signature": "sig_test"},
    )

    assert response.status_code == 500
    assert failing_repo.failed is True
