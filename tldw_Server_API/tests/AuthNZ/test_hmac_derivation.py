"""
Unit tests for HMAC key derivation behavior in JWTService.hash_token and APIKeyManager.
"""

import pytest

from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
from tldw_Server_API.app.core.AuthNZ.settings import Settings


def _svc_single_user(key: str, **overrides) -> JWTService:
    # Ensure env-provided secrets do not interfere with single-user derivation tests
    import os as _os
    _os.environ.pop("JWT_SECRET_KEY", None)
    _os.environ.pop("API_KEY_PEPPER", None)
    s = Settings(
        AUTH_MODE="single_user",
        SINGLE_USER_API_KEY=key,
        JWT_ALGORITHM="HS256",
        # Minimal other required settings
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
        **overrides,
    )
    return JWTService(settings=s)


def _svc_multi_user(secret: str, **overrides) -> JWTService:
    # Ensure no pepper from environment leaks into test unless explicitly passed
    import os as _os
    _os.environ.pop("API_KEY_PEPPER", None)
    s = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY=secret,
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=5,
        REFRESH_TOKEN_EXPIRE_DAYS=7,
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
        **overrides,
    )
    return JWTService(settings=s)


def test_hash_token_changes_with_pepper_or_secret():
    svc1 = _svc_multi_user(secret="A" * 32)
    svc2 = _svc_multi_user(secret="B" * 32)
    token = "example-token"
    assert svc1.hash_token(token) != svc2.hash_token(token)

    # With same secret, different pepper should also change digest
    svc3 = _svc_multi_user(secret="A" * 32, API_KEY_PEPPER="pep1")
    svc4 = _svc_multi_user(secret="A" * 32, API_KEY_PEPPER="pep2")
    assert svc3.hash_token(token) != svc4.hash_token(token)


def test_hash_token_single_user_derives_from_api_key():
    svc1 = _svc_single_user(key="key-one-abcdef0123456789")
    svc2 = _svc_single_user(key="key-two-abcdef0123456789")
    token = "example-token"
    assert svc1.hash_token(token) != svc2.hash_token(token)


@pytest.mark.asyncio
async def test_api_key_manager_hash_uses_same_derivation():
    # Single-user mode: derive from SINGLE_USER_API_KEY when pepper/secret unset
    settings = Settings(
        AUTH_MODE="single_user",
        SINGLE_USER_API_KEY="test-single-user-key-xyz",
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
    mgr = APIKeyManager()
    mgr.settings = settings
    a, b = "apikey-A", "apikey-B"
    assert mgr.hash_api_key(a) != mgr.hash_api_key(b)
    # Changing SINGLE_USER_API_KEY changes derivation
    mgr.settings.SINGLE_USER_API_KEY = "test-single-user-key-zzz"
    assert mgr.hash_api_key(a) != mgr.hash_api_key(b)
