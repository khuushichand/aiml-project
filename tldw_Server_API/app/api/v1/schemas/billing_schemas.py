"""
billing_schemas.py

Historical billing data schemas retained for non-public/internal usage.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, computed_field

class InvoiceResponse(BaseModel):
    """Invoice/payment record."""
    id: int
    org_id: int
    stripe_invoice_id: str | None = None
    amount_cents: int
    currency: str = "usd"
    status: str  # succeeded, failed, pending
    description: str | None = None
    invoice_pdf_url: str | None = None
    created_at: datetime | None = None

    @computed_field
    @property
    def amount_display(self) -> str:
        """Format amount for display."""
        currency = (self.currency or "usd").lower()
        amount = self.amount_cents / 100
        symbols = {
            "usd": "$",
            "eur": "EUR ",
            "gbp": "GBP ",
            "jpy": "JPY ",
        }
        prefix = symbols.get(currency, f"{currency.upper()} ")
        return f"{prefix}{amount:.2f}"


class InvoiceListResponse(BaseModel):
    """List of invoices."""
    items: list[InvoiceResponse]
    total: int
