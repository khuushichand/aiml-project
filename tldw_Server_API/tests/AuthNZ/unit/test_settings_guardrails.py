"""
Tests for production guardrails in single-user mode.
"""

import os
from pathlib import Path
import pytest

from tldw_Server_API.app.core.AuthNZ.settings import (
    AUTHNZ_DEFAULT_ENV_FILE,
    Settings,
    get_settings,
    reset_settings,
)
from tldw_Server_API.app.core.AuthNZ.api_key_crypto import format_api_key


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


def test_single_user_production_accepts_new_format(monkeypatch):


    monkeypatch.setenv("tldw_production", "true")
    Settings(
        AUTH_MODE="single_user",
        SINGLE_USER_API_KEY=format_api_key("deadbeefcafe", "secret-part"),
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


def test_single_user_production_rejects_legacy_format(monkeypatch):
    import sys

    legacy_key = "legacy-key-1234567890123456"

    monkeypatch.setenv("tldw_production", "true")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("E2E_TEST_BASE_URL", raising=False)

    pytest_mod = sys.modules.pop("pytest", None)
    try:
        with pytest.raises(ValueError):
            Settings(
                AUTH_MODE="single_user",
                SINGLE_USER_API_KEY=legacy_key,
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
    finally:
        if pytest_mod is not None:
            sys.modules["pytest"] = pytest_mod
    monkeypatch.delenv("tldw_production", raising=False)


def test_single_user_production_allows_legacy_format_with_override(monkeypatch):
    import sys

    legacy_key = "legacy-key-1234567890123456"

    monkeypatch.setenv("tldw_production", "true")
    monkeypatch.setenv("TLDW_ALLOW_LEGACY_SINGLE_USER_KEY", "true")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("E2E_TEST_BASE_URL", raising=False)

    pytest_mod = sys.modules.pop("pytest", None)
    try:
        Settings(
            AUTH_MODE="single_user",
            SINGLE_USER_API_KEY=legacy_key,
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
    finally:
        if pytest_mod is not None:
            sys.modules["pytest"] = pytest_mod
    monkeypatch.delenv("TLDW_ALLOW_LEGACY_SINGLE_USER_KEY", raising=False)
    monkeypatch.delenv("tldw_production", raising=False)


def test_get_settings_does_not_use_pytest_module_presence_for_test_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_settings()
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("TEST_MODE", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("TLDW_TEST_MODE", raising=False)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "legacy-key-1234567890123456")

    settings = get_settings()

    assert settings.AUTH_MODE == "single_user"
    assert not hasattr(settings, "RATE_LIMIT_ENABLED")


def test_authnz_settings_env_file_points_to_config_files() -> None:
    env_file = Path(Settings.model_config.get("env_file", ""))

    assert env_file == AUTHNZ_DEFAULT_ENV_FILE
    assert env_file.name == ".env"
    assert "Config_Files" in str(env_file)
