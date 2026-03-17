"""
Tests for Stripe usage metering reconciliation service.

Covers:
- Service initialization and configuration
- Billing-disabled skip behavior
- sync_daily_usage with mocked DB and Stripe calls
- check_reconciliation with mocked DB
- Default date handling (yesterday)
- Double-counting prevention
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.services import stripe_metering_service as _sms_module
from tldw_Server_API.app.services.stripe_metering_service import StripeMeteringService

# Mock stripe module for environments where stripe is not installed
_mock_stripe = MagicMock()
_mock_stripe.api_key = None


def _stripe_ok():
    """Context manager stack: pretend stripe is installed and provide a mock module."""
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(patch.object(_sms_module, "STRIPE_AVAILABLE", True))
    # Only patch stripe if it's actually None (not installed)
    if _sms_module.stripe is None:
        stack.enter_context(patch.object(_sms_module, "stripe", _mock_stripe))
    return stack


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


def _make_enabled_svc() -> StripeMeteringService:
    """Create a StripeMeteringService with billing enabled."""
    with patch.dict(
        "os.environ",
            {"BILLING_ENABLED": "true", "STRIPE_API_KEY": "sk_test_123"},
        ):
            return StripeMeteringService()


class _AcquireContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, conn):
        self._conn = conn

    def acquire(self):
        return _AcquireContext(self._conn)


class _FakeSqliteConn:
    def __init__(self, execute_side_effect):
        self.execute = AsyncMock(side_effect=execute_side_effect)


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
    async def test_skips_when_stripe_not_installed(self):
        """Returns skip status when stripe package is not installed."""
        svc = _make_enabled_svc()
        with patch.object(_sms_module, "STRIPE_AVAILABLE", False):
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["status"] == "skipped"
        assert result["reason"] == "stripe_package_not_installed"

    @pytest.mark.asyncio
    async def test_returns_completed_no_usage(self):
        """Returns completed with zero synced_users when no usage data exists."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[])

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["status"] == "completed"
        assert result["date"] == "2026-03-13"
        assert result["synced_users"] == 0
        assert result["errors"] == 0
        assert result["message"] == "no_usage_data"

    @pytest.mark.asyncio
    async def test_defaults_to_yesterday(self):
        """When no date is specified, defaults to yesterday."""
        yesterday = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")

        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[])

        with _stripe_ok():
            result = await svc.sync_daily_usage()

        assert result["date"] == yesterday

    @pytest.mark.asyncio
    async def test_syncs_user_with_subscription(self):
        """Successfully syncs usage for a user with an active Stripe subscription."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 100, "errors": 2, "bytes_total": 5000,
             "bytes_in_total": 3000, "latency_avg_ms": 50.0},
        ])
        svc._query_user_subscription = AsyncMock(return_value={
            "stripe_customer_id": "cus_test1",
            "stripe_subscription_id": "sub_test1",
            "org_id": 10,
        })
        svc._already_synced = AsyncMock(return_value=False)
        svc._get_subscription_metered_item = AsyncMock(return_value="si_item1")
        svc._report_usage_to_stripe = AsyncMock()
        svc._record_sync = AsyncMock()

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["status"] == "completed"
        assert result["synced_users"] == 1
        assert result["errors"] == 0

        svc._report_usage_to_stripe.assert_called_once()
        call_args = svc._report_usage_to_stripe.call_args
        assert call_args[0][0] == "si_item1"
        assert call_args[0][1] == 100  # requests quantity
        svc._record_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_already_synced_user(self):
        """Skips users whose usage was already synced (prevents double-counting)."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 50, "errors": 0, "bytes_total": 1000,
             "bytes_in_total": 500, "latency_avg_ms": 30.0},
        ])
        svc._query_user_subscription = AsyncMock(return_value={
            "stripe_customer_id": "cus_test1",
            "stripe_subscription_id": "sub_test1",
            "org_id": 10,
        })
        svc._already_synced = AsyncMock(return_value=True)

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["synced_users"] == 0
        assert result["skipped_users"] == 1

    @pytest.mark.asyncio
    async def test_skips_user_without_subscription(self):
        """Skips users who have no active Stripe subscription."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 99, "requests": 10, "errors": 0, "bytes_total": 100,
             "bytes_in_total": 50, "latency_avg_ms": 10.0},
        ])
        svc._query_user_subscription = AsyncMock(return_value=None)

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["synced_users"] == 0
        assert result["skipped_users"] == 1

    @pytest.mark.asyncio
    async def test_skips_user_with_zero_requests(self):
        """Skips users with zero requests."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 0, "errors": 0, "bytes_total": 0,
             "bytes_in_total": 0, "latency_avg_ms": 0},
        ])

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["synced_users"] == 0
        assert result["skipped_users"] == 1

    @pytest.mark.asyncio
    async def test_handles_stripe_error(self):
        """Counts errors when Stripe API call fails."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 100, "errors": 0, "bytes_total": 5000,
             "bytes_in_total": 3000, "latency_avg_ms": 50.0},
        ])
        svc._query_user_subscription = AsyncMock(return_value={
            "stripe_customer_id": "cus_test1",
            "stripe_subscription_id": "sub_test1",
            "org_id": 10,
        })
        svc._already_synced = AsyncMock(return_value=False)
        svc._get_subscription_metered_item = AsyncMock(return_value="si_item1")
        svc._report_usage_to_stripe = AsyncMock(
            side_effect=RuntimeError("Stripe API error")
        )

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["errors"] == 1
        assert result["synced_users"] == 0

    @pytest.mark.asyncio
    async def test_db_pool_error_returns_error_status(self):
        """Returns error status when DB pool is unavailable."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(side_effect=RuntimeError("no pool"))

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["status"] == "error"
        assert "db_pool_unavailable" in result["error"]

    @pytest.mark.asyncio
    async def test_skips_user_without_metered_item(self):
        """Skips users whose subscription has no metered item."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._ensure_metering_sync_table = AsyncMock()
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 100, "errors": 0, "bytes_total": 5000,
             "bytes_in_total": 3000, "latency_avg_ms": 50.0},
        ])
        svc._query_user_subscription = AsyncMock(return_value={
            "stripe_customer_id": "cus_test1",
            "stripe_subscription_id": "sub_test1",
            "org_id": 10,
        })
        svc._already_synced = AsyncMock(return_value=False)
        svc._get_subscription_metered_item = AsyncMock(return_value=None)

        with _stripe_ok():
            result = await svc.sync_daily_usage(date="2026-03-13")

        assert result["synced_users"] == 0
        assert result["skipped_users"] == 1

    @pytest.mark.asyncio
    async def test_query_usage_for_date_falls_back_when_bytes_in_total_missing(self):
        svc = _make_enabled_svc()
        legacy_cursor = MagicMock()
        legacy_cursor.description = [
            ("user_id",),
            ("requests",),
            ("errors",),
            ("bytes_total",),
            ("latency_avg_ms",),
        ]
        legacy_cursor.fetchall = AsyncMock(return_value=[(7, 12, 1, 4096, 25.0)])

        conn = _FakeSqliteConn(
            [
                sqlite3.OperationalError("no such column: bytes_in_total"),
                legacy_cursor,
            ]
        )

        rows = await svc._query_usage_for_date(_FakePool(conn), "2026-03-13")

        assert rows == [
            {
                "user_id": 7,
                "requests": 12,
                "errors": 1,
                "bytes_total": 4096,
                "bytes_in_total": 0,
                "latency_avg_ms": 25.0,
            }
        ]

    @pytest.mark.asyncio
    async def test_query_user_subscription_falls_back_to_org_owner(self):
        svc = _make_enabled_svc()
        miss_cursor = MagicMock()
        miss_cursor.fetchone = AsyncMock(return_value=None)

        owner_cursor = MagicMock()
        owner_cursor.description = [
            ("stripe_customer_id",),
            ("stripe_subscription_id",),
            ("org_id",),
        ]
        owner_cursor.fetchone = AsyncMock(return_value=("cus_owner", "sub_owner", 9))

        conn = _FakeSqliteConn([miss_cursor, owner_cursor])

        result = await svc._query_user_subscription(_FakePool(conn), 42)

        assert result == {
            "stripe_customer_id": "cus_owner",
            "stripe_subscription_id": "sub_owner",
            "org_id": 9,
        }


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
    async def test_returns_completed_no_discrepancies(self):
        """Returns completed with no discrepancies when usage matches synced data."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 100, "errors": 0, "bytes_total": 5000,
             "bytes_in_total": 3000, "latency_avg_ms": 50.0},
        ])
        svc._query_sync_totals = AsyncMock(return_value=[
            {"user_id": 1, "stripe_subscription_id": "sub_1",
             "requests_synced": 100, "bytes_synced": 5000},
        ])

        result = await svc.check_reconciliation(date="2026-03-13")

        assert result["status"] == "completed"
        assert result["date"] == "2026-03-13"
        assert isinstance(result["discrepancies"], list)
        assert len(result["discrepancies"]) == 0
        assert result["total_local_requests"] == 100
        assert result["total_synced_requests"] == 100

    @pytest.mark.asyncio
    async def test_detects_drift(self):
        """Detects discrepancies between local usage and synced records."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 100, "errors": 0, "bytes_total": 5000,
             "bytes_in_total": 3000, "latency_avg_ms": 50.0},
            {"user_id": 2, "requests": 50, "errors": 0, "bytes_total": 1000,
             "bytes_in_total": 500, "latency_avg_ms": 20.0},
        ])
        svc._query_sync_totals = AsyncMock(return_value=[
            {"user_id": 1, "stripe_subscription_id": "sub_1",
             "requests_synced": 80, "bytes_synced": 4000},
            # user_id 2 has no sync record
        ])

        result = await svc.check_reconciliation(date="2026-03-13")

        assert result["status"] == "completed"
        assert len(result["discrepancies"]) == 2
        # User 1: 100 local, 80 synced => drift of 20
        d1 = next(d for d in result["discrepancies"] if d["user_id"] == 1)
        assert d1["drift"] == 20
        # User 2: 50 local, 0 synced => drift of 50
        d2 = next(d for d in result["discrepancies"] if d["user_id"] == 2)
        assert d2["drift"] == 50

    @pytest.mark.asyncio
    async def test_handles_sync_log_table_missing(self):
        """Gracefully handles missing metering_sync_log table."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._query_usage_for_date = AsyncMock(return_value=[
            {"user_id": 1, "requests": 50, "errors": 0, "bytes_total": 1000,
             "bytes_in_total": 500, "latency_avg_ms": 10.0},
        ])
        svc._query_sync_totals = AsyncMock(
            side_effect=Exception("no such table: metering_sync_log")
        )

        result = await svc.check_reconciliation(date="2026-03-13")

        assert result["status"] == "completed"
        # All usage shows as drift since no sync records
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["drift"] == 50

    @pytest.mark.asyncio
    async def test_defaults_to_yesterday(self):
        """When no date is specified, defaults to yesterday."""
        yesterday = (
            datetime.now(timezone.utc) - timedelta(days=1)
        ).strftime("%Y-%m-%d")

        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(return_value=MagicMock())
        svc._query_usage_for_date = AsyncMock(return_value=[])
        svc._query_sync_totals = AsyncMock(return_value=[])

        result = await svc.check_reconciliation()

        assert result["date"] == yesterday

    @pytest.mark.asyncio
    async def test_db_pool_error_returns_error(self):
        """Returns error status when DB pool is unavailable."""
        svc = _make_enabled_svc()
        svc._get_db_pool = AsyncMock(side_effect=RuntimeError("no pool"))

        result = await svc.check_reconciliation(date="2026-03-13")

        assert result["status"] == "error"
        assert "db_pool_unavailable" in result["error"]
        assert isinstance(result["discrepancies"], list)
