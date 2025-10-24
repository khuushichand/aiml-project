"""
Unit tests for HMAC key derivation behavior in JWTService.hash_token and APIKeyManager.
"""

from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyManager
from tldw_Server_API.app.core.AuthNZ.settings import Settings
from tldw_Server_API.app.core.AuthNZ.api_key_manager import APIKeyStatus
from tldw_Server_API.app.core.AuthNZ.session_manager import SessionManager


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


def test_hash_token_candidates_include_secondary_secret():
    token = "rotation-test-token"
    old_secret = "old-secret-value-1234567890abcdef123456"
    new_secret = "new-secret-value-fedcba0987654321123456"

    old_svc = _svc_multi_user(secret=old_secret)
    rotated_svc = _svc_multi_user(secret=new_secret, JWT_SECONDARY_SECRET=old_secret)

    old_hash = old_svc.hash_token(token)
    candidates = rotated_svc.hash_token_candidates(token)
    assert old_hash in candidates


def test_session_manager_hash_candidates_include_secondary_secret():
    token = "session-rotation-token"
    old_secret = "session-old-secret-abcdef0123456789abcd"
    new_secret = "session-new-secret-9876543210fedcbaabcd"

    settings_old = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY=old_secret)
    settings_new = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY=new_secret,
        JWT_SECONDARY_SECRET=old_secret,
    )

    manager_old = SessionManager(settings=settings_old)
    manager_new = SessionManager(settings=settings_new)

    old_hash = manager_old.hash_token(token)
    assert old_hash in manager_new._token_hash_candidates(token)


def test_api_key_manager_hash_candidates_include_secondary_secret():
    api_key = "apikey-rotation-token"
    old_secret = "apikey-old-secret-abcdef0123456789abcd"
    new_secret = "apikey-new-secret-9876543210fedcbaabcd"

    settings_old = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY=old_secret)
    settings_new = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY=new_secret,
        JWT_SECONDARY_SECRET=old_secret,
    )

    mgr_old = APIKeyManager()
    mgr_old.settings = settings_old
    mgr_new = APIKeyManager()
    mgr_new.settings = settings_new

    old_hash = mgr_old.hash_api_key(api_key)
    assert old_hash in mgr_new.hash_candidates(api_key)


class _FakePostgresPool:
    def __init__(self, expected_candidates, stored_hash=None):
        self.pool = object()
        self.expected_candidates = tuple(expected_candidates)
        self.stored_hash = stored_hash or self.expected_candidates[0]
        self.calls = []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchone(self, query: str, candidates, status):
        self.calls.append((query, candidates, status))
        assert tuple(candidates) == self.expected_candidates
        assert status == APIKeyStatus.ACTIVE.value
        return {
            "id": 1,
            "user_id": 99,
            "name": "legacy-key",
            "scope": "read",
            "status": APIKeyStatus.ACTIVE.value,
            "expires_at": None,
            "rate_limit": None,
            "allowed_ips": None,
            "usage_count": 0,
            "key_hash": self.stored_hash,
            "is_virtual": False,
            "parent_key_id": None,
            "org_id": None,
            "team_id": None,
            "llm_budget_day_tokens": None,
            "llm_budget_month_tokens": None,
            "llm_budget_day_usd": None,
            "llm_budget_month_usd": None,
            "llm_allowed_endpoints": None,
            "llm_allowed_providers": None,
            "llm_allowed_models": None,
            "metadata": None,
        }

    async def execute(self, query: str, *params):
        params_tuple = tuple(params)
        self.executed.append((query, params_tuple))
        if "SET key_hash" in query:
            self.stored_hash = params_tuple[0]
        return None


class _FakeSQLitePool:
    def __init__(self, expected_candidates, stored_hash=None):
        self.pool = None
        self.expected_candidates = tuple(expected_candidates)
        self.stored_hash = stored_hash or self.expected_candidates[0]
        self.calls = []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchone(self, query: str, params):
        self.calls.append((query, params))
        *hashes, status = params
        assert tuple(hashes) == tuple(self.expected_candidates)
        assert status == APIKeyStatus.ACTIVE.value
        return {
            "id": 1,
            "user_id": 99,
            "name": "legacy-key",
            "scope": "read",
            "status": APIKeyStatus.ACTIVE.value,
            "expires_at": None,
            "rate_limit": None,
            "allowed_ips": None,
            "usage_count": 0,
            "key_hash": self.stored_hash,
            "is_virtual": 0,
            "parent_key_id": None,
            "org_id": None,
            "team_id": None,
            "llm_budget_day_tokens": None,
            "llm_budget_month_tokens": None,
            "llm_budget_day_usd": None,
            "llm_budget_month_usd": None,
            "llm_allowed_endpoints": None,
            "llm_allowed_providers": None,
            "llm_allowed_models": None,
            "metadata": None,
        }

    async def execute(self, query: str, *params):
        params_tuple = tuple(params[0]) if len(params) == 1 and isinstance(params[0], (list, tuple)) else tuple(params)
        self.executed.append((query, params_tuple))
        if "SET key_hash" in query:
            self.stored_hash = params_tuple[0]
        return None


async def _noop_update_usage(*args, **kwargs):
    return None


@pytest.mark.asyncio
async def test_validate_api_key_uses_hash_candidates_postgres(monkeypatch):
    api_key = "tldw_rotated_key"
    old_secret = "old-secret-for-api-key-abcdefghijklmno"
    new_secret = "new-secret-for-api-key-ponmlkjihgfedcba"

    mgr_old = APIKeyManager()
    mgr_old.settings = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY=old_secret)
    stored_hash = mgr_old.hash_api_key(api_key)

    settings_new = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY=new_secret,
        JWT_SECONDARY_SECRET=old_secret,
    )
    manager = APIKeyManager()
    manager.settings = settings_new
    manager._initialized = True

    candidates = manager.hash_candidates(api_key)
    assert stored_hash in candidates

    fake_pool = _FakePostgresPool(candidates, stored_hash=stored_hash)
    manager.db_pool = fake_pool
    manager._update_usage = _noop_update_usage  # type: ignore[attr-defined]

    result = await manager.validate_api_key(api_key)
    assert result is not None
    assert result["id"] == 1
    assert fake_pool.calls, "Expected fetchone to be invoked with candidate hashes"
    assert any("SET key_hash" in q for q, _ in fake_pool.executed)
    assert fake_pool.stored_hash == candidates[0]
    assert "key_hash" not in result


@pytest.mark.asyncio
async def test_validate_api_key_uses_hash_candidates_sqlite(monkeypatch):
    api_key = "tldw_rotated_key_sqlite"
    old_secret = "old-secret-sqlite-abcdefghijklmno"
    new_secret = "new-secret-sqlite-ponmlkjihgfedcba"

    mgr_old = APIKeyManager()
    mgr_old.settings = Settings(AUTH_MODE="multi_user", JWT_SECRET_KEY=old_secret)
    stored_hash = mgr_old.hash_api_key(api_key)

    settings_new = Settings(
        AUTH_MODE="multi_user",
        JWT_SECRET_KEY=new_secret,
        JWT_SECONDARY_SECRET=old_secret,
    )
    manager = APIKeyManager()
    manager.settings = settings_new
    manager._initialized = True

    candidates = manager.hash_candidates(api_key)
    assert stored_hash in candidates

    fake_pool = _FakeSQLitePool(candidates, stored_hash=stored_hash)
    manager.db_pool = fake_pool
    manager._update_usage = _noop_update_usage  # type: ignore[attr-defined]

    result = await manager.validate_api_key(api_key)
    assert result is not None
    assert result["id"] == 1
    assert fake_pool.calls, "Expected fetchone to be invoked with candidate hashes"
    assert any("SET key_hash" in q for q, _ in fake_pool.executed)
    assert fake_pool.stored_hash == candidates[0]
    assert "key_hash" not in result


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
