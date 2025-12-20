"""
Unit tests for StripeClient webhook handling.

These tests focus on:
- Accepting both bytes and string payloads for construct_webhook_event
- Properly converting Stripe SignatureVerificationError into ValueError
"""
from __future__ import annotations

from typing import Any

import pytest
from unittest.mock import MagicMock, patch

from tldw_Server_API.app.core.Billing import stripe_client as stripe_client_module
from tldw_Server_API.app.core.Billing.stripe_client import StripeClient, StripeConfig


class _FakeStripeModule:
    class error:
        class SignatureVerificationError(Exception):
            pass

    class Webhook:
        @staticmethod
        def construct_event(payload: str, signature: str, secret: str) -> dict[str, Any]:
            return {"id": "evt_123", "type": "test.event", "data": {"payload": payload}}


@pytest.mark.parametrize("payload", [b'{"test": true}', '{"test": true}'])
def test_construct_webhook_event_accepts_bytes_and_str(monkeypatch, payload: Any) -> None:
    """construct_webhook_event should accept both bytes and str payloads and decode bytes as UTF-8."""

    # Patch stripe module used inside StripeClient
    monkeypatch.setattr(stripe_client_module, "stripe", _FakeStripeModule, raising=False)
    monkeypatch.setattr(stripe_client_module, "STRIPE_AVAILABLE", True, raising=False)

    config = StripeConfig(api_key="sk_test_123", webhook_secret="whsec_test")
    client = StripeClient(config=config)

    event = client.construct_webhook_event(payload, "sig_test")
    assert event["id"] == "evt_123"
    assert event["type"] == "test.event"


def test_construct_webhook_event_converts_signature_error_to_value_error(monkeypatch) -> None:
    """SignatureVerificationError from stripe should surface as ValueError."""

    class _FailingWebhook:
        @staticmethod
        def construct_event(payload: str, signature: str, secret: str) -> dict[str, Any]:
            raise _FakeStripeModule.error.SignatureVerificationError("bad sig")

    fake_stripe = _FakeStripeModule
    fake_stripe.Webhook = _FailingWebhook  # type: ignore[assignment]

    monkeypatch.setattr(stripe_client_module, "stripe", fake_stripe, raising=False)
    monkeypatch.setattr(stripe_client_module, "STRIPE_AVAILABLE", True, raising=False)

    config = StripeConfig(api_key="sk_test_123", webhook_secret="whsec_test")
    client = StripeClient(config=config)

    with pytest.raises(ValueError) as exc_info:
        client.construct_webhook_event(b"{}", "sig_bad")

    assert "Invalid webhook signature" in str(exc_info.value)
