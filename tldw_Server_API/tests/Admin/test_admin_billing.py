"""
Tests for admin billing management endpoints and service.

Covers:
- Billing overview endpoint returns expected structure
- List subscriptions returns a list
- Service functions are callable
- Handles billing-disabled case gracefully
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.services import admin_billing_service


# ---------------------------------------------------------------------------
# Helper: build a mock pool whose .acquire() is an async context manager
# ---------------------------------------------------------------------------

def _make_mock_pool(mock_conn):
    """Build a MagicMock pool where ``async with pool.acquire()`` yields *mock_conn*."""
    mock_pool = MagicMock()
    mock_pool.pool = None  # SQLite mode

    @asynccontextmanager
    async def _acquire():
        yield mock_conn

    mock_pool.acquire = _acquire
    return mock_pool


# ---------------------------------------------------------------------------
# Service-layer unit tests
# ---------------------------------------------------------------------------


class TestGetBillingOverview:
    """Tests for admin_billing_service.get_billing_overview."""

    @pytest.mark.asyncio
    async def test_billing_disabled_returns_minimal_response(self):
        """When billing is disabled, overview returns zeroed-out stats."""
        with patch.object(admin_billing_service, "is_billing_enabled", return_value=False):
            result = await admin_billing_service.get_billing_overview()

        assert result["billing_enabled"] is False
        assert result["total_subscriptions"] == 0
        assert result["active_subscriptions"] == 0
        assert result["canceled_subscriptions"] == 0
        assert result["past_due_subscriptions"] == 0
        assert result["plan_distribution"] == {}
        assert result["mrr_estimate_usd"] == 0

    @pytest.mark.asyncio
    async def test_billing_enabled_queries_database(self):
        """When billing is enabled, overview queries the database."""
        mock_conn = AsyncMock()

        # Mock cursor for status counts
        mock_cur_status = AsyncMock()
        mock_cur_status.description = [("status",), ("cnt",)]
        mock_cur_status.fetchall = AsyncMock(return_value=[
            ("active", 5),
            ("canceled", 2),
        ])

        # Mock cursor for plan distribution
        mock_cur_plan = AsyncMock()
        mock_cur_plan.description = [("name",), ("cnt",)]
        mock_cur_plan.fetchall = AsyncMock(return_value=[
            ("pro", 3),
            ("enterprise", 2),
        ])

        # Mock cursor for MRR
        mock_cur_mrr = AsyncMock()
        mock_cur_mrr.fetchone = AsyncMock(return_value=(145,))

        mock_conn.execute = AsyncMock(side_effect=[
            mock_cur_status, mock_cur_plan, mock_cur_mrr,
        ])

        mock_pool = _make_mock_pool(mock_conn)

        async def _mock_get_db_pool():
            return mock_pool

        with (
            patch.object(admin_billing_service, "is_billing_enabled", return_value=True),
            patch.object(admin_billing_service, "get_db_pool", side_effect=_mock_get_db_pool),
        ):
            result = await admin_billing_service.get_billing_overview()

        assert result["billing_enabled"] is True
        assert result["total_subscriptions"] == 7
        assert result["active_subscriptions"] == 5
        assert result["canceled_subscriptions"] == 2
        assert result["mrr_estimate_usd"] == 145


class TestListAllSubscriptions:
    """Tests for admin_billing_service.list_all_subscriptions."""

    @pytest.mark.asyncio
    async def test_returns_items_and_total(self):
        """list_all_subscriptions returns a dict with items and total."""
        mock_conn = AsyncMock()

        # Count cursor
        mock_cur_count = AsyncMock()
        mock_cur_count.fetchone = AsyncMock(return_value=(2,))

        # Data cursor
        mock_cur_data = AsyncMock()
        mock_cur_data.description = [
            ("id",), ("org_id",), ("plan_id",), ("stripe_customer_id",),
            ("stripe_subscription_id",), ("status",), ("billing_cycle",),
            ("current_period_start",), ("current_period_end",),
            ("trial_end",), ("cancel_at_period_end",),
            ("created_at",), ("plan_name",), ("plan_display_name",),
        ]
        mock_cur_data.fetchall = AsyncMock(return_value=[
            (1, 10, 1, None, None, "active", "monthly", None, None, None, 0, "2025-01-01", "pro", "Pro"),
            (2, 20, 2, None, None, "active", "yearly", None, None, None, 0, "2025-02-01", "enterprise", "Enterprise"),
        ])

        mock_conn.execute = AsyncMock(side_effect=[mock_cur_count, mock_cur_data])
        mock_pool = _make_mock_pool(mock_conn)

        async def _mock_get_db_pool():
            return mock_pool

        with patch.object(admin_billing_service, "get_db_pool", side_effect=_mock_get_db_pool):
            result = await admin_billing_service.list_all_subscriptions(limit=50, offset=0)

        assert "items" in result
        assert "total" in result
        assert result["total"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["plan_name"] == "pro"

    @pytest.mark.asyncio
    async def test_status_filter_applied(self):
        """list_all_subscriptions applies status filter to queries."""
        mock_conn = AsyncMock()

        mock_cur_count = AsyncMock()
        mock_cur_count.fetchone = AsyncMock(return_value=(0,))

        mock_cur_data = AsyncMock()
        mock_cur_data.description = [
            ("id",), ("org_id",), ("plan_id",), ("stripe_customer_id",),
            ("stripe_subscription_id",), ("status",), ("billing_cycle",),
            ("current_period_start",), ("current_period_end",),
            ("trial_end",), ("cancel_at_period_end",),
            ("created_at",), ("plan_name",), ("plan_display_name",),
        ]
        mock_cur_data.fetchall = AsyncMock(return_value=[])

        mock_conn.execute = AsyncMock(side_effect=[mock_cur_count, mock_cur_data])
        mock_pool = _make_mock_pool(mock_conn)

        async def _mock_get_db_pool():
            return mock_pool

        with patch.object(admin_billing_service, "get_db_pool", side_effect=_mock_get_db_pool):
            result = await admin_billing_service.list_all_subscriptions(
                status_filter="canceled", limit=10, offset=0,
            )

        assert result["total"] == 0
        assert result["items"] == []

        # Verify the SQL included the status filter
        count_call = mock_conn.execute.call_args_list[0]
        assert "os.status = ?" in count_call[0][0]


class TestGetUserSubscriptionDetails:
    """Tests for admin_billing_service.get_user_subscription_details."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_subscription(self):
        """Returns None when user has no explicit subscription."""
        mock_repo = AsyncMock()
        mock_repo.get_org_subscription = AsyncMock(return_value=None)

        with patch.object(admin_billing_service, "_get_billing_repo", return_value=mock_repo):
            result = await admin_billing_service.get_user_subscription_details(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_subscription_dict(self):
        """Returns the subscription dict when one exists."""
        sub_data = {
            "org_id": 10,
            "plan_name": "pro",
            "status": "active",
            "billing_cycle": "monthly",
        }
        mock_repo = AsyncMock()
        mock_repo.get_org_subscription = AsyncMock(return_value=sub_data)

        with patch.object(admin_billing_service, "_get_billing_repo", return_value=mock_repo):
            result = await admin_billing_service.get_user_subscription_details(10)

        assert result == sub_data


class TestOverrideUserPlan:
    """Tests for admin_billing_service.override_user_plan."""

    @pytest.mark.asyncio
    async def test_raises_on_unknown_plan(self):
        """Raises ValueError when plan_id is not found."""
        mock_repo = AsyncMock()
        mock_repo.get_plan_by_name = AsyncMock(return_value=None)

        with (
            patch.object(admin_billing_service, "_get_billing_repo", return_value=mock_repo),
            patch.object(admin_billing_service, "get_subscription_service", return_value=AsyncMock()),
            pytest.raises(ValueError, match="not found"),
        ):
            await admin_billing_service.override_user_plan(
                10, plan_id="nonexistent", reason="test",
            )

    @pytest.mark.asyncio
    async def test_creates_subscription_when_none_exists(self):
        """Creates a new subscription when user has no existing one."""
        mock_repo = AsyncMock()
        mock_repo.get_plan_by_name = AsyncMock(return_value={"id": 2, "name": "pro"})
        mock_repo.get_org_subscription = AsyncMock(side_effect=[None, {"org_id": 10, "plan_name": "pro"}])
        mock_repo.create_org_subscription = AsyncMock()
        mock_repo.log_billing_action = AsyncMock(return_value={"id": 1})

        with (
            patch.object(admin_billing_service, "_get_billing_repo", return_value=mock_repo),
            patch.object(admin_billing_service, "get_subscription_service", return_value=AsyncMock()),
        ):
            result = await admin_billing_service.override_user_plan(
                10, plan_id="pro", reason="upgrade",
            )

        mock_repo.create_org_subscription.assert_called_once()
        assert result["plan_name"] == "pro"


class TestGrantCredits:
    """Tests for admin_billing_service.grant_credits."""

    @pytest.mark.asyncio
    async def test_raises_on_non_positive_amount(self):
        """Raises ValueError when amount is not positive."""
        with pytest.raises(ValueError, match="positive"):
            await admin_billing_service.grant_credits(
                10, amount=0, reason="test",
            )

    @pytest.mark.asyncio
    async def test_logs_credit_grant(self):
        """Logs a billing action for the credit grant."""
        mock_repo = AsyncMock()
        mock_repo.log_billing_action = AsyncMock(return_value={
            "id": 1,
            "created_at": "2025-01-01T00:00:00Z",
        })

        with patch.object(admin_billing_service, "_get_billing_repo", return_value=mock_repo):
            result = await admin_billing_service.grant_credits(
                10, amount=100, reason="promo",
            )

        assert result["user_id"] == 10
        assert result["credits_granted"] == 100
        assert result["reason"] == "promo"
        mock_repo.log_billing_action.assert_called_once()


class TestListBillingEvents:
    """Tests for admin_billing_service.list_billing_events."""

    @pytest.mark.asyncio
    async def test_returns_items_and_total(self):
        """list_billing_events returns a dict with items and total."""
        mock_conn = AsyncMock()

        mock_cur_count = AsyncMock()
        mock_cur_count.fetchone = AsyncMock(return_value=(3,))

        mock_cur_data = AsyncMock()
        mock_cur_data.description = [
            ("id",), ("org_id",), ("user_id",), ("action",),
            ("details",), ("ip_address",), ("created_at",),
        ]
        mock_cur_data.fetchall = AsyncMock(return_value=[
            (1, 10, 1, "checkout.completed", None, "127.0.0.1", "2025-01-01"),
        ])

        mock_conn.execute = AsyncMock(side_effect=[mock_cur_count, mock_cur_data])
        mock_pool = _make_mock_pool(mock_conn)

        async def _mock_get_db_pool():
            return mock_pool

        with patch.object(admin_billing_service, "get_db_pool", side_effect=_mock_get_db_pool):
            result = await admin_billing_service.list_billing_events(limit=50)

        assert "items" in result
        assert "total" in result
        assert result["total"] == 3
        assert len(result["items"]) == 1


# ---------------------------------------------------------------------------
# Endpoint-layer tests (import validation)
# ---------------------------------------------------------------------------


class TestEndpointImports:
    """Verify the admin billing endpoint module imports cleanly."""

    def test_router_importable(self):
        """The admin billing router can be imported."""
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_billing import router
        assert router is not None
        assert router.prefix == "/billing"

    def test_router_has_expected_routes(self):
        """The router has all expected route paths."""
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_billing import router

        route_paths = {route.path for route in router.routes}
        expected_paths = {
            "/billing/overview",
            "/billing/subscriptions",
            "/billing/subscriptions/{user_id}",
            "/billing/subscriptions/{user_id}/override",
            "/billing/subscriptions/{user_id}/credits",
            "/billing/events",
        }
        assert expected_paths.issubset(route_paths), (
            f"Missing routes: {expected_paths - route_paths}"
        )

    def test_router_registered_in_admin(self):
        """The billing router is included in the admin router."""
        from tldw_Server_API.app.api.v1.endpoints.admin import router as admin_router

        sub_prefixes = set()
        for route in admin_router.routes:
            path = getattr(route, "path", "")
            if "/billing" in path:
                sub_prefixes.add(path)

        # At minimum, the overview endpoint should be reachable
        assert any("/billing/overview" in p for p in sub_prefixes), (
            f"Billing routes not found in admin router. Found paths: {sub_prefixes}"
        )


class TestResponseModels:
    """Verify Pydantic response models work correctly."""

    def test_billing_overview_response_model(self):
        """BillingOverviewResponse can be instantiated with expected data."""
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_billing import BillingOverviewResponse

        resp = BillingOverviewResponse(
            billing_enabled=True,
            total_subscriptions=10,
            active_subscriptions=8,
            canceled_subscriptions=1,
            past_due_subscriptions=1,
            plan_distribution={"pro": 5, "enterprise": 3},
            mrr_estimate_usd=350,
        )
        assert resp.billing_enabled is True
        assert resp.total_subscriptions == 10

    def test_grant_credits_response_model(self):
        """GrantCreditsResponse can be instantiated with expected data."""
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_billing import GrantCreditsResponse

        resp = GrantCreditsResponse(
            user_id=10,
            credits_granted=100,
            reason="promo",
        )
        assert resp.credits_granted == 100

    def test_plan_override_request_validation(self):
        """PlanOverrideRequest validates required fields."""
        from tldw_Server_API.app.api.v1.endpoints.admin.admin_billing import PlanOverrideRequest

        req = PlanOverrideRequest(plan_id="pro", reason="testing")
        assert req.plan_id == "pro"

        with pytest.raises(Exception):
            PlanOverrideRequest(plan_id="", reason="")  # reason too short
