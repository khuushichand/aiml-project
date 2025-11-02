"""
Tests for production guardrails in single-user mode.
"""

import os
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import Settings


def test_single_user_production_rejects_weak_key(monkeypatch):
    monkeypatch.setenv("tldw_production", "true")
    with pytest.raises(ValueError):
        Settings(
            AUTH_MODE="single_user",
            SINGLE_USER_API_KEY="test-api-key-12345",  # default/weak
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
    monkeypatch.delenv("tldw_production", raising=False)
