from pathlib import Path

import pytest

from Helper_Scripts.validate_hosted_saas_profile import validate_hosted_profile


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def test_hosted_production_env_example_uses_prod_public_origin():
    text = Path("tldw_Server_API/Config_Files/.env.hosted-production.example").read_text(
        encoding="utf-8"
    )

    _require(
        "PUBLIC_WEB_BASE_URL=https://app.example.com" in text,
        "expected prod public web base url",
    )
    _require(
        "DATABASE_URL=postgresql://" in text,
        "expected managed postgres DSN placeholder",
    )


def test_hosted_production_caddy_sample_routes_api_and_webui():
    text = Path("Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose").read_text(
        encoding="utf-8"
    )

    _require("reverse_proxy @api app:8000" in text, "expected api reverse proxy")
    _require("reverse_proxy webui:3000" in text, "expected webui reverse proxy")


def test_hosted_production_env_example_validates_against_hosted_profile():
    env_file = Path("tldw_Server_API/Config_Files/.env.hosted-production.example")
    env_map = {}
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env_map[key] = value

    result = validate_hosted_profile(env_map)

    _require(result.ok is True, "expected hosted production env example to satisfy profile")
    _require(result.errors == {}, "expected no validation errors for hosted production env example")
