"""
Tests for billing enforcement module.

Test Strategy
=============
This module tests the billing limit enforcement system at the unit level.
Tests are organized into logical groups:

1. **LimitCheckResult tests**: Verify the dataclass correctly determines
    blocking and warning states based on enforcement actions.

2. **PlanLimits tests**: Verify default plan tier definitions and the
    `get_plan_limits` function handles edge cases (unknown plans, case sensitivity).

3. **CheckLimit tests**: Verify the utility function correctly categorizes
    usage into unlimited, under-limit, soft-limit (warning), and hard-limit states.

4. **BillingEnforcer tests**: Verify the main enforcement class handles:
    - Cache invalidation (single org and all orgs)
    - Limit checking with mocked usage/limits data
    - Feature access checks

5. **Module function tests**: Verify environment-based feature flags
    (billing_enabled, enforcement_enabled) and singleton behavior.

All tests use mocking to isolate from database dependencies. For integration
tests with real database, see test_billing_endpoints_integration.py.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from tldw_Server_API.app.core.Billing.enforcement import (
    BillingEnforcer,
    LimitCategory,
    EnforcementAction,
    LimitCheckResult,
    UsageSummary,
    get_billing_enforcer,
    billing_enabled,
    enforcement_enabled,
)
from tldw_Server_API.app.core.Billing.plan_limits import (
    PlanTier,
    PlanLimits,
    DEFAULT_LIMITS,
    get_plan_limits,
    check_limit,
    SOFT_LIMIT_PERCENT,
)


class TestLimitCheckResult:
    """Tests for LimitCheckResult dataclass."""

    def test_should_block_soft_block(self):

        """SOFT_BLOCK should indicate blocking."""
        result = LimitCheckResult(
            category="api_calls_day",
            action=EnforcementAction.SOFT_BLOCK,
            current=100,
            limit=100,
            percent_used=100,
        )
        assert result.should_block is True

    def test_should_block_hard_block(self):

        """HARD_BLOCK should indicate blocking."""
        result = LimitCheckResult(
            category="api_calls_day",
            action=EnforcementAction.HARD_BLOCK,
            current=150,
            limit=100,
            percent_used=150,
        )
        assert result.should_block is True

    def test_should_not_block_allow(self):

        """ALLOW should not indicate blocking."""
        result = LimitCheckResult(
            category="api_calls_day",
            action=EnforcementAction.ALLOW,
            current=50,
            limit=100,
            percent_used=50,
        )
        assert result.should_block is False

    def test_should_not_block_warn(self):

        """WARN should not indicate blocking."""
        result = LimitCheckResult(
            category="api_calls_day",
            action=EnforcementAction.WARN,
            current=85,
            limit=100,
            percent_used=85,
        )
        assert result.should_block is False

    def test_should_warn(self):

        """WARN action should indicate warning."""
        result = LimitCheckResult(
            category="api_calls_day",
            action=EnforcementAction.WARN,
            current=85,
            limit=100,
            percent_used=85,
        )
        assert result.should_warn is True

    def test_should_not_warn_allow(self):

        """ALLOW action should not indicate warning."""
        result = LimitCheckResult(
            category="api_calls_day",
            action=EnforcementAction.ALLOW,
            current=50,
            limit=100,
            percent_used=50,
        )
        assert result.should_warn is False


class TestPlanLimits:
    """Tests for plan limit definitions."""

    def test_free_tier_has_limits(self):

        """Free tier should have restrictive limits."""
        limits = DEFAULT_LIMITS[PlanTier.FREE]
        assert limits.storage_mb == 1024
        assert limits.api_calls_day == 100
        assert limits.team_members == 1
        assert limits.advanced_analytics is False

    def test_pro_tier_has_higher_limits(self):

        """Pro tier should have higher limits than Free."""
        free_limits = DEFAULT_LIMITS[PlanTier.FREE]
        pro_limits = DEFAULT_LIMITS[PlanTier.PRO]
        assert pro_limits.storage_mb > free_limits.storage_mb
        assert pro_limits.api_calls_day > free_limits.api_calls_day
        assert pro_limits.advanced_analytics is True

    def test_enterprise_has_unlimited_members(self):

        """Enterprise tier should have unlimited team members."""
        limits = DEFAULT_LIMITS[PlanTier.ENTERPRISE]
        assert limits.team_members == -1  # -1 means unlimited

    def test_get_plan_limits_free(self):

        """get_plan_limits should return correct limits for free tier."""
        limits = get_plan_limits("free")
        assert limits["storage_mb"] == 1024
        assert limits["api_calls_day"] == 100

    def test_get_plan_limits_unknown_defaults_to_free(self):

        """Unknown plan names should default to free tier."""
        limits = get_plan_limits("unknown_plan")
        free_limits = get_plan_limits("free")
        assert limits == free_limits

    def test_get_plan_limits_case_insensitive(self):

        """Plan names should be case insensitive."""
        lower = get_plan_limits("pro")
        upper = get_plan_limits("PRO")
        mixed = get_plan_limits("Pro")
        assert lower == upper == mixed


class TestCheckLimit:
    """Tests for the check_limit utility function."""

    def test_unlimited_returns_no_warning(self):

        """Unlimited limits (-1) should never warn or exceed."""
        result = check_limit(current_value=1000000, limit_value=-1, limit_name="test")
        assert result["unlimited"] is True
        assert result["exceeded"] is False
        assert result["warning"] is False
        assert result["percent_used"] == 0

    def test_under_limit_no_warning(self):

        """Usage well under limit should not warn."""
        result = check_limit(current_value=50, limit_value=100, limit_name="test")
        assert result["exceeded"] is False
        assert result["warning"] is False
        assert result["percent_used"] == 50

    def test_at_soft_limit_warns(self):

        """Usage at soft limit (80%) should warn but not exceed."""
        result = check_limit(current_value=80, limit_value=100, limit_name="test")
        assert result["exceeded"] is False
        assert result["warning"] is True
        assert result["percent_used"] == 80

    def test_at_hard_limit_exceeds(self):

        """Usage at hard limit should exceed."""
        result = check_limit(current_value=100, limit_value=100, limit_name="test")
        assert result["exceeded"] is True
        assert result["warning"] is False  # No warning if exceeded
        assert result["percent_used"] == 100

    def test_over_limit_exceeds(self):

        """Usage over limit should exceed."""
        result = check_limit(current_value=150, limit_value=100, limit_name="test")
        assert result["exceeded"] is True
        assert result["percent_used"] == 150


class TestBillingEnforcer:
    """Tests for BillingEnforcer class."""

    @pytest.fixture
    def enforcer(self):
        """Create a BillingEnforcer instance."""
        return BillingEnforcer(soft_limit_percent=80)

    def test_cache_invalidation_single_org(self, enforcer):

        """Cache invalidation should work for single org."""
        # Populate cache
        enforcer._usage_cache[1] = (UsageSummary(org_id=1), 0)
        enforcer._limits_cache[1] = ({"api_calls_day": 100}, 0)
        enforcer._usage_cache[2] = (UsageSummary(org_id=2), 0)

        # Invalidate for org 1 only
        enforcer.invalidate_cache(org_id=1)

        assert 1 not in enforcer._usage_cache
        assert 1 not in enforcer._limits_cache
        assert 2 in enforcer._usage_cache

    def test_cache_invalidation_all_orgs(self, enforcer):

        """Cache invalidation should work for all orgs."""
        # Populate cache
        enforcer._usage_cache[1] = (UsageSummary(org_id=1), 0)
        enforcer._limits_cache[1] = ({"api_calls_day": 100}, 0)
        enforcer._usage_cache[2] = (UsageSummary(org_id=2), 0)

        # Invalidate all
        enforcer.invalidate_cache()

        assert len(enforcer._usage_cache) == 0
        assert len(enforcer._limits_cache) == 0

    @pytest.mark.asyncio
    async def test_check_limit_unlimited(self, enforcer):
        """Checking unlimited limit should always allow."""
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits:
            with patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
                mock_limits.return_value = {"api_calls_day": -1}
                mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=10000)

                result = await enforcer.check_limit(
                    org_id=1,
                    category=LimitCategory.API_CALLS_DAY,
                    requested_units=1,
                )

                assert result.action == EnforcementAction.ALLOW
                assert result.unlimited is True
                assert result.should_block is False

    @pytest.mark.asyncio
    async def test_check_limit_under_soft_limit(self, enforcer):
        """Usage under soft limit should allow without warning."""
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits:
            with patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
                mock_limits.return_value = {"api_calls_day": 100}
                mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=50)

                result = await enforcer.check_limit(
                    org_id=1,
                    category=LimitCategory.API_CALLS_DAY,
                    requested_units=1,
                )

                assert result.action == EnforcementAction.ALLOW
                assert result.should_block is False
                assert result.should_warn is False

    @pytest.mark.asyncio
    async def test_check_limit_at_soft_limit(self, enforcer):
        """Usage at soft limit should warn but not block."""
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits:
            with patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
                mock_limits.return_value = {"api_calls_day": 100}
                mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=79)

                result = await enforcer.check_limit(
                    org_id=1,
                    category=LimitCategory.API_CALLS_DAY,
                    requested_units=1,
                )

                # 79 + 1 = 80, which is at soft limit
                assert result.action == EnforcementAction.WARN
                assert result.should_block is False
                assert result.should_warn is True

    @pytest.mark.asyncio
    async def test_check_limit_exceeds_hard_limit(self, enforcer):
        """Usage exceeding hard limit should soft block."""
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits:
            with patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
                mock_limits.return_value = {"api_calls_day": 100}
                mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=100)

                result = await enforcer.check_limit(
                    org_id=1,
                    category=LimitCategory.API_CALLS_DAY,
                    requested_units=1,
                )

                assert result.action == EnforcementAction.SOFT_BLOCK
                assert result.should_block is True
                assert "exceeded" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_limit_invalid_limit_value_fails_open(self, enforcer):
        """Invalid limit values should be treated as unlimited to avoid crashes."""
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits:
            with patch.object(enforcer, "get_org_usage", new_callable=AsyncMock) as mock_usage:
                mock_limits.return_value = {"api_calls_day": None}
                mock_usage.return_value = UsageSummary(org_id=1, api_calls_today=1000)

                result = await enforcer.check_limit(
                    org_id=1,
                    category=LimitCategory.API_CALLS_DAY,
                    requested_units=1,
                )

                assert result.action == EnforcementAction.ALLOW
                assert result.unlimited is True

    @pytest.mark.asyncio
    async def test_check_feature_access_enabled(self, enforcer):
        """Feature access should return True when enabled."""
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits:
            mock_limits.return_value = {"advanced_analytics": True}

            result = await enforcer.check_feature_access(org_id=1, feature="advanced_analytics")

            assert result is True

    @pytest.mark.asyncio
    async def test_check_feature_access_disabled(self, enforcer):
        """Feature access should return False when disabled."""
        with patch.object(enforcer, "get_org_limits", new_callable=AsyncMock) as mock_limits:
            mock_limits.return_value = {"advanced_analytics": False}

            result = await enforcer.check_feature_access(org_id=1, feature="advanced_analytics")

            assert result is False

    @pytest.mark.asyncio
    async def test_get_transcription_minutes_month_uses_ledger_total(self, monkeypatch):
        """_get_transcription_minutes_month should use ResourceDailyLedger.peek_range total."""

        class _FakeLedger:
            def __init__(self, *args, **kwargs):
                self.init_called = False
                self.peek_args = None

            async def initialize(self):
                self.init_called = True

            async def peek_range(
                self,
                *,
                entity_scope,
                entity_value,
                category,
                start_day_utc,
                end_day_utc,
            ):
                # Record arguments for basic sanity checks
                self.peek_args = {
                    "entity_scope": entity_scope,
                    "entity_value": entity_value,
                    "category": category,
                    "start_day_utc": start_day_utc,
                    "end_day_utc": end_day_utc,
                }
                # Simulate a monthly total of 42 minutes
                return {"days": [], "total": 42}

        # Patch the ResourceDailyLedger used by BillingEnforcer
        monkeypatch.setattr(
            "tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger.ResourceDailyLedger",
            _FakeLedger,
            raising=False,
        )

        enforcer = BillingEnforcer()
        minutes = await enforcer._get_transcription_minutes_month(org_id=123)

        assert minutes == 42

    @pytest.mark.asyncio
    async def test_get_rag_queries_today_uses_ledger_total(self, monkeypatch):
        """_get_rag_queries_today should use ResourceDailyLedger.total_for_day."""

        class _FakeLedger:
            def __init__(self, *args, **kwargs):
                self.init_called = False
                self.total_args = None

            async def initialize(self):
                self.init_called = True

            async def total_for_day(
                self,
                entity_scope: str,
                entity_value: str,
                category: str,
                day_utc: str | None = None,
            ) -> int:
                self.total_args = {
                    "entity_scope": entity_scope,
                    "entity_value": entity_value,
                    "category": category,
                    "day_utc": day_utc,
                }
                return 7

        monkeypatch.setattr(
            "tldw_Server_API.app.core.DB_Management.Resource_Daily_Ledger.ResourceDailyLedger",
            _FakeLedger,
            raising=False,
        )

        enforcer = BillingEnforcer()
        count = await enforcer._get_rag_queries_today(org_id=321)

        assert count == 7


class TestModuleFunctions:
    """Tests for module-level functions."""

    def test_billing_enabled_false_by_default(self, monkeypatch):

        """billing_enabled should be False by default."""
        monkeypatch.delenv("BILLING_ENABLED", raising=False)
        assert billing_enabled() is False

    def test_billing_enabled_true(self, monkeypatch):

        """billing_enabled should be True when env var is set."""
        monkeypatch.setenv("BILLING_ENABLED", "true")
        assert billing_enabled() is True

    def test_enforcement_enabled_true_by_default(self, monkeypatch):

        """enforcement_enabled should be True by default."""
        monkeypatch.delenv("LIMIT_ENFORCEMENT_ENABLED", raising=False)
        assert enforcement_enabled() is True

    def test_enforcement_enabled_false(self, monkeypatch):

        """enforcement_enabled should be False when env var is set."""
        monkeypatch.setenv("LIMIT_ENFORCEMENT_ENABLED", "false")
        assert enforcement_enabled() is False

    def test_get_billing_enforcer_singleton(self):

        """get_billing_enforcer should return singleton instance."""
        enforcer1 = get_billing_enforcer()
        enforcer2 = get_billing_enforcer()
        assert enforcer1 is enforcer2
