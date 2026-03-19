from pathlib import Path

import pytest

from Helper_Scripts.Deployment import hosted_staging_preflight


def _write_valid_env_file(tmp_path: Path) -> Path:
    env_file = tmp_path / ".env.hosted-staging"
    env_file.write_text(
        "\n".join(
            [
                "AUTH_MODE=multi_user",
                "DATABASE_URL=postgresql://user:pass@db:5432/tldw",
                "tldw_production=true",
                "PUBLIC_WEB_BASE_URL=https://staging.example.com",
                "BILLING_REDIRECT_ALLOWLIST_REQUIRED=true",
                "BILLING_REDIRECT_REQUIRE_HTTPS=true",
                "BILLING_ALLOWED_REDIRECT_HOSTS=staging.example.com",
            ]
        ),
        encoding="utf-8",
    )
    return env_file


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def test_preflight_fails_when_billing_plans_endpoint_is_unreachable(tmp_path, monkeypatch) -> None:
    env_file = _write_valid_env_file(tmp_path)

    responses = {
        "https://staging.example.com/health": (200, "ok", ""),
        "https://staging.example.com/ready": (200, "ok", ""),
        "https://staging.example.com/login": (
            200,
            "<html><body>Hosted tldw keeps the first-run path focused.</body></html>",
            "",
        ),
        "https://staging.example.com/signup": (
            200,
            "<html><body>Create your hosted account</body></html>",
            "",
        ),
        "https://staging.example.com/api/v1/billing/plans": (0, "", "URL error: connection refused"),
    }

    monkeypatch.setattr(
        hosted_staging_preflight,
        "_fetch_url",
        lambda url, timeout: responses[url],
    )

    exit_code = hosted_staging_preflight.main(
        [
            "--env-file",
            str(env_file),
            "--base-url",
            "https://staging.example.com",
        ]
    )

    _require(exit_code == 1, "Expected preflight to fail when billing plans are unreachable")


def test_preflight_passes_when_health_routes_and_public_pages_are_reachable(tmp_path, monkeypatch) -> None:
    env_file = _write_valid_env_file(tmp_path)

    responses = {
        "https://api.staging.example.com/health": (200, '{"status":"ok"}', ""),
        "https://api.staging.example.com/ready": (200, '{"ready":true}', ""),
        "https://staging.example.com/login": (
            200,
            "<html><body>Hosted tldw keeps the first-run path focused.</body></html>",
            "",
        ),
        "https://staging.example.com/signup": (
            200,
            "<html><body>Create your hosted account</body></html>",
            "",
        ),
        "https://api.staging.example.com/api/v1/billing/plans": (200, '[{"code":"starter"}]', ""),
    }

    monkeypatch.setattr(
        hosted_staging_preflight,
        "_fetch_url",
        lambda url, timeout: responses[url],
    )

    exit_code = hosted_staging_preflight.main(
        [
            "--env-file",
            str(env_file),
            "--base-url",
            "https://staging.example.com",
            "--api-base-url",
            "https://api.staging.example.com",
            "--strict",
        ]
    )

    _require(exit_code == 0, "Expected preflight to pass for reachable hosted staging endpoints")
