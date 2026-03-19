from pathlib import Path

import pytest
import yaml

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
    _require("TLDW_APP_DATA_DIR=" in text, "expected app data dir env entry")
    _require("TLDW_USER_DATA_DIR=" in text, "expected user data dir env entry")
    _require("TLDW_REDIS_DATA_DIR=" in text, "expected redis data dir env entry")
    _require("TLDW_POSTGRES_DATA_DIR=" in text, "expected postgres data dir env entry")
    _require("POSTGRES_PASSWORD=" in text, "expected fallback postgres password env entry")


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


def test_hosted_production_compose_is_standalone_and_keeps_postgres_internal():
    text = Path("Dockerfiles/docker-compose.hosted-saas-prod.yml").read_text(
        encoding="utf-8"
    )
    data = yaml.safe_load(text)
    _require(isinstance(data, dict), "expected hosted production compose to parse as a mapping")

    services = data.get("services", {})
    _require("app" in services, "expected hosted production compose to define app service")
    _require("webui" in services, "expected hosted production compose to define webui service")
    _require("redis" in services, "expected hosted production compose to define redis service")
    _require("caddy" in services, "expected hosted production compose to define caddy service")
    _require("postgres" not in services, "primary prod compose should not define local postgres")

    app_service = services["app"]
    _require(
        app_service.get("ports", []) == [],
        "expected app service to avoid public host ports",
    )
    _require(
        app_service.get("expose", []) == ["8000"],
        "expected app service to expose port 8000 internally",
    )

    redis_service = services["redis"]
    _require(
        redis_service.get("ports", []) == [],
        "expected redis service to avoid public host ports",
    )
    _require(
        redis_service.get("expose", []) == ["6379"],
        "expected redis service to expose port 6379 internally",
    )

    caddy_service = services["caddy"]
    _require(
        caddy_service.get("ports", []) == ["80:80", "443:443"],
        "expected caddy to be the only public entrypoint",
    )

    webui_service = services["webui"]
    _require(
        webui_service.get("ports", []) == [],
        "expected webui to avoid public host ports",
    )

    app_environment = app_service.get("environment", {})
    _require(
        app_environment.get("DATABASE_URL") == "${DATABASE_URL:?Set DATABASE_URL}",
        "expected app service to require a managed DATABASE_URL",
    )
    _require(
        app_environment.get("PUBLIC_WEB_BASE_URL") == "${PUBLIC_WEB_BASE_URL:?Set PUBLIC_WEB_BASE_URL}",
        "expected app service to require PUBLIC_WEB_BASE_URL",
    )

    webui_build_args = webui_service.get("build", {}).get("args", {})
    _require(
        webui_build_args.get("NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE") == "hosted",
        "expected webui build args to bake hosted deployment mode",
    )

    webui_environment = webui_service.get("environment", {})
    _require(
        webui_environment.get("NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE") == "hosted",
        "expected webui runtime env to set hosted deployment mode",
    )

    app_volumes = app_service.get("volumes", [])
    _require(
        any("TLDW_APP_DATA_DIR" in volume for volume in app_volumes),
        "expected app data bind mount to use TLDW_APP_DATA_DIR",
    )
    _require(
        any("TLDW_USER_DATA_DIR" in volume for volume in app_volumes),
        "expected user data bind mount to use TLDW_USER_DATA_DIR",
    )

    redis_volumes = redis_service.get("volumes", [])
    _require(
        any("TLDW_REDIS_DATA_DIR" in volume for volume in redis_volumes),
        "expected redis data bind mount to use TLDW_REDIS_DATA_DIR",
    )

    caddy_volumes = caddy_service.get("volumes", [])
    _require(
        "../Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose:/etc/caddy/Caddyfile:ro"
        in caddy_volumes,
        "expected caddy service to mount the production Caddyfile sample",
    )


def test_hosted_production_local_postgres_overlay_adds_internal_postgres_service():
    text = Path("Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml").read_text(
        encoding="utf-8"
    )
    data = yaml.safe_load(text)
    _require(isinstance(data, dict), "expected hosted production fallback overlay to parse as a mapping")

    services = data.get("services", {})
    _require(
        "postgres" in services,
        "expected fallback overlay to define postgres service",
    )
    _require(
        "app" in services,
        "expected fallback overlay to override app service dependencies",
    )
    _require(
        "caddy" not in services and "webui" not in services and "redis" not in services,
        "expected fallback overlay to add only postgres and app overrides",
    )

    postgres_service = services["postgres"]
    _require(
        postgres_service.get("ports", []) == [],
        "expected fallback postgres to avoid public host ports",
    )
    _require(
        postgres_service.get("expose", []) == ["5432"],
        "expected fallback postgres to expose port 5432 internally",
    )
    _require(
        any("TLDW_POSTGRES_DATA_DIR" in volume for volume in postgres_service.get("volumes", [])),
        "expected fallback postgres to use TLDW_POSTGRES_DATA_DIR bind mount",
    )

    postgres_environment = postgres_service.get("environment", {})
    _require(
        postgres_environment.get("POSTGRES_PASSWORD")
        == "${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}",
        "expected fallback postgres to require an explicit POSTGRES_PASSWORD",
    )

    app_service = services["app"]
    depends_on = app_service.get("depends_on", {})
    _require(
        "postgres" in depends_on,
        "expected fallback overlay to add postgres dependency to app",
    )


def test_hosted_production_runbook_documents_prod_and_fallback_topology():
    text = Path("Docs/Published/Deployment/Hosted_Production_Runbook.md").read_text(
        encoding="utf-8"
    )

    _require(
        "docker-compose.hosted-saas-prod.yml" in text,
        "expected production runbook to reference the standalone prod compose file",
    )
    _require(
        "docker-compose.hosted-saas-prod.local-postgres.yml" in text,
        "expected production runbook to reference the local-postgres fallback overlay",
    )
    _require(
        "tldw_Server_API/Config_Files/.env.hosted-production.example" in text,
        "expected production runbook to reference the production env template",
    )
    _require(
        "tldw_Server_API/Config_Files/.env.hosted-production" in text,
        "expected production runbook to use a real production env file",
    )
    _require(
        "Caddyfile.hosted-saas.prod.compose" in text,
        "expected production runbook to reference the production Caddy sample",
    )
    _require(
        "Stripe test mode" in text or "staging" in text.lower(),
        "expected production runbook to keep live Stripe proof in staging",
    )

    profile_text = Path("Docs/Published/Deployment/Hosted_SaaS_Profile.md").read_text(
        encoding="utf-8"
    )
    _require(
        "Hosted_Production_Runbook.md" in profile_text,
        "expected hosted profile to reference the production runbook",
    )

    staging_text = Path("Docs/Published/Deployment/Hosted_Staging_Runbook.md").read_text(
        encoding="utf-8"
    )
    _require(
        "Hosted_Production_Runbook.md" in staging_text,
        "expected hosted staging runbook to reference the production runbook",
    )

    first_time_text = Path("Docs/Published/Deployment/First_Time_Production_Setup.md").read_text(
        encoding="utf-8"
    )
    _require(
        "Hosted_Production_Runbook.md" in first_time_text,
        "expected first-time production setup guide to reference the production runbook",
    )
