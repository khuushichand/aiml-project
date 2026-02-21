"""
Integration tests for the billing webhooks endpoint with a real Postgres DB.

These tests verify that:
- Webhook events are persisted in stripe_webhook_events
- Events are marked processed
- Idempotency prevents double-processing of the same event
"""
from __future__ import annotations

from typing import Any, Dict

import asyncpg
import pytest
import pytest_asyncio

from tldw_Server_API.tests.helpers.pg_env import get_pg_env

# Reuse Postgres AuthNZ fixtures
pytest_plugins = ["tldw_Server_API.tests.AuthNZ.conftest"]

_pg = get_pg_env()
TEST_DB_HOST = _pg.host
TEST_DB_PORT = _pg.port
TEST_DB_USER = _pg.user
TEST_DB_PASSWORD = _pg.password


def _has_postgres_dependencies() -> bool:


    """Check if PostgreSQL dependencies are available."""
    try:
        import psycopg  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
class TestBillingWebhooksIntegration:
    """Integration tests for /api/v1/billing/webhooks/stripe."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, isolated_test_environment, monkeypatch):
        """Setup test client and enable billing."""
        client, db_name = isolated_test_environment
        self.db_name = db_name

        # Ensure the billing webhooks router is mounted for this test,
        # regardless of route gating configuration in the main app.
        from tldw_Server_API.app.api.v1.endpoints.billing_webhooks import router as billing_webhooks_router

        app = getattr(client, "app", None)
        if app is not None:
            try:
                existing_paths = {getattr(r, "path", "") for r in app.routes}
                if "/api/v1/billing/webhooks/stripe" not in existing_paths:
                    app.include_router(billing_webhooks_router, prefix="/api/v1")
            except Exception:
                # If inspection fails, still fall back to the original client.
                _ = None

        self.client = client

        # Ensure billing is considered enabled for these tests.
        monkeypatch.setattr(
            "tldw_Server_API.app.api.v1.endpoints.billing_webhooks.is_billing_enabled",
            lambda: True,
            raising=False,
        )

    @pytest.mark.asyncio
    async def test_webhook_happy_path_persists_event_and_marks_processed(self, monkeypatch) -> None:
        """Webhook should persist event and mark it processed."""

        from tldw_Server_API.app.api.v1.endpoints import billing_webhooks

        event_id = "evt_int_1"

        class _FakeStripeClient:
            def __init__(self) -> None:
                self.is_available = True

            def construct_webhook_event(self, payload: Any, signature: str) -> Dict[str, Any]:
                return {
                    "id": event_id,
                    "type": "customer.subscription.updated",
                    "data": {"object": {"dummy": True}},
                }

        class _FakeSubscriptionService:
            def __init__(self) -> None:
                self.call_count = 0

            async def handle_webhook_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
                self.call_count += 1
                return {"handled": True}

        fake_client = _FakeStripeClient()
        fake_service = _FakeSubscriptionService()

        async def _fake_get_subscription_service() -> _FakeSubscriptionService:
            return fake_service

        monkeypatch.setattr(
            billing_webhooks,
            "get_stripe_client",
            lambda: fake_client,
            raising=False,
        )
        monkeypatch.setattr(
            billing_webhooks,
            "get_subscription_service",
            _fake_get_subscription_service,
            raising=False,
        )

        # First delivery: should process and persist the event.
        response = self.client.post(
            "/api/v1/billing/webhooks/stripe",
            data=b"{}",
            headers={"Stripe-Signature": "sig_test"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["received"] is True
        assert body["handled"] is True
        assert fake_service.call_count == 1

        # Verify DB state.
        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=self.db_name,
        )
        try:
            row = await conn.fetchrow(
                "SELECT stripe_event_id, status FROM stripe_webhook_events WHERE stripe_event_id = $1",
                event_id,
            )
            assert row is not None
            assert row["stripe_event_id"] == event_id
            assert row["status"] == "processed"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_webhook_is_idempotent(self, monkeypatch) -> None:
        """Same event should be processed only once."""

        from tldw_Server_API.app.api.v1.endpoints import billing_webhooks

        event_id = "evt_int_idempotent"

        class _FakeStripeClient:
            def __init__(self) -> None:
                self.is_available = True

            def construct_webhook_event(self, payload: Any, signature: str) -> Dict[str, Any]:
                return {
                    "id": event_id,
                    "type": "customer.subscription.updated",
                    "data": {"object": {"dummy": True}},
                }

        class _FakeSubscriptionService:
            def __init__(self) -> None:
                self.call_count = 0

            async def handle_webhook_event(self, event_type: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
                self.call_count += 1
                return {"handled": True}

        fake_client = _FakeStripeClient()
        fake_service = _FakeSubscriptionService()

        async def _fake_get_subscription_service() -> _FakeSubscriptionService:
            return fake_service

        monkeypatch.setattr(
            billing_webhooks,
            "get_stripe_client",
            lambda: fake_client,
            raising=False,
        )
        monkeypatch.setattr(
            billing_webhooks,
            "get_subscription_service",
            _fake_get_subscription_service,
            raising=False,
        )

        # First delivery: should process normally.
        resp1 = self.client.post(
            "/api/v1/billing/webhooks/stripe",
            data=b"{}",
            headers={"Stripe-Signature": "sig_test"},
        )
        assert resp1.status_code == 200
        assert fake_service.call_count == 1

        # Second delivery of the same event should be idempotent and not call the service again.
        resp2 = self.client.post(
            "/api/v1/billing/webhooks/stripe",
            data=b"{}",
            headers={"Stripe-Signature": "sig_test"},
        )
        assert resp2.status_code == 200
        assert fake_service.call_count == 1
