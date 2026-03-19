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
