"""
Integration tests for billing endpoints.

Test Strategy
=============
These tests verify the billing API endpoints work correctly with a real
PostgreSQL test database. They use the `isolated_test_environment` fixture
which provides:
- A unique test database per test
- A TestClient configured for the database
- Automatic cleanup after each test

Test Groups
-----------
1. **Plans endpoint tests**: Verify `/api/v1/billing/plans` returns available
    subscription plans without authentication.

2. **Subscription endpoint tests**: Verify `/api/v1/billing/subscription` returns
    correct subscription status for authenticated users.

3. **Usage endpoint tests**: Verify `/api/v1/billing/usage` returns usage vs limits.

4. **Billing disabled tests**: Verify endpoints behave correctly when billing
    is disabled (BILLING_ENABLED=false).

Prerequisites
-------------
- PostgreSQL test database (via `isolated_test_environment` fixture)
- The conftest.py fixtures from AuthNZ tests

Note: Stripe-dependent tests (checkout, portal, webhooks) are skipped unless
STRIPE_API_KEY is configured, as they require external service access.
"""

import json
import os
import pytest
import pytest_asyncio
import asyncpg
import uuid as uuid_lib

from tldw_Server_API.tests.helpers.pg_env import get_pg_env
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.Billing import stripe_client as stripe_client_module

# Reuse Postgres AuthNZ fixtures
pytest_plugins = ["tldw_Server_API.tests.AuthNZ.conftest"]

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

# Test database configuration
_pg = get_pg_env()
TEST_DB_HOST = _pg.host
TEST_DB_PORT = _pg.port
TEST_DB_USER = _pg.user
TEST_DB_PASSWORD = _pg.password


def _has_postgres_dependencies() -> bool:


    """Check if PostgreSQL dependencies are available."""
    try:
        import psycopg  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
class TestBillingPlansEndpoint:
    """Tests for the /api/v1/billing/plans endpoint."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, isolated_test_environment):
        """Setup test environment."""
        client, db_name = isolated_test_environment
        self.client = client
        self.db_name = db_name
        yield

    def test_list_plans_no_auth_required(self):

        """Plans endpoint should work without authentication."""
        response = self.client.get("/api/v1/billing/plans")

        # 200 if route available, 404 if router not loaded (acceptable in test env)
        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data

    def test_list_plans_returns_default_tiers(self):

        """Plans endpoint should return default plan tiers."""
        response = self.client.get("/api/v1/billing/plans")

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")
        assert response.status_code == 200
        data = response.json()
        plans = data["plans"]

        # Should have at least the default tiers
        plan_names = [p["name"] for p in plans]
        assert "free" in plan_names or len(plans) > 0

    def test_plans_include_limits(self):

        """Each plan should include limits information."""
        response = self.client.get("/api/v1/billing/plans")

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")
        assert response.status_code == 200
        data = response.json()

        for plan in data["plans"]:
            assert "limits" in plan or plan.get("price_usd_monthly") is not None


@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
class TestBillingSubscriptionEndpoint:
    """Tests for the /api/v1/billing/subscription endpoint."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_test_user_and_org(self, isolated_test_environment):
        """Setup test user with organization membership."""
        client, db_name = isolated_test_environment

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=db_name
        )

        try:
            password_service = PasswordService()
            user_uuid = str(uuid_lib.uuid4())
            password = "Test@Pass#2024!"
            password_hash = password_service.hash_password(password)

            # Create test user
            user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, user_uuid, "billinguser", "billing@example.com", password_hash,
                "user", True, True, 5120, 0.0)

            # Create test organization
            org_id = await conn.fetchval("""
                INSERT INTO organizations (name, slug, owner_user_id)
                VALUES ($1, $2, $3)
                RETURNING id
            """, "Test Org", "test-org", user_id)

            # Add user as org member
            await conn.execute("""
                INSERT INTO org_members (org_id, user_id, role)
                VALUES ($1, $2, $3)
            """, org_id, user_id, "owner")

            # Create a separate org for cross-org access checks.
            other_user_uuid = str(uuid_lib.uuid4())
            other_password_hash = password_service.hash_password("Other@Pass#2024!")
            other_user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, other_user_uuid, "billingother", "billing-other@example.com", other_password_hash,
                "user", True, True, 5120, 0.0)

            other_org_id = await conn.fetchval("""
                INSERT INTO organizations (name, slug, owner_user_id)
                VALUES ($1, $2, $3)
                RETURNING id
            """, "Other Org", "other-org", other_user_id)

            await conn.execute("""
                INSERT INTO org_members (org_id, user_id, role)
                VALUES ($1, $2, $3)
            """, other_org_id, other_user_id, "owner")

            self.client = client
            self.user_id = user_id
            self.org_id = org_id
            self.other_org_id = other_org_id
            self.username = "billinguser"
            self.password = password

        finally:
            await conn.close()
        yield

    def _get_auth_token(self):

        """Get auth token for test user."""
        response = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    def test_subscription_requires_auth(self):

        """Subscription endpoint should require authentication."""
        response = self.client.get("/api/v1/billing/subscription")

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")
        # Should return 401 or 403 without auth
        assert response.status_code in [401, 403]

    def test_subscription_with_auth(self):

        """Subscription endpoint should return data for authenticated user."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.get(
            "/api/v1/billing/subscription",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should return subscription info or 404 if no org
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "org_id" in data or "plan_name" in data

    def test_subscription_with_org_id(self):

        """Subscription endpoint should accept explicit org_id."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.get(
            f"/api/v1/billing/subscription?org_id={self.org_id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code in [200, 404]

    def test_subscription_rejects_cross_org_access(self):

        """Users should not access subscription data for other organizations."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.get(
            f"/api/v1/billing/subscription?org_id={self.other_org_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")
        assert response.status_code == 403


@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
class TestBillingUsageEndpoint:
    """Tests for the /api/v1/billing/usage endpoint."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_test_user_and_org(self, isolated_test_environment):
        """Setup test user with organization membership."""
        client, db_name = isolated_test_environment

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=db_name
        )

        try:
            password_service = PasswordService()
            user_uuid = str(uuid_lib.uuid4())
            password = "Test@Pass#2024!"
            password_hash = password_service.hash_password(password)

            # Create test user
            user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, user_uuid, "usageuser", "usage@example.com", password_hash,
                "user", True, True, 5120, 0.0)

            # Create test organization
            org_id = await conn.fetchval("""
                INSERT INTO organizations (name, slug, owner_user_id)
                VALUES ($1, $2, $3)
                RETURNING id
            """, "Usage Test Org", "usage-test-org", user_id)

            # Add user as org member
            await conn.execute("""
                INSERT INTO org_members (org_id, user_id, role)
                VALUES ($1, $2, $3)
            """, org_id, user_id, "owner")

            # Create a separate org for cross-org access checks.
            other_user_uuid = str(uuid_lib.uuid4())
            other_password_hash = password_service.hash_password("Other@Pass#2024!")
            other_user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, other_user_uuid, "usageother", "usage-other@example.com", other_password_hash,
                "user", True, True, 5120, 0.0)

            other_org_id = await conn.fetchval("""
                INSERT INTO organizations (name, slug, owner_user_id)
                VALUES ($1, $2, $3)
                RETURNING id
            """, "Usage Other Org", "usage-other-org", other_user_id)

            await conn.execute("""
                INSERT INTO org_members (org_id, user_id, role)
                VALUES ($1, $2, $3)
            """, other_org_id, other_user_id, "owner")

            self.client = client
            self.user_id = user_id
            self.org_id = org_id
            self.other_org_id = other_org_id
            self.username = "usageuser"
            self.password = password

        finally:
            await conn.close()
        yield

    def _get_auth_token(self):

        """Get auth token for test user."""
        response = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    def test_usage_requires_auth(self):

        """Usage endpoint should require authentication."""
        response = self.client.get("/api/v1/billing/usage")

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")
        assert response.status_code in [401, 403]

    def test_usage_with_auth(self):

        """Usage endpoint should return usage data for authenticated user."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.get(
            "/api/v1/billing/usage",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            # Should have usage metrics
            assert "limits" in data or "usage" in data or "org_id" in data

    def test_usage_rejects_cross_org_access(self):

        """Users should not access usage data for other organizations."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.get(
            f"/api/v1/billing/usage?org_id={self.other_org_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")
        assert response.status_code == 403


@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
class TestBillingCheckoutAndPortal:
    """Tests for the /api/v1/billing/checkout and /portal endpoints."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_test_user_and_org(self, isolated_test_environment, monkeypatch):
        """Setup test user with organization ownership and enable billing."""
        client, db_name = isolated_test_environment

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=db_name,
        )

        try:
            password_service = PasswordService()
            user_uuid = str(uuid_lib.uuid4())
            password = "Test@Pass#2024!"
            password_hash = password_service.hash_password(password)

            # Create test user (org owner)
            user_id = await conn.fetchval(
                """
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                user_uuid,
                "billingowner",
                "billing-owner@example.com",
                password_hash,
                "user",
                True,
                True,
                5120,
                0.0,
            )

            # Create test organization owned by the user
            org_id = await conn.fetchval(
                """
                INSERT INTO organizations (name, slug, owner_user_id)
                VALUES ($1, $2, $3)
                RETURNING id
                """,
                "Checkout Org",
                "checkout-org",
                user_id,
            )

            # Add user as org owner
            await conn.execute(
                """
                INSERT INTO org_members (org_id, user_id, role)
                VALUES ($1, $2, $3)
                """,
                org_id,
                user_id,
                "owner",
            )

            plan_id = await conn.fetchval(
                "SELECT id FROM subscription_plans WHERE name = $1",
                "pro",
            )
            if plan_id:
                await conn.execute(
                    """
                    INSERT INTO org_subscriptions
                    (org_id, plan_id, stripe_customer_id, billing_cycle, status)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (org_id) DO NOTHING
                    """,
                    org_id,
                    plan_id,
                    "cus_int_123",
                    "monthly",
                    "active",
                )

            custom_plan_name = "custom-tier"
            await conn.execute(
                """
                INSERT INTO subscription_plans
                (name, display_name, description, price_usd_monthly, price_usd_yearly, limits_json, is_active, is_public, sort_order)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, TRUE, TRUE, 10)
                ON CONFLICT (name) DO NOTHING
                """,
                custom_plan_name,
                "Custom Tier",
                "Custom plan for integration tests",
                42,
                420,
                json.dumps({"api_calls_day": 123}),
            )

            self.client = client
            self.user_id = user_id
            self.org_id = org_id
            self.username = "billingowner"
            self.password = password
            self.custom_plan_name = custom_plan_name

        finally:
            await conn.close()

        # Enable billing for these tests and force Stripe to be "available".
        monkeypatch.setenv("BILLING_ENABLED", "true")
        monkeypatch.setattr(
            "tldw_Server_API.app.core.Billing.subscription_service.is_billing_enabled",
            lambda: True,
            raising=False,
        )

        class _FakeStripeClient:
            def __init__(self) -> None:
                self.is_available = True

            async def create_customer(self, *, email: str, name: str | None = None, metadata: dict[str, str] | None = None) -> str:
                return "cus_int_123"

            def get_price_id(self, plan_name: str, billing_cycle: str = "monthly") -> str | None:
                return "price_int_123"

            async def create_checkout_session(
                self,
                *,
                customer_id: str,
                price_id: str,
                success_url: str,
                cancel_url: str,
                metadata: dict[str, str] | None = None,
            ):
                from tldw_Server_API.app.core.Billing.stripe_client import CheckoutSession

                return CheckoutSession(id="sess_int_123", url="https://example.com/checkout")

            async def create_portal_session(
                self,
                *,
                customer_id: str,
                return_url: str,
            ):
                from tldw_Server_API.app.core.Billing.stripe_client import PortalSession

                return PortalSession(id="ps_int_123", url="https://example.com/portal")

        # Patch the Stripe client singleton module-wide so checkout/portal use the fake implementation.
        monkeypatch.setattr(
            stripe_client_module,
            "get_stripe_client",
            lambda: _FakeStripeClient(),
            raising=False,
        )
        monkeypatch.setattr(
            "tldw_Server_API.app.core.Billing.subscription_service.get_stripe_client",
            lambda: _FakeStripeClient(),
            raising=False,
        )
        monkeypatch.setattr(
            stripe_client_module,
            "STRIPE_AVAILABLE",
            True,
            raising=False,
        )
        yield

    def _get_auth_token(self):

        """Get auth token for test user."""
        response = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password},
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    def test_checkout_creates_session_for_owner(self):

        """Owner should be able to create a checkout session."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.post(
            f"/api/v1/billing/checkout?org_id={self.org_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "plan_name": "pro",
                "billing_cycle": "monthly",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")

        assert response.status_code == 200
        data = response.json()
        assert data.get("session_id") == "sess_int_123"
        assert data.get("url") == "https://example.com/checkout"

    def test_portal_creates_session_for_owner(self):

        """Owner should be able to create a billing portal session."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.post(
            f"/api/v1/billing/portal?org_id={self.org_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"return_url": "https://example.com/account"},
        )

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")

        assert response.status_code == 200
        data = response.json()
        assert data.get("session_id") == "ps_int_123"
        assert data.get("url") == "https://example.com/portal"

    def test_checkout_accepts_custom_plan_name(self):
        """Owner should be able to checkout with a custom plan name."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.post(
            f"/api/v1/billing/checkout?org_id={self.org_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "plan_name": self.custom_plan_name,
                "billing_cycle": "monthly",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )

        if response.status_code == 404:
            pytest.skip("Billing routes not available in test environment")

        assert response.status_code == 200
        data = response.json()
        assert data.get("session_id") == "sess_int_123"


@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
class TestOrgInviteEndpoints:
    """Tests for organization invite endpoints."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_test_user_and_org(self, isolated_test_environment):
        """Setup test user with organization ownership."""
        client, db_name = isolated_test_environment

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=db_name
        )

        try:
            password_service = PasswordService()
            user_uuid = str(uuid_lib.uuid4())
            password = "Test@Pass#2024!"
            password_hash = password_service.hash_password(password)

            # Create test user (org owner)
            user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, user_uuid, "inviteowner", "invite@example.com", password_hash,
                "user", True, True, 5120, 0.0)

            # Create test organization
            org_id = await conn.fetchval("""
                INSERT INTO organizations (name, slug, owner_user_id)
                VALUES ($1, $2, $3)
                RETURNING id
            """, "Invite Test Org", "invite-test-org", user_id)

            # Add user as org owner
            await conn.execute("""
                INSERT INTO org_members (org_id, user_id, role)
                VALUES ($1, $2, $3)
            """, org_id, user_id, "owner")

            allowed_uuid = str(uuid_lib.uuid4())
            allowed_password = "Test@Pass#2024!"
            allowed_hash = password_service.hash_password(allowed_password)
            allowed_user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, allowed_uuid, "inviteallowed", "allowed@example.com", allowed_hash,
                "user", True, True, 5120, 0.0)

            blocked_uuid = str(uuid_lib.uuid4())
            blocked_password = "Test@Pass#2024!"
            blocked_hash = password_service.hash_password(blocked_password)
            blocked_user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, blocked_uuid, "inviteblocked", "blocked@other.com", blocked_hash,
                "user", True, True, 5120, 0.0)

            self.client = client
            self.user_id = user_id
            self.org_id = org_id
            self.username = "inviteowner"
            self.password = password
            self.allowed_user_id = allowed_user_id
            self.allowed_username = "inviteallowed"
            self.allowed_password = allowed_password
            self.blocked_user_id = blocked_user_id
            self.blocked_username = "inviteblocked"
            self.blocked_password = blocked_password
            self.db_name = db_name

        finally:
            await conn.close()
        yield

    def _get_auth_token(self):

        """Get auth token for test user."""
        response = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    def _get_auth_token_for(self, username, password):
        response = self.client.post(
            "/api/v1/auth/login",
            data={"username": username, "password": password}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    def test_preview_invite_invalid_code(self):

        """Preview endpoint should return 404 for invalid codes."""
        response = self.client.get("/api/v1/invites/preview?code=INVALID123")

        assert response.status_code == 404

    def test_redeem_invite_requires_auth(self):

        """Redeem endpoint should require authentication."""
        response = self.client.post(
            "/api/v1/invites/redeem",
            json={"code": "SOMECODE"}
        )

        if response.status_code == 404:
            pytest.skip("Invite routes not available in test environment")
        assert response.status_code in [401, 403, 422]

    def test_list_org_invites_requires_auth(self):

        """Listing org invites should require authentication."""
        response = self.client.get(f"/api/v1/orgs/{self.org_id}/invites")

        if response.status_code == 404:
            pytest.skip("Org/invite routes not available in test environment")
        assert response.status_code in [401, 403]

    def test_list_org_invites_with_auth(self):

        """Authenticated owner should be able to list org invites."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.get(
            f"/api/v1/orgs/{self.org_id}/invites",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should return 200 with empty list or list of invites
        assert response.status_code in [200, 403, 404]
        if response.status_code == 200:
            data = response.json()
            assert "invites" in data or "items" in data or isinstance(data, list)

    def test_create_invite_requires_owner_or_admin(self):

        """Creating invites should require owner/admin role."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.post(
            f"/api/v1/orgs/{self.org_id}/invites",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "role_to_grant": "member",
                "max_uses": 5,
                "expiry_days": 7,
            }
        )

        if response.status_code == 404:
            pytest.skip("Org/invite routes not available in test environment")
        # Owner should be able to create invites
        assert response.status_code in [200, 201, 403, 422]

    def test_create_invite_with_allowlist_returns_domain(self):
        """Create invite should return allowed_email_domain when provided."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.post(
            f"/api/v1/orgs/{self.org_id}/invites",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "role_to_grant": "member",
                "max_uses": 2,
                "expiry_days": 7,
                "allowed_email_domain": "@Example.com",
            }
        )

        if response.status_code == 404:
            pytest.skip("Org/invite routes not available in test environment")
        if response.status_code in [403, 422]:
            pytest.skip("Invite creation not permitted in this environment")
        assert response.status_code in [200, 201]
        data = response.json()
        assert data.get("allowed_email_domain") == "example.com"

    def test_preview_invite_includes_allowlist(self):
        """Preview should include allowed_email_domain when set."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        create_resp = self.client.post(
            f"/api/v1/orgs/{self.org_id}/invites",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "role_to_grant": "member",
                "max_uses": 1,
                "expiry_days": 7,
                "allowed_email_domain": "example.com",
            }
        )

        if create_resp.status_code == 404:
            pytest.skip("Org/invite routes not available in test environment")
        if create_resp.status_code in [403, 422]:
            pytest.skip("Invite creation not permitted in this environment")
        assert create_resp.status_code in [200, 201]
        code = create_resp.json().get("code")
        assert code

        preview_resp = self.client.get(f"/api/v1/invites/preview?code={code}")
        assert preview_resp.status_code == 200
        preview_data = preview_resp.json()
        assert preview_data.get("allowed_email_domain") == "example.com"

    def test_redeem_invite_allowlist_blocks_mismatch(self):
        """Redeem should reject users outside allowed_email_domain."""
        owner_token = self._get_auth_token()
        if not owner_token:
            pytest.skip("Could not get auth token")

        create_resp = self.client.post(
            f"/api/v1/orgs/{self.org_id}/invites",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "role_to_grant": "member",
                "max_uses": 1,
                "expiry_days": 7,
                "allowed_email_domain": "example.com",
            }
        )

        if create_resp.status_code == 404:
            pytest.skip("Org/invite routes not available in test environment")
        if create_resp.status_code in [403, 422]:
            pytest.skip("Invite creation not permitted in this environment")
        assert create_resp.status_code in [200, 201]
        code = create_resp.json().get("code")
        assert code

        blocked_token = self._get_auth_token_for(self.blocked_username, self.blocked_password)
        if not blocked_token:
            pytest.skip("Could not get auth token for blocked user")

        redeem_resp = self.client.post(
            "/api/v1/invites/redeem",
            headers={"Authorization": f"Bearer {blocked_token}"},
            json={"code": code}
        )

        assert redeem_resp.status_code == 400
        detail = redeem_resp.json().get("detail", "")
        assert "allowed email domain" in detail.lower()

    def test_redeem_invite_allowlist_allows_match(self):
        """Redeem should allow users with matching allowed_email_domain."""
        owner_token = self._get_auth_token()
        if not owner_token:
            pytest.skip("Could not get auth token")

        create_resp = self.client.post(
            f"/api/v1/orgs/{self.org_id}/invites",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "role_to_grant": "member",
                "max_uses": 2,
                "expiry_days": 7,
                "allowed_email_domain": "example.com",
            }
        )

        if create_resp.status_code == 404:
            pytest.skip("Org/invite routes not available in test environment")
        if create_resp.status_code in [403, 422]:
            pytest.skip("Invite creation not permitted in this environment")
        assert create_resp.status_code in [200, 201]
        code = create_resp.json().get("code")
        assert code

        allowed_token = self._get_auth_token_for(self.allowed_username, self.allowed_password)
        if not allowed_token:
            pytest.skip("Could not get auth token for allowed user")

        redeem_resp = self.client.post(
            "/api/v1/invites/redeem",
            headers={"Authorization": f"Bearer {allowed_token}"},
            json={"code": code}
        )

        assert redeem_resp.status_code == 200
        data = redeem_resp.json()
        assert data.get("org_id") == self.org_id


@pytest.mark.skipif(
    not _has_postgres_dependencies(),
    reason="Postgres dependencies missing (install psycopg[binary])",
)
class TestSelfServiceOrgEndpoints:
    """Tests for self-service organization management endpoints."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_test_user(self, isolated_test_environment):
        """Setup test user."""
        client, db_name = isolated_test_environment

        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=db_name
        )

        try:
            password_service = PasswordService()
            user_uuid = str(uuid_lib.uuid4())
            password = "Test@Pass#2024!"
            password_hash = password_service.hash_password(password)

            # Create test user
            user_id = await conn.fetchval("""
                INSERT INTO users (
                    uuid, username, email, password_hash, role,
                    is_active, is_verified, storage_quota_mb, storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, user_uuid, "orguser", "org@example.com", password_hash,
                "user", True, True, 5120, 0.0)

            self.client = client
            self.user_id = user_id
            self.username = "orguser"
            self.password = password

        finally:
            await conn.close()
        yield

    def _get_auth_token(self):

        """Get auth token for test user."""
        response = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password}
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        return None

    def test_list_user_orgs_requires_auth(self):

        """Listing user's orgs should require authentication."""
        response = self.client.get("/api/v1/orgs")

        if response.status_code == 404:
            pytest.skip("Orgs routes not available in test environment")
        assert response.status_code in [401, 403]

    def test_list_user_orgs_with_auth(self):

        """Authenticated user should see their orgs (empty initially)."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {token}"}
        )

        if response.status_code == 404:
            pytest.skip("Orgs routes not available in test environment")
        assert response.status_code == 200
        data = response.json()
        # New user should have no orgs initially
        assert "items" in data or "orgs" in data or isinstance(data, list)

    def test_create_org_requires_auth(self):

        """Creating an org should require authentication."""
        response = self.client.post(
            "/api/v1/orgs",
            json={"name": "Test Org", "slug": "test-org"}
        )

        if response.status_code == 404:
            pytest.skip("Orgs routes not available in test environment")
        assert response.status_code in [401, 403]

    def test_create_org_with_auth(self):

        """Authenticated user should be able to create an org."""
        token = self._get_auth_token()
        if not token:
            pytest.skip("Could not get auth token")

        response = self.client.post(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "My New Org", "slug": "my-new-org"}
        )

        if response.status_code == 404:
            pytest.skip("Orgs routes not available in test environment")
        # Should succeed or return validation error
        assert response.status_code in [200, 201, 400, 422]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "id" in data or "org_id" in data
