"""
Tests for overage policy integration with BillingEnforcer.check_limit().

Verifies that:
- Hard-block overage policy upgrades SOFT_BLOCK to HARD_BLOCK
- Degraded overage policy upgrades ALLOW to SOFT_BLOCK when over grace
- Notify-only policy upgrades ALLOW to WARN when above threshold
- Default notify_only mode does not block
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.core.Billing import enforcement as enforcement_module
from tldw_Server_API.app.core.Billing.enforcement import (
    BillingEnforcer,
    EnforcementAction,
    LimitCategory,
    UsageSummary,
)


@pytest.fixture
def enforcer():
    """Create a BillingEnforcer with short cache TTL for testing."""
    return BillingEnforcer(cache_ttl=0, soft_limit_percent=80)


class TestOverageHardBlock:
    """Overage mode=hard_block should escalate to HARD_BLOCK."""

    @pytest.mark.asyncio
    async def test_hard_block_when_over_grace(self, enforcer, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "hard_block")
        monkeypatch.setenv("BILLING_OVERAGE_GRACE_PCT", "5")
        monkeypatch.setenv("BILLING_OVERAGE_NOTIFY_PCT", "80")

        # Mock org limits and usage so usage is 115% (over 105% grace threshold)
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
             patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
            mock_limits.return_value = {"api_calls_day": 100}
            mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=114)

            result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
            assert result.action == EnforcementAction.HARD_BLOCK
            assert "Hard blocked" in (result.message or "")

    @pytest.mark.asyncio
    async def test_no_hard_block_within_grace(self, enforcer, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "hard_block")
        monkeypatch.setenv("BILLING_OVERAGE_GRACE_PCT", "10")

        # Usage at 105% -- within 10% grace
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
             patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
            mock_limits.return_value = {"api_calls_day": 100}
            mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=104)

            result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
            # Should be SOFT_BLOCK (base behavior) not HARD_BLOCK
            assert result.action == EnforcementAction.SOFT_BLOCK


class TestOverageDegraded:
    """Overage mode=degraded should escalate to SOFT_BLOCK."""

    @pytest.mark.asyncio
    async def test_degraded_when_over_grace(self, enforcer, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "degraded")
        monkeypatch.setenv("BILLING_OVERAGE_GRACE_PCT", "5")
        monkeypatch.setenv("BILLING_OVERAGE_NOTIFY_PCT", "80")

        # Usage at 106% -- over 5% grace threshold
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
             patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
            mock_limits.return_value = {"api_calls_day": 100}
            mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=105)

            result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
            assert result.action == EnforcementAction.SOFT_BLOCK


class TestOverageNotifyOnly:
    """Overage mode=notify_only should upgrade ALLOW to WARN."""

    @pytest.mark.asyncio
    async def test_notify_upgrades_allow_to_warn(self, enforcer, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "notify_only")
        monkeypatch.setenv("BILLING_OVERAGE_NOTIFY_PCT", "80")
        monkeypatch.setenv("BILLING_OVERAGE_GRACE_PCT", "5")

        # Usage at 85% -- above 80% notify threshold but under limit
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
             patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
            mock_limits.return_value = {"api_calls_day": 100}
            mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=84)

            result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
            assert result.action == EnforcementAction.WARN

    @pytest.mark.asyncio
    async def test_notify_only_never_blocks(self, enforcer, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "notify_only")
        monkeypatch.setenv("BILLING_OVERAGE_NOTIFY_PCT", "80")
        monkeypatch.setenv("BILLING_OVERAGE_GRACE_PCT", "5")

        # Usage at 150% -- way over limit
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
             patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
            mock_limits.return_value = {"api_calls_day": 100}
            mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=149)

            result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
            # Base action is SOFT_BLOCK (over limit), overage notify_only doesn't upgrade to HARD
            assert result.action == EnforcementAction.SOFT_BLOCK
            assert result.action != EnforcementAction.HARD_BLOCK

    @pytest.mark.asyncio
    async def test_no_warn_below_threshold(self, enforcer, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "notify_only")
        monkeypatch.setenv("BILLING_OVERAGE_NOTIFY_PCT", "80")
        monkeypatch.setenv("BILLING_OVERAGE_GRACE_PCT", "5")

        # Usage at 50% -- well under threshold
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
             patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
            mock_limits.return_value = {"api_calls_day": 100}
            mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=49)

            result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
            assert result.action == EnforcementAction.ALLOW


class TestOverageUnlimited:
    """Unlimited limits should bypass overage checks."""

    @pytest.mark.asyncio
    async def test_unlimited_ignores_overage(self, enforcer, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "hard_block")

        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
             patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
            mock_limits.return_value = {"api_calls_day": -1}
            mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=999999)

            result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
            assert result.action == EnforcementAction.ALLOW
            assert result.unlimited is True


class TestOveragePolicyLifecycle:
    @pytest.mark.asyncio
    async def test_overage_policy_is_loaded_once(self, monkeypatch):
        monkeypatch.setenv("BILLING_OVERAGE_MODE", "notify_only")
        monkeypatch.setenv("BILLING_OVERAGE_NOTIFY_PCT", "80")

        policy = MagicMock()
        policy.evaluate.return_value = {
            "blocked": False,
            "degraded": False,
            "notify": False,
            "mode": "notify_only",
        }

        with patch.object(enforcement_module.OveragePolicy, "from_env", return_value=policy) as mock_from_env:
            enforcer = BillingEnforcer(cache_ttl=0)
            with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
                 patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
                mock_limits.return_value = {"api_calls_day": 100}
                mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=10)

                await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)
                await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)

        assert mock_from_env.call_count == 1

    @pytest.mark.asyncio
    async def test_logs_warning_when_overage_policy_evaluation_is_skipped(self):
        policy = MagicMock()
        policy.evaluate.side_effect = RuntimeError("broken policy")

        with patch.object(enforcement_module.OveragePolicy, "from_env", return_value=policy):
            enforcer = BillingEnforcer(cache_ttl=0)
            with patch.object(enforcement_module.logger, "warning") as mock_warning, \
                 patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits, \
                 patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
                mock_limits.return_value = {"api_calls_day": 100}
                mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=10)

                result = await enforcer.check_limit(1, LimitCategory.API_CALLS_DAY)

        assert result.action == EnforcementAction.ALLOW
        mock_warning.assert_called_once()
