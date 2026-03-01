from pathlib import Path

import yaml


def test_manifest_has_required_profiles() -> None:
    manifest = yaml.safe_load(Path("Docs/Getting_Started/onboarding_manifest.yaml").read_text())
    expected = {
        "local_single_user",
        "docker_single_user",
        "docker_multi_user_postgres",
        "gpu_stt_addon",
    }
    assert set(manifest["profiles"].keys()) == expected


def test_manifest_profile_schema_fields() -> None:
    manifest = yaml.safe_load(Path("Docs/Getting_Started/onboarding_manifest.yaml").read_text())
    required = {"title", "path", "published_path", "profile_type"}
    for key, meta in manifest["profiles"].items():
        missing = required - set(meta.keys())
        assert not missing, f"{key} missing fields: {sorted(missing)}"
