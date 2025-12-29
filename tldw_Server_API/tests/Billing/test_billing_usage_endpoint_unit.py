"""
Unit tests for the billing usage endpoint wiring.

These tests verify that:
- The /billing/usage handler maps UsageSummary fields to the
  current_usage dict passed into SubscriptionService.check_usage.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import pytest
from unittest.mock import AsyncMock

from tldw_Server_API.app.api.v1.endpoints import billing as billing_endpoint
from tldw_Server_API.app.core.Billing import enforcement as enforcement_module
from tldw_Server_API.app.core.Billing.enforcement import UsageSummary
from tldw_Server_API.app.core.Billing.subscription_service import SubscriptionStatus
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


class _FakeUsageStatus:
    def __init__(self, *, org_id: int, plan_name: str, limits: Dict[str, Any], usage: Dict[str, int]) -> None:
        self.org_id = org_id
        self.plan_name = plan_name
        self.limits = limits
        self.usage = usage
        self.limit_checks: Dict[str, Dict[str, Any]] = {}
        self.has_warnings = False
        self.has_exceeded = False


class _FakeSubscriptionService:
    def __init__(self) -> None:
        self.check_usage = AsyncMock()


class _FakeEnforcer:
    def __init__(self, summary: UsageSummary) -> None:
        self._summary = summary
        self.get_org_usage = AsyncMock(return_value=summary)
        self.get_org_limits = AsyncMock(return_value={})


@pytest.mark.asyncio
async def test_get_rag_usage_debug_uses_enforcer(monkeypatch) -> None:
    """get_rag_usage_debug should use BillingEnforcer to report RAG usage."""

    fake_principal = AuthPrincipal(kind="user", user_id=999)

    async def _fake_resolve_org_id(principal: AuthPrincipal, org_id: Optional[int]) -> int:
        assert principal is fake_principal
        return 77

    monkeypatch.setattr(
        billing_endpoint,
        "_resolve_org_id",
        _fake_resolve_org_id,
        raising=False,
    )

    # Simulate owner membership so the endpoint authorizes.
    async def _fake_membership(user_id: int, org_id: int) -> Dict[str, Any]:
        assert user_id == fake_principal.user_id
        assert org_id == 77
        return {"role": "owner", "status": "active"}

    monkeypatch.setattr(
        billing_endpoint,
        "_get_user_org_membership",
        _fake_membership,
        raising=False,
    )

    # Prepare a UsageSummary with a non-zero RAG count and matching limits.
    summary = UsageSummary(
        org_id=77,
        api_calls_today=0,
        llm_tokens_month=0,
        storage_bytes=0,
        team_members=0,
        transcription_minutes_month=0,
        rag_queries_today=5,
        concurrent_jobs=0,
    )

    class _FakeEnforcerForRag:
        def __init__(self) -> None:
            self.get_org_usage = AsyncMock(return_value=summary)
            self.get_org_limits = AsyncMock(return_value={"rag_queries_day": 100})

    fake_enforcer = _FakeEnforcerForRag()

    monkeypatch.setattr(
        billing_endpoint,
        "get_billing_enforcer",
        lambda: fake_enforcer,
        raising=False,
    )

    response = await billing_endpoint.get_rag_usage_debug(org_id=None, principal=fake_principal)

    assert response.org_id == 77
    assert response.rag_queries_today == 5
    assert response.rag_queries_day_limit == 100


@pytest.mark.asyncio
async def test_get_usage_maps_usage_summary_to_current_usage(monkeypatch) -> None:
    """get_usage should map UsageSummary to current_usage (including storage GB conversion)."""

    # Prepare a fake UsageSummary with non-trivial values.
    storage_bytes = 5 * (1024**3) + 1234  # 5 GB plus a bit of extra
    summary = UsageSummary(
        org_id=42,
        api_calls_today=10,
        llm_tokens_month=2000,
        storage_bytes=storage_bytes,
        team_members=3,
        transcription_minutes_month=0,
        rag_queries_today=0,
        concurrent_jobs=0,
    )

    fake_enforcer = _FakeEnforcer(summary)
    fake_service = _FakeSubscriptionService()

    # When the endpoint calls check_usage, return a simple UsageStatus-like object.
    fake_limits = {"api_calls_day": 100, "llm_tokens_month": 10_000, "storage_mb": 10_240, "team_members": 5}
    fake_service.check_usage.return_value = _FakeUsageStatus(
        org_id=42,
        plan_name="pro",
        limits=fake_limits,
        usage={},
    )

    # Patch the singleton getters the endpoint imports.
    async def _fake_get_subscription_service() -> _FakeSubscriptionService:
        return fake_service

    monkeypatch.setattr(
        billing_endpoint,
        "get_subscription_service",
        _fake_get_subscription_service,
        raising=False,
    )

    monkeypatch.setattr(
        billing_endpoint,
        "get_billing_enforcer",
        lambda: fake_enforcer,
        raising=False,
    )

    # Call the endpoint function directly.
    response = await billing_endpoint.get_usage(org_id=42)

    # Verify the mapping to current_usage passed into check_usage.
    assert fake_service.check_usage.call_count == 1
    args, kwargs = fake_service.check_usage.call_args
    # org_id is the first positional argument
    assert args[0] == 42
    current_usage = kwargs["current_usage"]

    assert current_usage["api_calls_day"] == summary.api_calls_today
    assert current_usage["llm_tokens_month"] == summary.llm_tokens_month
    # storage_bytes should be converted to whole MB via integer division.
    assert current_usage["storage_mb"] == 5120
    assert current_usage["team_members"] == summary.team_members

    # Response should mirror the UsageStatus returned by the service.
    assert response.org_id == 42
    assert response.plan_name == "pro"
    assert response.limits == fake_limits


@pytest.mark.asyncio
async def test_get_usage_propagates_limit_flags_and_checks(monkeypatch) -> None:
    """get_usage should propagate has_warnings/has_exceeded and limit_checks from the service."""

    summary = UsageSummary(
        org_id=99,
        api_calls_today=0,
        llm_tokens_month=0,
        storage_bytes=0,
        team_members=0,
        transcription_minutes_month=0,
        rag_queries_today=0,
        concurrent_jobs=0,
    )

    fake_enforcer = _FakeEnforcer(summary)

    monkeypatch.setattr(
        billing_endpoint,
        "get_billing_enforcer",
        lambda: fake_enforcer,
        raising=False,
    )

    fake_service = _FakeSubscriptionService()

    fake_limits = {"api_calls_day": 100}
    fake_limit_checks = {
        "api_calls_day": {"limit_name": "api_calls_day", "current": 80, "limit": 100, "warning": True, "exceeded": False}
    }

    usage_status = _FakeUsageStatus(
        org_id=99,
        plan_name="pro",
        limits=fake_limits,
        usage={"api_calls_day": 80},
    )
    usage_status.limit_checks = fake_limit_checks
    usage_status.has_warnings = True
    usage_status.has_exceeded = True

    fake_service.check_usage.return_value = usage_status

    async def _fake_get_subscription_service() -> _FakeSubscriptionService:
        return fake_service

    monkeypatch.setattr(
        billing_endpoint,
        "get_subscription_service",
        _fake_get_subscription_service,
        raising=False,
    )

    response = await billing_endpoint.get_usage(org_id=99)

    assert response.has_warnings is True
    assert response.has_exceeded is True
    assert response.limit_checks == fake_limit_checks


@pytest.mark.asyncio
async def test_get_subscription_positive_path(monkeypatch) -> None:
    """get_subscription should return subscription data from the service."""

    status = SubscriptionStatus(
        org_id=123,
        plan_name="pro",
        plan_display_name="Pro",
        status="active",
        billing_cycle="monthly",
        current_period_end="2025-12-31T00:00:00Z",
        trial_end=None,
        cancel_at_period_end=False,
        limits={"api_calls_day": 100},
    )

    class _FakeSubscriptionServiceForSub:
        def __init__(self, subscription_status: SubscriptionStatus) -> None:
            self.subscription_status = subscription_status
            self.get_subscription = AsyncMock(return_value=subscription_status)

    fake_service = _FakeSubscriptionServiceForSub(status)

    async def _fake_get_subscription_service() -> _FakeSubscriptionServiceForSub:
        return fake_service

    monkeypatch.setattr(
        billing_endpoint,
        "get_subscription_service",
        _fake_get_subscription_service,
        raising=False,
    )

    response = await billing_endpoint.get_subscription(org_id=123)

    assert response.org_id == 123
    assert response.plan_name == "pro"
    assert response.plan_display_name == "Pro"
    assert response.status == "active"
    assert response.billing_cycle == "monthly"
    assert response.current_period_end == "2025-12-31T00:00:00Z"
    assert response.trial_end is None
    assert response.cancel_at_period_end is False
    assert response.limits == {"api_calls_day": 100}
