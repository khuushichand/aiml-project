from pathlib import Path

import pytest


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def test_boundary_policy_and_inventory_exist() -> None:
    policy = Path("Docs/Policies/OSS_Private_Boundary.md").read_text(encoding="utf-8")
    inventory = Path("Docs/Plans/2026-03-19-oss-saas-private-inventory.md").read_text(
        encoding="utf-8"
    )

    _require("Public" in policy, "expected public boundary rules")
    _require("Private" in policy, "expected private boundary rules")
    _require(
        "Hosted_Production_Runbook.md" in inventory,
        "expected hosted inventory entry",
    )


def test_public_docs_pipeline_declares_hosted_material_private() -> None:
    guide = Path("Docs/Code_Documentation/Docs_Site_Guide.md").read_text(encoding="utf-8")
    refresh_script = Path("Helper_Scripts/refresh_docs_published.sh").read_text(
        encoding="utf-8"
    )
    mkdocs_config = Path("Docs/mkdocs.yml").read_text(encoding="utf-8")

    _require(
        "hosted/commercial docs are excluded" in guide.lower(),
        "expected docs site guide to state that hosted/commercial docs are excluded",
    )
    _require(
        "private repo" in guide.lower(),
        "expected docs site guide to point contributors to the private repo for hosted docs",
    )
    _require(
        "hosted/commercial docs stay out of docs/published" in refresh_script.lower(),
        "expected refresh script comments to document that hosted/commercial docs stay out of Docs/Published",
    )
    _require(
        "Hosted_Production_Runbook.md" not in mkdocs_config,
        "expected mkdocs nav to avoid hosted private runbooks",
    )


def test_public_docs_do_not_point_self_host_users_to_hosted_runbooks() -> None:
    first_time_setup = Path("Docs/Published/Deployment/First_Time_Production_Setup.md").read_text(
        encoding="utf-8"
    )
    production_hardening = Path(
        "Docs/User_Guides/Server/Production_Hardening_Checklist.md"
    ).read_text(
        encoding="utf-8"
    )
    billing_readme = Path("tldw_Server_API/app/core/Billing/README.md").read_text(
        encoding="utf-8"
    )

    _require(
        "Hosted_SaaS_Profile.md" not in first_time_setup,
        "expected self-host production setup guide to avoid hosted SaaS profile links",
    )
    _require(
        "Hosted_Production_Runbook.md" not in first_time_setup,
        "expected self-host production setup guide to avoid hosted production runbook links",
    )
    _require(
        "Hosted_SaaS_Profile.md" not in production_hardening,
        "expected production hardening checklist to avoid public hosted SaaS profile links",
    )
    _require(
        "validate_hosted_saas_profile.py" not in production_hardening,
        "expected production hardening checklist to avoid public hosted validation helper references",
    )
    _require(
        "Hosted_Stripe_Test_Mode_Runbook.md" not in billing_readme,
        "expected billing README to avoid public hosted Stripe runbook links",
    )


def test_public_frontend_does_not_import_hosted_customer_surface() -> None:
    checked_files = [
        "apps/tldw-frontend/pages/_app.tsx",
        "apps/tldw-frontend/pages/login.tsx",
        "apps/tldw-frontend/pages/signup.tsx",
        "apps/tldw-frontend/pages/account/index.tsx",
        "apps/tldw-frontend/pages/billing/index.tsx",
        "apps/tldw-frontend/pages/auth/verify-email.tsx",
        "apps/tldw-frontend/pages/auth/reset-password.tsx",
        "apps/tldw-frontend/pages/auth/magic-link.tsx",
    ]

    for path in checked_files:
        text = Path(path).read_text(encoding="utf-8")
        _require(
            "@web/components/hosted" not in text,
            f"expected public frontend entrypoint to avoid hosted component imports: {path}",
        )
        _require(
            "@web/lib/hosted-route-allowlist" not in text,
            f"expected public frontend entrypoint to avoid hosted route allowlist imports: {path}",
        )


def test_boundary_checker_exists() -> None:
    checker = Path("Helper_Scripts/docs/check_public_private_boundary.py").read_text(
        encoding="utf-8"
    )

    _require(
        "Hosted_Production_Runbook.md" in checker,
        "expected hosted reference denylist in the boundary checker",
    )
    _require(
        "Docs/Published" in checker,
        "expected boundary checker to scan public docs paths",
    )
    _require(
        "billing_webhooks.py" in checker,
        "expected commercial billing runtime denylist in the boundary checker",
    )
    _require(
        "stripe_metering_service.py" in checker,
        "expected commercial metering runtime denylist in the boundary checker",
    )
    _require(
        "admin_billing.py" in checker,
        "expected admin billing runtime denylist in the boundary checker",
    )
    _require(
        "pages/account/index.tsx" in checker,
        "expected public account marker denylist in the boundary checker",
    )
    _require(
        "pages/billing/index.tsx" in checker,
        "expected public billing marker denylist in the boundary checker",
    )


def test_public_curated_tree_does_not_ship_hosted_deployment_docs() -> None:
    hosted_docs = [
        Path("Docs/Published/Deployment/Hosted_SaaS_Profile.md"),
        Path("Docs/Published/Deployment/Hosted_Staging_Runbook.md"),
        Path("Docs/Published/Deployment/Hosted_Production_Runbook.md"),
    ]

    for path in hosted_docs:
        _require(
            not path.exists(),
            f"expected hosted doc to be absent from public tree: {path}",
        )


def test_public_repo_does_not_ship_hosted_ops_and_asset_paths() -> None:
    hosted_paths = [
        Path("Docs/Operations/Hosted_Staging_Operations_Runbook.md"),
        Path("Docs/Operations/Hosted_Stripe_Test_Mode_Runbook.md"),
        Path("Dockerfiles/docker-compose.hosted-saas-staging.yml"),
        Path("Dockerfiles/docker-compose.hosted-saas-prod.yml"),
        Path("Dockerfiles/docker-compose.hosted-saas-prod.local-postgres.yml"),
        Path("tldw_Server_API/Config_Files/.env.hosted-staging.example"),
        Path("tldw_Server_API/Config_Files/.env.hosted-production.example"),
        Path("Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.compose"),
        Path("Helper_Scripts/Samples/Caddy/Caddyfile.hosted-saas.prod.compose"),
        Path("Helper_Scripts/validate_hosted_saas_profile.py"),
        Path("Helper_Scripts/Deployment/hosted_staging_preflight.py"),
        Path("tldw_Server_API/tests/test_hosted_production_compose.py"),
        Path("tldw_Server_API/tests/test_hosted_staging_compose.py"),
        Path("tldw_Server_API/tests/test_hosted_staging_preflight.py"),
        Path("tldw_Server_API/tests/AuthNZ/unit/test_validate_hosted_saas_profile.py"),
    ]

    for path in hosted_paths:
        _require(
            not path.exists(),
            f"expected hosted asset to be absent from public repo: {path}",
        )


def test_public_repo_does_not_ship_extracted_commercial_runtime_files() -> None:
    commercial_runtime_paths = [
        Path("tldw_Server_API/app/api/v1/endpoints/billing.py"),
        Path("tldw_Server_API/app/api/v1/endpoints/billing_webhooks.py"),
        Path("tldw_Server_API/app/core/Billing/stripe_client.py"),
        Path("tldw_Server_API/app/services/stripe_metering_service.py"),
        Path("tldw_Server_API/app/api/v1/endpoints/admin/admin_billing.py"),
        Path("tldw_Server_API/app/services/admin_billing_service.py"),
    ]

    for path in commercial_runtime_paths:
        _require(
            not path.exists(),
            f"expected extracted commercial runtime file to be absent from public repo: {path}",
        )


def test_mkdocs_workflow_runs_boundary_checker() -> None:
    workflow = Path(".github/workflows/mkdocs.yml").read_text(encoding="utf-8")

    _require(
        "python Helper_Scripts/docs/check_public_private_boundary.py" in workflow,
        "expected mkdocs workflow to run the public/private boundary checker",
    )
