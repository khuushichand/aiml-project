from tldw_Server_API.app.core.Setup.audio_bundle_catalog import get_audio_bundle_catalog


def test_catalog_contains_expected_v1_bundle_ids():
    catalog = get_audio_bundle_catalog()
    bundle_ids = {bundle.bundle_id for bundle in catalog.bundles}

    assert {
        "cpu_local",
        "apple_silicon_local",
        "nvidia_local",
        "hosted_plus_local_backup",
    } <= bundle_ids


def test_bundle_declares_automation_tiers_for_steps():
    catalog = get_audio_bundle_catalog()
    bundle = catalog.bundle_by_id("cpu_local")

    all_install_steps = bundle.system_prerequisites + bundle.python_dependencies + bundle.model_assets

    assert any(step.automation_tier == "automatic" for step in all_install_steps)
    assert any(step.automation_tier == "guided" for step in bundle.system_prerequisites)


def test_cpu_local_bundle_exposes_named_resource_profiles():
    bundle = get_audio_bundle_catalog().bundle_by_id("cpu_local")

    assert {"light", "balanced", "performance"} <= set(bundle.resource_profiles.keys())


def test_apple_silicon_balanced_profile_prefers_parakeet_mlx():
    catalog = get_audio_bundle_catalog()
    profile = catalog.bundle_by_id("apple_silicon_local").profile_by_id("balanced")

    assert profile.stt_plan == [{"engine": "nemo_parakeet_mlx", "models": []}]
    assert profile.tts_plan == [{"engine": "kokoro", "variants": []}]


def test_apple_silicon_performance_profile_prefers_parakeet_mlx():
    catalog = get_audio_bundle_catalog()
    profile = catalog.bundle_by_id("apple_silicon_local").profile_by_id("performance")

    assert profile.stt_plan == [{"engine": "nemo_parakeet_mlx", "models": []}]
    assert profile.tts_plan == [{"engine": "kokoro", "variants": []}]


def test_nvidia_balanced_profile_uses_parakeet_path():
    catalog = get_audio_bundle_catalog()
    profile = catalog.bundle_by_id("nvidia_local").profile_by_id("balanced")

    assert profile.stt_plan[0]["engine"] in {"nemo_parakeet_standard", "nemo_parakeet_onnx"}
    assert profile.tts_plan == [{"engine": "kokoro", "variants": []}]


def test_nvidia_performance_profile_uses_parakeet_and_local_tts():
    catalog = get_audio_bundle_catalog()
    profile = catalog.bundle_by_id("nvidia_local").profile_by_id("performance")

    assert profile.stt_plan[0]["engine"] == "nemo_parakeet_standard"
    assert profile.tts_plan[0]["engine"] in {"dia", "higgs"}
