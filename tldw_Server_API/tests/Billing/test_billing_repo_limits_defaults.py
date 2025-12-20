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
