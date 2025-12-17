"""
Focused tests for the LimitEnforcer context manager wiring.

These tests verify that:
- The API-layer LimitEnforcer delegates actual usage deltas to BillingEnforcer.
- LLM token and API call usage are mirrored into the cost-units ledger via
  record_cost_units_for_entity with the expected token/request fields.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tldw_Server_API.app.core.Billing.enforcement import (
    EnforcementAction,
    LimitCategory,
    LimitCheckResult,
)
from tldw_Server_API.app.api.v1.API_Deps.billing_deps import (
    LimitEnforcer as APILimitEnforcer,
)


@pytest.mark.asyncio
async def test_limit_enforcer_applies_usage_delta_on_success(monkeypatch):
    """LimitEnforcer should apply usage delta when operation succeeds."""
    mock_enforcer = MagicMock()

    mock_enforcer.check_limit = AsyncMock(
        return_value=LimitCheckResult(
            category=LimitCategory.LLM_TOKENS_MONTH.value,
            action=EnforcementAction.ALLOW,
            current=1000,
            limit=10_000,
            percent_used=10.0,
        )
    )
    mock_enforcer.apply_usage_delta = MagicMock()

    # Ensure the API deps LimitEnforcer uses our mock enforcer and has enforcement enabled
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.API_Deps.billing_deps.get_billing_enforcer",
        lambda: mock_enforcer,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.API_Deps.billing_deps.enforcement_enabled",
        lambda: True,
    )

    async with APILimitEnforcer(
        org_id=1,
        category=LimitCategory.LLM_TOKENS_MONTH,
        estimated_units=1000,
    ) as ctx:
        ctx.record_actual(1200)

    mock_enforcer.apply_usage_delta.assert_called_once_with(
        1,
        LimitCategory.LLM_TOKENS_MONTH,
        1200,
    )


@pytest.mark.asyncio
async def test_limit_enforcer_records_cost_units_for_llm_tokens(monkeypatch):
    """LimitEnforcer should record LLM tokens into org cost-units ledger."""
    mock_enforcer = MagicMock()
    mock_enforcer.check_limit = AsyncMock(
        return_value=LimitCheckResult(
            category=LimitCategory.LLM_TOKENS_MONTH.value,
            action=EnforcementAction.ALLOW,
            current=0,
            limit=-1,
            percent_used=0,
            unlimited=True,
        )
    )
    mock_enforcer.apply_usage_delta = MagicMock()

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.API_Deps.billing_deps.get_billing_enforcer",
        lambda: mock_enforcer,
    )
    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.API_Deps.billing_deps.enforcement_enabled",
        lambda: True,
    )

    from tldw_Server_API.app.core.Resource_Governance import cost_units as cost_units_mod

    cost_units_calls: list[dict] = []

    async def fake_record_cost_units_for_entity(
        *,
        entity_scope,
        entity_value,
        tokens,
        minutes,
        requests,
        op_id=None,
        occurred_at=None,
    ):
        cost_units_calls.append(
            {
                "entity_scope": entity_scope,
                "entity_value": entity_value,
                "tokens": tokens,
                "minutes": minutes,
                "requests": requests,
            }
        )
        return 1

    monkeypatch.setattr(
        cost_units_mod,
        "record_cost_units_for_entity",
        fake_record_cost_units_for_entity,
    )

    org_id = 99
    actual_tokens = 4321

    async with APILimitEnforcer(
        org_id=org_id,
        category=LimitCategory.LLM_TOKENS_MONTH,
        estimated_units=1000,
    ) as ctx:
        ctx.record_actual(actual_tokens)

    assert len(cost_units_calls) == 1
    rec = cost_units_calls[0]
    assert rec["entity_scope"] == "org"
    assert rec["entity_value"] == str(org_id)
    assert rec["tokens"] == actual_tokens
    assert rec["requests"] == 0
    assert rec["minutes"] == 0.0

