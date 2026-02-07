"""
billing_schemas.py

Pydantic schemas for billing and subscription endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, computed_field

# =============================================================================
# Plans
# =============================================================================

class PlanLimitsResponse(BaseModel):
    """Plan limits details."""
    storage_mb: int | None = None
    api_calls_day: int | None = None
    llm_tokens_month: int | None = None
    team_members: int | None = None
    transcription_minutes_month: int | None = None
    rag_queries_day: int | None = None
    concurrent_jobs: int | None = None
    advanced_analytics: bool | None = None
    priority_support: bool | None = None
    custom_models: bool | None = None
    api_access: bool | None = None
    sso_enabled: bool | None = None
    audit_logs: bool | None = None


class SubscriptionPlanResponse(BaseModel):
    """Subscription plan details."""
    id: int | None = None
    name: str
    display_name: str
    description: str | None = None
    price_usd_monthly: float = 0
    price_usd_yearly: float = 0
    limits: PlanLimitsResponse = Field(default_factory=PlanLimitsResponse)
    is_active: bool = True
    is_public: bool = True


class PlanListResponse(BaseModel):
    """List of available plans."""
    plans: list[SubscriptionPlanResponse]


# =============================================================================
# Subscriptions
# =============================================================================

class OrgSubscriptionResponse(BaseModel):
    """Organization subscription status."""
    org_id: int
    plan_name: str
    plan_display_name: str
    status: str  # active, past_due, canceled, trialing, canceling
    billing_cycle: str | None = None  # monthly, yearly
    current_period_end: str | None = None
    trial_end: str | None = None
    cancel_at_period_end: bool = False
    limits: dict[str, Any] = Field(default_factory=dict)


class SubscriptionUsageResponse(BaseModel):
    """Usage vs limits status."""
    org_id: int
    plan_name: str
    limits: dict[str, Any]
    usage: dict[str, int]
    limit_checks: dict[str, dict[str, Any]]
    has_warnings: bool
    has_exceeded: bool


class RagUsageDebugResponse(BaseModel):
    """Debug view of RAG query usage vs daily limit."""
    org_id: int
    rag_queries_today: int
    rag_queries_day_limit: int | None = None


# =============================================================================
# Checkout & Portal
# =============================================================================

class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""
    plan_name: str = Field(
        ...,
        min_length=1,
        description="Plan to subscribe to (must match a subscription_plans entry)",
    )
    billing_cycle: str = Field("monthly", pattern=r"^(monthly|yearly)$", description="Billing frequency")
    success_url: HttpUrl = Field(..., description="URL to redirect to after successful checkout")
    cancel_url: HttpUrl = Field(..., description="URL to redirect to if checkout is cancelled")


class CheckoutResponse(BaseModel):
    """Checkout session result."""
    session_id: str
    url: str


class PortalRequest(BaseModel):
    """Request to create a billing portal session."""
    return_url: HttpUrl = Field(..., description="URL to redirect to after leaving the portal")


class PortalResponse(BaseModel):
    """Billing portal session result."""
    session_id: str
    url: str


# =============================================================================
# Subscription Management
# =============================================================================

class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription."""
    at_period_end: bool = Field(
        True,
        description="If true, cancel at end of current billing period. If false, cancel immediately.",
    )


class CancelSubscriptionResponse(BaseModel):
    """Cancellation result."""
    canceled: bool
    current_period_end: str | None = None


class ResumeSubscriptionResponse(BaseModel):
    """Resume result."""
    resumed: bool


# =============================================================================
# Invoices
# =============================================================================

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
        return f"${self.amount_cents / 100:.2f} {self.currency.upper()}"


class InvoiceListResponse(BaseModel):
    """List of invoices."""
    items: list[InvoiceResponse]
    total: int


# =============================================================================
# Webhooks
# =============================================================================

class WebhookResponse(BaseModel):
    """Webhook processing result."""
    received: bool = True
    event_type: str | None = None
    handled: bool = False
