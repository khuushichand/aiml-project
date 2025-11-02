"""
Integration tests for authentication endpoints using real database.
"""

import os

import pytest
pytestmark = pytest.mark.integration
import asyncio
from datetime import datetime, timedelta
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.token_blacklist import get_token_blacklist


class TestAuthEndpointsIntegration:
    """Integration tests for authentication endpoints with real database."""

    @pytest.mark.asyncio
    async def test_login_success(self, isolated_test_environment):
        """Test successful login."""
        client, db_name = isolated_test_environment

        # Register a user first
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "MyS3cur3P@ssw0rd!"
            }
        )
        assert register_response.status_code in [200, 201]

        # Login with correct credentials
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "loginuser",
                "password": "MyS3cur3P@ssw0rd!"
            }
        )

        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, isolated_test_environment):
        """Test login with invalid credentials."""
        client, db_name = isolated_test_environment

        # Try to login with non-existent user
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent",
                "password": "wrongpass"
            }
        )

        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_inactive_account(self, isolated_test_environment):
        """Test login with inactive account."""
        client, db_name = isolated_test_environment

        # For this test, we need to create an inactive user
        # Since we can't directly create inactive users via API,
        # we'll need to use database connection
        import asyncpg
        import uuid
        from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService

        # Connect to test database
        _dsn = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
        _host=_port=_user=_password=None
        if _dsn:
            try:
                from urllib.parse import urlparse
                _p = urlparse(_dsn)
                if _p.scheme.startswith("postgres"):
                    _host = _p.hostname or None
                    _port = int(_p.port) if _p.port else None
                    _user = _p.username or None
                    _password = _p.password or None
            except Exception:
                pass
        test_host = _host or os.getenv("TEST_DB_HOST", "localhost")
        test_port = int(_port or int(os.getenv("TEST_DB_PORT", "5432")))
        test_user = _user or os.getenv("TEST_DB_USER", "tldw_user")
        test_password = _password or os.getenv("TEST_DB_PASSWORD", "TestPassword123!")

        conn = await asyncpg.connect(
            host=test_host,
            port=test_port,
            user=test_user,
            password=test_password,
            database=db_name
        )

        try:
            # Create inactive user directly in database
            password_service = PasswordService()
            user_uuid = str(uuid.uuid4())
            password_hash = password_service.hash_password("MyS3cur3P@ssw0rd!")

            await conn.execute("""
                INSERT INTO users (uuid, username, email, password_hash, role, is_active, is_verified)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, user_uuid, "inactiveuser", "inactive@example.com", password_hash, "user", False, True)
        finally:
            await conn.close()

        # Try to login with inactive account
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "inactiveuser",
                "password": "MyS3cur3P@ssw0rd!"
            }
        )

        # The response could be 401 or 403 depending on implementation
        # Some systems return 401 to avoid leaking account status information
        assert response.status_code in [401, 403]
        detail = response.json().get("detail", "").lower()
        # Check for either inactive account message or generic auth failure
        assert "inactive" in detail or "incorrect" in detail or "unauthorized" in detail

    @pytest.mark.asyncio
    async def test_register_success(self, isolated_test_environment):
        """Test successful user registration."""
        client, db_name = isolated_test_environment

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "S3cur3P@ssw0rd2024!"
            }
        )
        # Debug/diagnostics: print status, payload, and diagnostic headers
        try:
            payload = response.json()
        except Exception:
            payload = {"raw": response.text}
        diag_headers = {k: v for k, v in response.headers.items() if k.startswith("X-TLDW-")}
        # Avoid printing diagnostics in CI; headers are asserted below when present

        # Assert diagnostics to ensure correct runtime wiring (conditionally present)
        db_hdr = response.headers.get("X-TLDW-DB")
        if db_hdr is not None:
            assert db_hdr == "postgres"
        csrf_hdr = response.headers.get("X-TLDW-CSRF-Enabled")
        if csrf_hdr is not None:
            assert csrf_hdr == "false"
        dur_hdr = response.headers.get("X-TLDW-Register-Duration-ms")
        if dur_hdr is not None:
            dur_ms = int(dur_hdr or 0)
            assert dur_ms >= 0 and dur_ms < 5000
        assert response.status_code in [200, 201]
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@example.com"
        assert "user_id" in data or "id" in data

        # Verify can login with new account
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "newuser",
                "password": "S3cur3P@ssw0rd2024!"
            }
        )
        assert login_response.status_code == 200

    @pytest.mark.asyncio
    async def test_register_duplicate_user(self, isolated_test_environment):
        """Test registration with duplicate username."""
        client, db_name = isolated_test_environment

        # Register first user with a secure password (avoiding sequential characters)
        first_response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "duplicateuser",
                "email": "first@example.com",
                "password": "MyS3cur3P@ssw0rd!"  # Avoid sequential patterns
            }
        )
        # First registration should succeed
        assert first_response.status_code in [200, 201], f"First registration failed: {first_response.json()}"

        # Try to register with same username
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "duplicateuser",
                "email": "second@example.com",
                "password": "An0th3rS3cur3P@ss!"  # Different password
            }
        )

        # Second registration should fail due to duplicate username
        assert response.status_code in [400, 409], f"Expected duplicate error, got: {response.status_code} - {response.json()}"
        detail = response.json().get("detail", "")
        assert any(word in detail.lower() for word in ["already", "duplicate", "exists"]), f"Expected duplicate error message, got: {detail}"

    @pytest.mark.asyncio
    async def test_register_weak_password(self, isolated_test_environment):
        """Test registration with weak password."""
        client, db_name = isolated_test_environment

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "weakpassuser",
                "email": "weak@example.com",
                "password": "weak"
            }
        )

        # Should get validation error for weak password
        assert response.status_code in [400, 422]
        detail = str(response.json().get("detail", ""))
        assert "password" in detail.lower() or "weak" in detail.lower() or "characters" in detail.lower()

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, isolated_test_environment):
        """Test successful token refresh."""
        client, db_name = isolated_test_environment

        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "refreshuser",
                "email": "refresh@example.com",
                "password": "R3fr3shP@ssw0rd!"
            }
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "refreshuser",
                "password": "R3fr3shP@ssw0rd!"
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, isolated_test_environment):
        """Test refresh with invalid token."""
        client, db_name = isolated_test_environment

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_rotation_enforced(self, isolated_test_environment):
        """Refresh rotates refresh token when enabled and rejects the old one."""
        client, db_name = isolated_test_environment

        # Ensure rotation is enabled via default settings (default True), then register/login
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "rotuser",
                "email": "rot@example.com",
                "password": "R0t@t10nP@ss!"
            }
        )

        login_resp = client.post(
            "/api/v1/auth/login",
            data={
                "username": "rotuser",
                "password": "R0t@t10nP@ss!"
            }
        )
        assert login_resp.status_code == 200
        first_refresh = login_resp.json()["refresh_token"]

        # First refresh
        r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
        assert r1.status_code == 200
        r1_json = r1.json()
        assert "refresh_token" in r1_json
        new_refresh = r1_json["refresh_token"]
        assert new_refresh and new_refresh != first_refresh

        # Old refresh token should now be rejected
        r_old = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
        assert r_old.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_success(self, isolated_test_environment):
        """Test successful logout."""
        client, db_name = isolated_test_environment

        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "logoutuser",
                "email": "logout@example.com",
                "password": "L0g0utP@ssw0rd!"
            }
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "logoutuser",
                "password": "L0g0utP@ssw0rd!"
            }
        )
        tokens = login_response.json()
        token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        jwt_service = JWTService()
        access_jti = jwt_service.extract_jti(token)

        # Logout
        logout_response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert logout_response.status_code == 200
        assert "logged out" in logout_response.json()["message"].lower()

        # Access token should now be blacklisted
        if access_jti:
            blacklist = get_token_blacklist()
            assert await blacklist.is_blacklisted(access_jti)

        # Token should no longer grant access
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 401
        # Refresh token should fail too
        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_all_devices_blacklists_tokens(self, isolated_test_environment):
        """Logout from all devices blacklists stored JTIs without decrypting tokens."""
        client, db_name = isolated_test_environment

        client.post(
            "/api/v1/auth/register",
            json={
                "username": "masslogout",
                "email": "masslogout@example.com",
                "password": "MassL0goutP@ss!"
            }
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "masslogout",
                "password": "MassL0goutP@ss!"
            }
        )
        tokens = login_response.json()
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]

        jwt_service = JWTService()
        access_jti = jwt_service.extract_jti(access_token)
        refresh_jti = jwt_service.extract_jti(refresh_token)

        logout_response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"all_devices": True}
        )
        assert logout_response.status_code == 200

        blacklist = get_token_blacklist()
        if access_jti:
            assert await blacklist.is_blacklisted(access_jti)
        if refresh_jti:
            assert await blacklist.is_blacklisted(refresh_jti)

        # Both access and refresh should be rejected
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert me_response.status_code == 401

        refresh_resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_info(self, isolated_test_environment):
        """Test getting current user information."""
        client, db_name = isolated_test_environment

        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "currentuser",
                "email": "current@example.com",
                "password": "Curr3ntP@ssw0rd!"
            }
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "currentuser",
                "password": "Curr3ntP@ssw0rd!"
            }
        )
        token = login_response.json()["access_token"]

        # Get current user info
        user_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert user_response.status_code == 200
        data = user_response.json()
        assert data["username"] == "currentuser"
        assert data["email"] == "current@example.com"
        assert data["role"] == "user"


class TestAuthEndpointsValidation:
    """Validation tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, isolated_test_environment):
        """Test registration with invalid email format."""
        client, db_name = isolated_test_environment

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "invalidemail",
                "email": "not-an-email",
                "password": "V@lidP@ssw0rd2024!"
            }
        )

        # Should get validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, isolated_test_environment):
        """Test registration with missing fields."""
        client, db_name = isolated_test_environment

        # Missing password
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "missingpass",
                "email": "missing@example.com"
            }
        )
        assert response.status_code == 422

        # Missing email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "missingemail",
                "password": "V@lidP@ssw0rd2024!"
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_credentials(self, isolated_test_environment):
        """Test login with missing credentials."""
        client, db_name = isolated_test_environment

        # Missing password
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "user"}
        )
        assert response.status_code == 422

        # Missing username
        response = client.post(
            "/api/v1/auth/login",
            data={"password": "pass"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_multiple_login_sessions(self, isolated_test_environment):
        """Test creating multiple login sessions for same user."""
        client, db_name = isolated_test_environment

        # Register user
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "multiuser",
                "email": "multi@example.com",
                "password": "Mult1P@ssw0rd!"
            }
        )

        # Login multiple times
        tokens = []
        for i in range(3):
            response = client.post(
                "/api/v1/auth/login",
                data={
                    "username": "multiuser",
                    "password": "Mult1P@ssw0rd!"
                }
            )
            assert response.status_code == 200
            tokens.append(response.json()["access_token"])

        # All tokens should be valid
        for token in tokens:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
