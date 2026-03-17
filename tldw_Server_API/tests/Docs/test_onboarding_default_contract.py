from pathlib import Path

import pytest
import yaml


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def test_manifest_declares_default_profile_and_entrypoint() -> None:
    manifest = yaml.safe_load(Path("Docs/Getting_Started/onboarding_manifest.yaml").read_text())
    _require(
        manifest["default_profile"] == "docker_single_user",
        "Onboarding manifest should declare docker_single_user as the default profile",
    )
    _require(
        manifest["default_entrypoint"] == "quickstart-docker-webui",
        "Onboarding manifest should declare quickstart-docker-webui as the default entrypoint",
    )
