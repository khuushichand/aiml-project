from pathlib import Path

import pytest
import yaml


def _require(condition: bool, message: str) -> None:
    if not condition:
        pytest.fail(message)


def test_manifest_has_required_profiles() -> None:
    manifest = yaml.safe_load(Path("Docs/Getting_Started/onboarding_manifest.yaml").read_text())
    expected = {
        "local_single_user",
        "docker_single_user",
        "docker_multi_user_postgres",
        "first_time_audio_cpu",
        "first_time_audio_gpu_accelerated",
        "gpu_stt_addon",
    }
    _require(
        set(manifest["profiles"].keys()) == expected,
        f"Unexpected onboarding profiles: {sorted(manifest['profiles'].keys())}",
    )


def test_manifest_profile_schema_fields() -> None:
    manifest = yaml.safe_load(Path("Docs/Getting_Started/onboarding_manifest.yaml").read_text())
    required = {"title", "path", "published_path", "profile_type"}
    for key, meta in manifest["profiles"].items():
        missing = required - set(meta.keys())
        _require(not missing, f"{key} missing fields: {sorted(missing)}")
