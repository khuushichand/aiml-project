"""
billing_schemas.py

Pydantic schemas for billing and subscription endpoints.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, HttpUrl


# =============================================================================
# Plans
# =============================================================================

class PlanLimitsResponse(BaseModel):
    """Plan limits details."""
    storage_mb: Optional[int] = None
    api_calls_day: Optional[int] = None
    llm_tokens_month: Optional[int] = None
    team_members: Optional[int] = None
    transcription_minutes_month: Optional[int] = None
    rag_queries_day: Optional[int] = None
    concurrent_jobs: Optional[int] = None
    advanced_analytics: Optional[bool] = None
    priority_support: Optional[bool] = None
    custom_models: Optional[bool] = None
    api_access: Optional[bool] = None
    sso_enabled: Optional[bool] = None
    audit_logs: Optional[bool] = None


class SubscriptionPlanResponse(BaseModel):
    """Subscription plan details."""
    id: Optional[int] = None
    name: str
    display_name: str
    description: Optional[str] = None
    price_usd_monthly: float = 0
    price_usd_yearly: float = 0
    limits: PlanLimitsResponse = Field(default_factory=PlanLimitsResponse)
    is_active: bool = True
    is_public: bool = True


class PlanListResponse(BaseModel):
    """List of available plans."""
    plans: List[SubscriptionPlanResponse]


# =============================================================================
# Subscriptions
# =============================================================================

class OrgSubscriptionResponse(BaseModel):
    """Organization subscription status."""
    org_id: int
    plan_name: str
    plan_display_name: str
    status: str  # active, past_due, canceled, trialing, canceling
    billing_cycle: Optional[str] = None  # monthly, yearly
    current_period_end: Optional[str] = None
    trial_end: Optional[str] = None
    cancel_at_period_end: bool = False
    limits: Dict[str, Any] = Field(default_factory=dict)


class SubscriptionUsageResponse(BaseModel):
    """Usage vs limits status."""
    org_id: int
    plan_name: str
    limits: Dict[str, Any]
    usage: Dict[str, int]
    limit_checks: Dict[str, Dict[str, Any]]
    has_warnings: bool
    has_exceeded: bool


class RagUsageDebugResponse(BaseModel):
    """Debug view of RAG query usage vs daily limit."""
    org_id: int
    rag_queries_today: int
    rag_queries_day_limit: Optional[int] = None


# =============================================================================
# Checkout & Portal
# =============================================================================

class CheckoutRequest(BaseModel):
    """Request to create a checkout session."""
    plan_name: str = Field(..., pattern=r"^(pro|enterprise)$", description="Plan to subscribe to (pro or enterprise)")
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
    current_period_end: Optional[str] = None


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
    stripe_invoice_id: Optional[str] = None
    amount_cents: int
    currency: str = "usd"
    status: str  # succeeded, failed, pending
    description: Optional[str] = None
    invoice_pdf_url: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def amount_display(self) -> str:
        """Format amount for display."""
        return f"${self.amount_cents / 100:.2f} {self.currency.upper()}"


class InvoiceListResponse(BaseModel):
    """List of invoices."""
    items: List[InvoiceResponse]
    total: int


# =============================================================================
# Webhooks
# =============================================================================

class WebhookResponse(BaseModel):
    """Webhook processing result."""
    received: bool = True
    event_type: Optional[str] = None
    handled: bool = False
