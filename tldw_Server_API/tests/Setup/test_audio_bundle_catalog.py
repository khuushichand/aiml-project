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
