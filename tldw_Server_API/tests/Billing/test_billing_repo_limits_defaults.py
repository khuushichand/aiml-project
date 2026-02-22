"""
Unit tests for billing repo limit merging.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.billing_repo import AuthnzBillingRepo


@pytest.mark.asyncio
async def test_get_org_limits_merges_defaults(monkeypatch) -> None:
    """Missing limit categories should be filled from default plan limits."""
    repo = AuthnzBillingRepo(db_pool=MagicMock())

    async def _fake_get_org_subscription(org_id: int):
        return {
            "plan_name": "pro",
            "effective_limits": {
                "api_calls_day": 10,
            },
        }

    monkeypatch.setattr(repo, "get_org_subscription", _fake_get_org_subscription, raising=False)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.billing_repo.get_plan_limits",
        lambda plan_name: {"api_calls_day": 100, "rag_queries_day": 500},
        raising=False,
    )

    limits = await repo.get_org_limits(1)

    assert limits["api_calls_day"] == 10
    assert limits["rag_queries_day"] == 500


@pytest.mark.asyncio
async def test_get_org_limits_without_subscription_merges_free_defaults(monkeypatch) -> None:
    """No-subscription path should still include canonical free-tier limit categories."""
    repo = AuthnzBillingRepo(db_pool=MagicMock())

    async def _fake_get_org_subscription(org_id: int):
        return None

    async def _fake_get_plan_by_name(name: str):
        if name == "free":
            return {"name": "free", "limits": {"api_calls_day": 123}}
        return None

    monkeypatch.setattr(repo, "get_org_subscription", _fake_get_org_subscription, raising=False)
    monkeypatch.setattr(repo, "get_plan_by_name", _fake_get_plan_by_name, raising=False)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.billing_repo.get_plan_limits",
        lambda plan_name: {"api_calls_day": 100, "rag_queries_day": 500},
        raising=False,
    )

    limits = await repo.get_org_limits(1)

    assert limits["api_calls_day"] == 123
    assert limits["rag_queries_day"] == 500


@pytest.mark.asyncio
async def test_get_org_limits_non_active_status_falls_back_to_free(monkeypatch) -> None:
    """Non-active subscription statuses should not retain paid/effective limits."""

    repo = AuthnzBillingRepo(db_pool=MagicMock())

    async def _fake_get_org_subscription(org_id: int):
        return {
            "plan_name": "pro",
            "status": "past_due",
            "effective_limits": {
                "api_calls_day": 9999,
                "rag_queries_day": 9999,
            },
        }

    async def _fake_get_plan_by_name(name: str):
        if name == "free":
            return {"name": "free", "limits": {"api_calls_day": 123}}
        return None

    def _fake_get_plan_limits(plan_name: str):
        if plan_name == "free":
            return {"api_calls_day": 100, "rag_queries_day": 50}
        if plan_name == "pro":
            return {"api_calls_day": 5000, "rag_queries_day": 500}
        return {}

    monkeypatch.setattr(repo, "get_org_subscription", _fake_get_org_subscription, raising=False)
    monkeypatch.setattr(repo, "get_plan_by_name", _fake_get_plan_by_name, raising=False)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.AuthNZ.repos.billing_repo.get_plan_limits",
        _fake_get_plan_limits,
        raising=False,
    )

    limits = await repo.get_org_limits(1)

    assert limits["api_calls_day"] == 123
    assert limits["rag_queries_day"] == 50
