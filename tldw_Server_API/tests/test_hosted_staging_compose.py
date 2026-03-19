from pathlib import Path

import pytest
import yaml


def _load_yaml(path: str) -> dict:
    loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        pytest.fail(f"Expected YAML mapping at {path}")
    return loaded


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def test_hosted_staging_compose_declares_app_webui_proxy_and_postgres():
    data = _load_yaml("Dockerfiles/docker-compose.hosted-saas-staging.yml")
    services = data.get("services", {})

    _require("app" in services, "Expected hosted staging overlay to define app service")
    _require("webui" in services, "Expected hosted staging overlay to define webui service")
    _require("caddy" in services, "Expected hosted staging overlay to define caddy service")
    _require("postgres" in services, "Expected hosted staging overlay to define postgres service")

    app_environment = services["app"].get("environment", {})
    _require(
        app_environment.get("PUBLIC_WEB_BASE_URL") == "${PUBLIC_WEB_BASE_URL:?Set PUBLIC_WEB_BASE_URL}",
        "Expected app service to require PUBLIC_WEB_BASE_URL",
    )
    _require(
        app_environment.get("BILLING_ENABLED") == "${BILLING_ENABLED:-true}",
        "Expected app service to enable billing by default in staging overlay",
    )
    _require(
        app_environment.get("BILLING_ALLOWED_REDIRECT_HOSTS")
        == "${BILLING_ALLOWED_REDIRECT_HOSTS:?Set BILLING_ALLOWED_REDIRECT_HOSTS}",
        "Expected app service to require BILLING_ALLOWED_REDIRECT_HOSTS",
    )

    webui_build_args = services["webui"].get("build", {}).get("args", {})
    _require(
        webui_build_args.get("NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE") == "hosted",
        "Expected webui build args to bake hosted deployment mode",
    )

    caddy_volumes = services["caddy"].get("volumes", [])
    _require(
        "../Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose:/etc/caddy/Caddyfile:ro"
        in caddy_volumes,
        "Expected caddy service to mount the hosted SaaS Caddyfile sample",
    )
