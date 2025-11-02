"""
Unit tests for JWT service.
"""

import pytest
from jose import jwt

from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import Settings
from tldw_Server_API.app.core.AuthNZ.exceptions import (
    InvalidTokenError,
    TokenExpiredError
)


class TestJWTServiceUnit:
    """Unit tests for JWT service."""

    def test_create_access_token(self, jwt_service):
        """Test creating an access token."""
        token = jwt_service.create_access_token(
            user_id=1,
            username="testuser",
            role="user"
        )

        assert token is not None
        assert isinstance(token, str)

        # Decode and verify
        payload = jwt.decode(
            token,
            jwt_service.settings.JWT_SECRET_KEY,
            algorithms=[jwt_service.settings.JWT_ALGORITHM]
        )

        assert payload["sub"] == "1"  # JWT service stores user_id as string in 'sub'
        assert payload["username"] == "testuser"
        assert payload["role"] == "user"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_create_refresh_token(self, jwt_service):
        """Test creating a refresh token."""
        token = jwt_service.create_refresh_token(user_id=1, username="testuser")

        assert token is not None
        assert isinstance(token, str)

        # Decode and verify
        payload = jwt.decode(
            token,
            jwt_service.settings.JWT_SECRET_KEY,
            algorithms=[jwt_service.settings.JWT_ALGORITHM]
        )

        assert payload["sub"] == "1"  # JWT service stores user_id as string in 'sub'
        assert payload["type"] == "refresh"
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload

    def test_decode_access_token_valid(self, jwt_service):
        """Test decoding a valid access token."""
        token = jwt_service.create_access_token(
            user_id=1,
            username="testuser",
            role="user"
        )

        payload = jwt_service.decode_access_token(token)

        assert payload["sub"] == "1"  # JWT service stores user_id as string in 'sub'
        assert payload["username"] == "testuser"
        assert payload["role"] == "user"
        assert payload["type"] == "access"

    def test_decode_access_token_expired(self, jwt_service):
        """Test decoding an expired access token."""
        # Create expired token
        original_expire = jwt_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES
        jwt_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES = -1

        token = jwt_service.create_access_token(
            user_id=1,
            username="testuser",
            role="user"
        )

        jwt_service.settings.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire

        with pytest.raises(TokenExpiredError):
            jwt_service.decode_access_token(token)

    def test_decode_access_token_invalid(self, jwt_service):
        """Test decoding an invalid access token."""
        with pytest.raises(InvalidTokenError):
            jwt_service.decode_access_token("invalid.token.here")

    def test_decode_refresh_token_as_access(self, jwt_service):
        """Test that refresh tokens cannot be used as access tokens."""
        refresh_token = jwt_service.create_refresh_token(user_id=1, username="testuser")

        with pytest.raises(InvalidTokenError, match="Invalid token type"):
            jwt_service.decode_access_token(refresh_token)

    def test_decode_refresh_token_valid(self, jwt_service):
        """Test decoding a valid refresh token."""
        token = jwt_service.create_refresh_token(user_id=1, username="testuser")

        payload = jwt_service.decode_refresh_token(token)

        assert payload["sub"] == "1"  # JWT service stores user_id as string in 'sub'
        assert payload["type"] == "refresh"

    def test_token_with_additional_claims(self, jwt_service):
        """Test creating tokens with additional claims."""
        token = jwt_service.create_access_token(
            user_id=1,
            username="testuser",
            role="user",
            additional_claims={
                "session_id": "session-123",
                "custom_claim": "custom_value"
            }
        )

        payload = jwt_service.decode_access_token(token)

        assert payload["session_id"] == "session-123"
        assert payload["custom_claim"] == "custom_value"

    def test_issuer_audience_enforced(self):
        """Ensure tokens with wrong/missing iss/aud fail and correct ones pass (HS)."""
        settings = Settings(
            AUTH_MODE="multi_user",
            JWT_SECRET_KEY="test-key-that-is-at-least-32-characters-long",
            JWT_ALGORITHM="HS256",
            JWT_ISSUER="tldw.test",
            JWT_AUDIENCE="tldw.clients",
            ACCESS_TOKEN_EXPIRE_MINUTES=5,
            REFRESH_TOKEN_EXPIRE_DAYS=7,
            SESSION_CLEANUP_INTERVAL_HOURS=24,
            SESSION_MAX_AGE_DAYS=30,
            RATE_LIMIT_ENABLED=False,
            PASSWORD_MIN_LENGTH=8,
            PASSWORD_REQUIRE_UPPERCASE=True,
            PASSWORD_REQUIRE_LOWERCASE=True,
            PASSWORD_REQUIRE_DIGIT=True,
            PASSWORD_REQUIRE_SPECIAL=False,
            REGISTRATION_ENABLED=True,
            REGISTRATION_REQUIRE_CODE=False,
            REGISTRATION_CODES=[],
            DEFAULT_USER_ROLE="user",
            DEFAULT_STORAGE_QUOTA_MB=1000,
            EMAIL_VERIFICATION_REQUIRED=False,
            CORS_ORIGINS=["*"],
            API_PREFIX="/api/v1",
        )
        svc = JWTService(settings=settings)
        good = svc.create_access_token(1, "good", "user")
        # Verify good token passes
        assert svc.decode_access_token(good)["sub"] == "1"
        # Mint a token with wrong audience by temporarily overriding settings
        bad_settings = Settings(
            AUTH_MODE="multi_user",
            JWT_SECRET_KEY=settings.JWT_SECRET_KEY,
            JWT_ALGORITHM="HS256",
            JWT_ISSUER="tldw.test",
            JWT_AUDIENCE="wrong.aud",
            ACCESS_TOKEN_EXPIRE_MINUTES=5,
            REFRESH_TOKEN_EXPIRE_DAYS=7,
            SESSION_CLEANUP_INTERVAL_HOURS=24,
            SESSION_MAX_AGE_DAYS=30,
            RATE_LIMIT_ENABLED=False,
            PASSWORD_MIN_LENGTH=8,
            PASSWORD_REQUIRE_UPPERCASE=True,
            PASSWORD_REQUIRE_LOWERCASE=True,
            PASSWORD_REQUIRE_DIGIT=True,
            PASSWORD_REQUIRE_SPECIAL=False,
            REGISTRATION_ENABLED=True,
            REGISTRATION_REQUIRE_CODE=False,
            REGISTRATION_CODES=[],
            DEFAULT_USER_ROLE="user",
            DEFAULT_STORAGE_QUOTA_MB=1000,
            EMAIL_VERIFICATION_REQUIRED=False,
            CORS_ORIGINS=["*"],
            API_PREFIX="/api/v1",
        )
        svc_bad = JWTService(settings=bad_settings)
        bad = svc_bad.create_access_token(1, "bad", "user")
        with pytest.raises(InvalidTokenError):
            svc.decode_access_token(bad)
