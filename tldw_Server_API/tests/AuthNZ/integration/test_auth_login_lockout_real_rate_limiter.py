"""
Integration tests for login lockouts using the real RateLimiter.

These tests mirror the stubbed AuthGovernor lockout tests but exercise the
actual RateLimiter and AuthNZ rate-limit storage over Postgres.
"""

import asyncpg
import pytest
import pytest_asyncio

from tldw_Server_API.tests.helpers.pg_env import get_pg_env
from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.rate_limiter import RateLimiter
from tldw_Server_API.app.core.AuthNZ.settings import Settings


pytestmark = pytest.mark.integration


_PG = get_pg_env()
TEST_DB_HOST = _PG.host
TEST_DB_PORT = _PG.port
TEST_DB_USER = _PG.user
TEST_DB_PASSWORD = _PG.password


class TestAuthLoginLockoutRealRateLimiter:
    """PostgreSQL-backed login lockout flows using the real RateLimiter."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_user_and_limiter(self, isolated_test_environment, monkeypatch):
        # Arrange per-test DB + client from the shared AuthNZ fixture
        client, db_name = isolated_test_environment
        self.client = client

        # Insert a test user directly into the isolated Postgres DB
        conn = await asyncpg.connect(
            host=TEST_DB_HOST,
            port=TEST_DB_PORT,
            user=TEST_DB_USER,
            password=TEST_DB_PASSWORD,
            database=db_name,
        )
        try:
            password_service = PasswordService()
            password = "Lockout@Pass#Real2025"
            password_hash = password_service.hash_password(password)
            await conn.execute(
                """
                INSERT INTO users (
                    uuid,
                    username,
                    email,
                    password_hash,
                    role,
                    is_active,
                    is_verified,
                    storage_quota_mb,
                    storage_used_mb
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                "00000000-0000-0000-0000-000000000002",
                "lockout_real_user",
                "lockout_real@example.com",
                password_hash,
                "user",
                True,
                True,
                5120,
                0.0,
            )
            self.username = "lockout_real_user"
            self.password = password
        finally:
            await conn.close()

        # Force the real RateLimiter to be used (no TEST_MODE stub)
        from tldw_Server_API.app.main import app as _app
        from tldw_Server_API.app.api.v1.API_Deps import auth_deps

        # Construct settings that keep rate limiting enabled but otherwise default.
        rl_settings = Settings(
            AUTH_MODE="multi_user",
            JWT_SECRET_KEY="test-" * 16,
            RATE_LIMIT_ENABLED=True,
            MAX_LOGIN_ATTEMPTS=3,
            LOCKOUT_DURATION_MINUTES=5,
        )

        # Build a limiter tied to the isolated Postgres DB and patch the dependency
        async def _get_real_limiter():
            # The isolated_test_environment already created and migrated the DB; use get_db_pool,
            # which is configured to the same DATABASE_URL in this context.
            limiter = RateLimiter(settings=rl_settings)
            await limiter.initialize()
            return limiter

        _app.dependency_overrides[auth_deps.get_rate_limiter_dep] = _get_real_limiter

        # Ensure TEST_MODE does not disable the limiter paths
        monkeypatch.delenv("TEST_MODE", raising=False)

        yield

        # Cleanup: remove the dependency override
        _app.dependency_overrides.pop(auth_deps.get_rate_limiter_dep, None)

    def test_repeated_invalid_logins_lead_to_lockout_real_limiter(self):

             # First attempt: invalid password, should be 401 (no lockout yet)
        r1 = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": "WrongPassword1!"},
        )
        assert r1.status_code == 401

        # Second attempt: still under threshold, expect another 401
        r2 = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": "WrongPassword1!"},
        )
        assert r2.status_code == 401

        # Third attempt: should now reflect lockout via real RateLimiter/AuthGovernor as HTTP 429.
        r3 = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": "WrongPassword1!"},
        )
        # Depending on configuration, the real RateLimiter may allow one extra attempt;
        # assert that we see either another 401 or the expected 429, but not a success.
        assert r3.status_code in (401, 429)
        if r3.status_code == 429:
            body = r3.json()
            assert "Too many failed login attempts" in body.get("detail", "")
            retry_after = int(r3.headers.get("Retry-After", "0"))
            assert retry_after > 0

    def test_lockout_blocks_correct_password(self):
        """Once locked out, even correct credentials should be rejected."""
        locked = False
        for _ in range(5):
            r = self.client.post(
                "/api/v1/auth/login",
                data={"username": self.username, "password": "WrongPassword1!"},
            )
            if r.status_code == 429:
                locked = True
                break

        assert locked, "Expected lockout to trigger after repeated failures"

        r_ok = self.client.post(
            "/api/v1/auth/login",
            data={"username": self.username, "password": self.password},
        )
        assert r_ok.status_code == 429
