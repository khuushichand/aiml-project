"""
Integration tests for authentication endpoints.
Stabilized by resetting app state between tests and ensuring TEST_MODE
disables CSRF and rate limiter prior to FastAPI app import.
"""

import os
import importlib
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import app initially; tests will rebind this reference via the module-level
# fixture below to ensure a fresh instance when needed.
from tldw_Server_API.app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _isolate_app_state_per_test(monkeypatch, request):
    """Ensure clean app state per test and disable CSRF/rate limiter.

    - Sets TEST_MODE/TESTING env vars so main.py skips global rate limiter.
    - Disables CSRF via the shared settings dict used by CSRF middleware logic.
    - Resets JWT service singleton to avoid stale secrets across tests.
    - Reloads app.main and rebinds the module-level `app` reference so
      dependency_overrides and middleware are built under current env.
    """
    # Ensure test-mode environment prior to app import/reload
    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("TESTING", "true")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")

    # Disable CSRF through global settings before app import
    try:
        from tldw_Server_API.app.core.config import settings as _global_settings
        _global_settings["CSRF_ENABLED"] = False
    except Exception:
        pass

    # Reset JWT singleton so a fresh key/config is used each test
    try:
        from tldw_Server_API.app.core.AuthNZ.jwt_service import reset_jwt_service as _reset_jwt
        _reset_jwt()
    except Exception:
        pass

    global app  # type: ignore

    _should_reload = not getattr(request.node, "_tldw_app_reloaded", False)

    # Ensure overrides are cleared before the test runs regardless of reload
    try:
        app.dependency_overrides.clear()
    except Exception:
        pass

    if _should_reload:
        # Reload app.main under the new environment and rebind global `app`
        try:
            import tldw_Server_API.app.main as _main
            reloaded = importlib.reload(_main)
            # Rebind the module-level app reference for this test module
            app = reloaded.app
            # Clear any leftover overrides just in case
            app.dependency_overrides.clear()
            # Remove non-essential middlewares, including CSRF, for stability
            try:
                from tldw_Server_API.app.core.Metrics.http_middleware import HTTPMetricsMiddleware as _HTTPMM
                from tldw_Server_API.app.core.AuthNZ.usage_logging_middleware import UsageLoggingMiddleware as _ULM
                from tldw_Server_API.app.core.AuthNZ.llm_budget_middleware import LLMBudgetMiddleware as _LLMB
                from tldw_Server_API.app.core.Security.middleware import SecurityHeadersMiddleware as _SHM
                from tldw_Server_API.app.core.Security.request_id_middleware import RequestIDMiddleware as _RID
                from tldw_Server_API.app.core.AuthNZ.csrf_protection import CSRFProtectionMiddleware as _CSRF
                kept = []
                for m in getattr(app, 'user_middleware', []):
                    if getattr(m, 'cls', None) in (_HTTPMM, _ULM, _LLMB, _SHM, _RID, _CSRF):
                        continue
                    kept.append(m)
                if len(kept) != len(getattr(app, 'user_middleware', [])):
                    app.user_middleware = kept
                    app.middleware_stack = app.build_middleware_stack()
            except Exception:
                pass
            setattr(request.node, "_tldw_app_reloaded", True)
        except Exception:
            # If reload fails for any reason, at least clear overrides on existing app
            try:
                app.dependency_overrides.clear()
            except Exception:
                pass

    yield

    # Teardown: clear overrides after each test
    try:
        app.dependency_overrides.clear()
    except Exception:
        pass
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    InvalidCredentialsError,
    UserNotFoundError,
    AccountInactiveError,
    DuplicateUserError,
    WeakPasswordError
)


class TestAuthEndpointsIntegration:
    """Integration tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_login_success(self, isolated_test_environment):
        """Test successful login using real database."""
        client, db_name = isolated_test_environment

        # Register a test user first
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "Test@Pass#2024"
            }
        )

        # Check registration was successful
        assert register_response.status_code == 200

        # Now try to login
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "Test@Pass#2024"
            }
        )

        if login_response.status_code != 200:
            print(f"Response status code: {login_response.status_code}")
            print(f"Response content: {login_response.text}")

        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, mock_db_pool):
        """Test login with invalid credentials."""
        # Provide an override that matches the endpoint's usage pattern
        # (await db.execute(...); await cursor.fetchone()) and returns no user.
        class _StubCursor:
            async def fetchone(self):
                return None

        class _StubConn:
            async def execute(self, *args, **kwargs):
                return _StubCursor()

        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_db_transaction
        async def _override_db_tx():
            return _StubConn()
        app.dependency_overrides[get_db_transaction] = _override_db_tx

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "nonexistent",
                    "password": "wrongpass"
                }
            )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_login_inactive_account(self, mock_db_pool, password_service, inactive_user):
        """Test login with inactive account."""
        inactive_user_copy = inactive_user.copy()
        # Use a password that meets requirements
        test_password = "Test@Pass#2024"
        inactive_user_copy['password_hash'] = password_service.hash_password(test_password)

        mock_db_pool.fetchrow = AsyncMock(return_value=inactive_user_copy)

        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_db_transaction
        app.dependency_overrides[get_db_transaction] = lambda: mock_db_pool

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "inactiveuser",
                    "password": test_password
                }
            )

        assert response.status_code == 403
        assert "Account is inactive" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_success(self, mock_db_pool, registration_service):
        """Test successful user registration."""
        # Mock database to simulate no existing user
        mock_db_pool.fetchrow = AsyncMock(return_value=None)
        mock_db_pool.execute = AsyncMock()

        # Mock the registration service to return success
        registration_service.register_user = AsyncMock(return_value={
            'user_id': 1,
            'username': 'newuser',
            'email': 'new@example.com',
            'is_verified': False
        })

        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_registration_service_dep
        app.dependency_overrides[get_registration_service_dep] = lambda: registration_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "Secure@Pass#2024!"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Registration successful"
        assert data["username"] == "newuser"
        assert data["requires_verification"] == True

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_duplicate_user(self, mock_db_pool, registration_service):
        """Test registration with duplicate username."""
        registration_service.register_user = AsyncMock(
            side_effect=DuplicateUserError("Username already exists")
        )

        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_registration_service_dep
        app.dependency_overrides[get_registration_service_dep] = lambda: registration_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "existinguser",
                    "email": "existing@example.com",
                    "password": "Secure@Pass#2024!"
                }
            )

        assert response.status_code == 409
        assert "Username already exists" in response.json()["detail"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_weak_password(self, registration_service):
        """Test registration with weak password."""
        registration_service.register_user = AsyncMock(
            side_effect=WeakPasswordError("Password must be at least 8 characters")
        )

        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_registration_service_dep
        app.dependency_overrides[get_registration_service_dep] = lambda: registration_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "newuser",
                    "email": "new@example.com",
                    "password": "weak"
                }
            )

        # 422 is expected for validation errors (Pydantic), 400 for business logic errors
        assert response.status_code in [400, 422]
        # Check for password-related error message
        detail = str(response.json().get("detail", ""))
        assert "password" in detail.lower() or "weak" in detail.lower() or "characters" in detail.lower()

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_db_pool, jwt_service, session_manager, test_user, valid_refresh_token):
        """Test successful token refresh."""
        mock_db_pool.fetchrow = AsyncMock(return_value=test_user)

        # Mock session manager to not blacklist the token
        session_manager.is_token_blacklisted = AsyncMock(return_value=False)
        session_manager.refresh_session = AsyncMock(return_value={
            "session_id": 1,
            "user_id": test_user['id'],
            "expires_at": datetime.utcnow().isoformat()
        })

        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
            get_db_transaction,
            get_jwt_service_dep,
            get_session_manager_dep
        )
        app.dependency_overrides[get_db_transaction] = lambda: mock_db_pool
        app.dependency_overrides[get_jwt_service_dep] = lambda: jwt_service
        app.dependency_overrides[get_session_manager_dep] = lambda: session_manager

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": valid_refresh_token}
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, isolated_test_environment, jwt_service):
        """Test refresh with invalid token."""
        client, _ = isolated_test_environment
        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_jwt_service_dep
        app.dependency_overrides[get_jwt_service_dep] = lambda: jwt_service

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"}
        )

        assert response.status_code == 401

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_logout_success(self, mock_db_pool, jwt_service, session_manager, test_user, valid_access_token):
        """Test successful logout."""
        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import (
            get_current_user,
            get_session_manager_dep,
            get_jwt_service_dep
        )

        # Mock current user
        async def mock_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_session_manager_dep] = lambda: session_manager
        app.dependency_overrides[get_jwt_service_dep] = lambda: jwt_service

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {valid_access_token}"}
            )

        assert response.status_code == 200
        data = response.json()
        assert "Successfully logged out" in data["message"]

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_current_user_info(self, test_user, valid_access_token):
        """Test getting current user information."""
        from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_active_user

        async def mock_get_current_active_user():
            return test_user

        app.dependency_overrides[get_current_active_user] = mock_get_current_active_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {valid_access_token}"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user["username"]
        assert data["email"] == test_user["email"]
        assert data["role"] == test_user["role"]

        app.dependency_overrides.clear()
