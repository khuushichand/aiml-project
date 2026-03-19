from Helper_Scripts.generate_audio_bundle_docs import _iter_profiles, generate_bundle_docs_text
from tldw_Server_API.app.core.Setup.audio_bundle_catalog import AudioBundle, AudioResourceProfile


def test_generated_bundle_docs_reference_all_v1_bundle_ids() -> None:
    content = generate_bundle_docs_text()

    assert "cpu_local" in content
    assert "apple_silicon_local" in content
    assert "nvidia_local" in content
    assert "hosted_plus_local_backup" in content
    assert "Offline runtime after provisioning" in content
    assert "Offline pack compatibility" in content
    assert "Guided prerequisites" in content
    assert "Balanced" in content
    assert "Performance" in content


def test_iter_profiles_uses_catalog_defined_order() -> None:
    bundle = AudioBundle(
        bundle_id="custom_order",
        label="Custom Order",
        description="Test bundle",
        default_resource_profile="balanced",
        resource_profiles={
            "balanced": AudioResourceProfile(profile_id="balanced", label="Balanced"),
            "performance": AudioResourceProfile(profile_id="performance", label="Performance"),
            "light": AudioResourceProfile(profile_id="light", label="Light"),
        },
    )

    assert [profile.profile_id for profile in _iter_profiles(bundle)] == [
        "balanced",
        "performance",
        "light",
    ]
