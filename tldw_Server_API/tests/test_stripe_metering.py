"""
Tests for Stripe usage metering reconciliation service.

Covers:
- Service initialization and configuration
- Billing-disabled skip behavior
- sync_daily_usage returns expected structure
- check_reconciliation returns expected structure
- Default date handling (yesterday)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tldw_Server_API.app.services.stripe_metering_service import StripeMeteringService


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


class TestStripeMeteringServiceInit:
    """Tests for StripeMeteringService initialization."""

    def test_disabled_by_default(self):
        """Service is disabled when no env vars are set."""
        with patch.dict("os.environ", {}, clear=True):
            svc = StripeMeteringService()
            assert svc.is_enabled is False

    def test_enabled_with_env_vars(self):
        """Service is enabled when both BILLING_ENABLED and STRIPE_API_KEY are set."""
        with patch.dict(
            "os.environ",
            {"BILLING_ENABLED": "true", "STRIPE_API_KEY": "sk_test_123"},
        ):
            svc = StripeMeteringService()
            assert svc.is_enabled is True

    def test_enabled_with_numeric_flag(self):
        """BILLING_ENABLED=1 also enables the service."""
        with patch.dict(
            "os.environ",
            {"BILLING_ENABLED": "1", "STRIPE_API_KEY": "sk_test_abc"},
        ):
            svc = StripeMeteringService()
            assert svc.is_enabled is True

    def test_not_enabled_without_stripe_key(self):
        """Service is not enabled if STRIPE_API_KEY is missing."""
        with patch.dict("os.environ", {"BILLING_ENABLED": "true"}, clear=True):
            svc = StripeMeteringService()
            assert svc.is_enabled is False


# ---------------------------------------------------------------------------
# sync_daily_usage tests
# ---------------------------------------------------------------------------


class TestSyncDailyUsage:
    """Tests for StripeMeteringService.sync_daily_usage."""

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self):
        """Returns skip status when billing is not enabled."""
        with patch.dict("os.environ", {}, clear=True):
            svc = StripeMeteringService()
            result = await svc.sync_daily_usage()

        assert result["status"] == "skipped"
        assert result["reason"] == "billing_not_enabled"

    @pytest.mark.asyncio
    async def test_returns_completed_with_date(self):
        """Returns completed status with the specified date."""
        with patch.dict(
            "os.environ",
            {"BILLING_ENABLED": "true", "STRIPE_API_KEY": "sk_test_123"},
        ):
            svc = StripeMeteringService()
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["status"] == "completed"
        assert result["date"] == "2026-03-13"
        assert result["synced_users"] == 0
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_defaults_to_yesterday(self):
        """When no date is specified, defaults to yesterday."""
        yesterday = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")

        with patch.dict(
            "os.environ",
            {"BILLING_ENABLED": "true", "STRIPE_API_KEY": "sk_test_123"},
        ):
            svc = StripeMeteringService()
            result = await svc.sync_daily_usage()

        assert result["date"] == yesterday


# ---------------------------------------------------------------------------
# check_reconciliation tests
# ---------------------------------------------------------------------------


class TestCheckReconciliation:
    """Tests for StripeMeteringService.check_reconciliation."""

    @pytest.mark.asyncio
    async def test_skips_when_disabled(self):
        """Returns skip status when billing is not enabled."""
        with patch.dict("os.environ", {}, clear=True):
            svc = StripeMeteringService()
            result = await svc.check_reconciliation()

        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_returns_completed_structure(self):
        """Returns expected reconciliation structure."""
        with patch.dict(
            "os.environ",
            {"BILLING_ENABLED": "true", "STRIPE_API_KEY": "sk_test_123"},
        ):
            svc = StripeMeteringService()
            result = await svc.check_reconciliation(date="2026-03-13")

        assert result["status"] == "completed"
        assert result["date"] == "2026-03-13"
        assert isinstance(result["discrepancies"], list)
        assert len(result["discrepancies"]) == 0
