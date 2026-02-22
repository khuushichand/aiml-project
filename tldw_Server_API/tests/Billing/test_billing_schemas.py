"""
Unit tests for billing response schemas.
"""
from __future__ import annotations

from tldw_Server_API.app.api.v1.schemas.billing_schemas import InvoiceResponse


def test_invoice_amount_display_formats_usd_with_symbol() -> None:
    invoice = InvoiceResponse(
        id=1,
        org_id=10,
        amount_cents=1234,
        currency="usd",
        status="succeeded",
    )
    assert invoice.amount_display == "$12.34"


def test_invoice_amount_display_formats_non_usd_without_dollar_prefix() -> None:
    invoice = InvoiceResponse(
        id=2,
        org_id=10,
        amount_cents=5678,
        currency="eur",
        status="succeeded",
    )
    assert invoice.amount_display == "EUR 56.78"
