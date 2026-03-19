import pytest

from Helper_Scripts.validate_hosted_saas_profile import main, validate_hosted_profile


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def test_validator_rejects_missing_public_web_base_url():
    result = validate_hosted_profile(
        {
            "AUTH_MODE": "multi_user",
            "DATABASE_URL": "postgresql://user:pass@db:5432/tldw",
            "tldw_production": "true",
            "BILLING_REDIRECT_ALLOWLIST_REQUIRED": "true",
            "BILLING_REDIRECT_REQUIRE_HTTPS": "true",
            "BILLING_ALLOWED_REDIRECT_HOSTS": "app.example.com",
        }
    )

    _require(result.ok is False, "expected validation to fail without PUBLIC_WEB_BASE_URL")
    _require(
        "PUBLIC_WEB_BASE_URL" in result.errors,
        "expected PUBLIC_WEB_BASE_URL validation error",
    )


def test_validator_rejects_non_multi_user_auth_mode():
    result = validate_hosted_profile(
        {
            "AUTH_MODE": "single_user",
            "DATABASE_URL": "postgresql://user:pass@db:5432/tldw",
            "tldw_production": "true",
            "PUBLIC_WEB_BASE_URL": "https://app.example.com",
            "BILLING_REDIRECT_ALLOWLIST_REQUIRED": "true",
            "BILLING_REDIRECT_REQUIRE_HTTPS": "true",
            "BILLING_ALLOWED_REDIRECT_HOSTS": "app.example.com",
        }
    )

    _require(result.ok is False, "expected validation to fail for single_user auth mode")
    _require("AUTH_MODE" in result.errors, "expected AUTH_MODE validation error")


def test_validator_rejects_non_postgres_database_url():
    result = validate_hosted_profile(
        {
            "AUTH_MODE": "multi_user",
            "DATABASE_URL": "sqlite:///./Databases/users.db",
            "tldw_production": "true",
            "PUBLIC_WEB_BASE_URL": "https://app.example.com",
            "BILLING_REDIRECT_ALLOWLIST_REQUIRED": "true",
            "BILLING_REDIRECT_REQUIRE_HTTPS": "true",
            "BILLING_ALLOWED_REDIRECT_HOSTS": "app.example.com",
        }
    )

    _require(
        result.ok is False,
        "expected validation to fail for non-Postgres DATABASE_URL",
    )
    _require("DATABASE_URL" in result.errors, "expected DATABASE_URL validation error")


def test_validator_rejects_when_production_guard_is_disabled():
    result = validate_hosted_profile(
        {
            "AUTH_MODE": "multi_user",
            "DATABASE_URL": "postgresql://user:pass@db:5432/tldw",
            "tldw_production": "false",
            "PUBLIC_WEB_BASE_URL": "https://app.example.com",
            "BILLING_REDIRECT_ALLOWLIST_REQUIRED": "true",
            "BILLING_REDIRECT_REQUIRE_HTTPS": "true",
            "BILLING_ALLOWED_REDIRECT_HOSTS": "app.example.com",
        }
    )

    _require(
        result.ok is False,
        "expected validation to fail when tldw_production is disabled",
    )
    _require(
        "tldw_production" in result.errors,
        "expected tldw_production validation error",
    )


def test_validator_rejects_when_billing_redirect_host_is_not_allowlisted():
    result = validate_hosted_profile(
        {
            "AUTH_MODE": "multi_user",
            "DATABASE_URL": "postgresql://user:pass@db:5432/tldw",
            "tldw_production": "true",
            "PUBLIC_WEB_BASE_URL": "https://app.example.com",
            "BILLING_REDIRECT_ALLOWLIST_REQUIRED": "true",
            "BILLING_REDIRECT_REQUIRE_HTTPS": "true",
            "BILLING_ALLOWED_REDIRECT_HOSTS": "billing.example.com",
        }
    )

    _require(
        result.ok is False,
        "expected validation to fail when redirect host is not allowlisted",
    )
    _require(
        "BILLING_ALLOWED_REDIRECT_HOSTS" in result.errors,
        "expected BILLING_ALLOWED_REDIRECT_HOSTS validation error",
    )


def test_validator_accepts_the_hosted_saas_contract():
    result = validate_hosted_profile(
        {
            "AUTH_MODE": "multi_user",
            "DATABASE_URL": "postgresql://user:pass@db:5432/tldw",
            "tldw_production": "true",
            "PUBLIC_WEB_BASE_URL": "https://app.example.com",
            "BILLING_REDIRECT_ALLOWLIST_REQUIRED": "true",
            "BILLING_REDIRECT_REQUIRE_HTTPS": "true",
            "BILLING_ALLOWED_REDIRECT_HOSTS": "app.example.com,*.example.net",
        }
    )

    _require(result.ok is True, "expected hosted SaaS contract to validate successfully")
    _require(result.errors == {}, "expected no validation errors for hosted SaaS contract")


def test_validator_cli_can_read_env_file(tmp_path):
    env_file = tmp_path / ".env.hosted"
    env_file.write_text(
        "\n".join(
            [
                "AUTH_MODE=multi_user",
                "DATABASE_URL=postgresql://user:pass@db:5432/tldw",
                "tldw_production=true",
                "PUBLIC_WEB_BASE_URL=https://app.example.com",
                "BILLING_REDIRECT_ALLOWLIST_REQUIRED=true",
                "BILLING_REDIRECT_REQUIRE_HTTPS=true",
                "BILLING_ALLOWED_REDIRECT_HOSTS=app.example.com",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(
        ["validate_hosted_saas_profile.py", "--env-file", str(env_file)]
    )

    _require(exit_code == 0, "expected CLI validation to pass for valid env file")


def test_validator_cli_rejects_missing_env_file(tmp_path):
    missing_env_file = tmp_path / ".env.missing"

    exit_code = main(
        ["validate_hosted_saas_profile.py", "--env-file", str(missing_env_file)]
    )

    _require(exit_code == 1, "expected CLI validation to fail for missing env file")
