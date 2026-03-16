from tldw_Server_API.app.core.Setup.audio_profile_service import (
    MachineProfile,
    rank_audio_bundles,
    recommend_audio_bundles,
)


def test_nvidia_machine_prefers_nvidia_bundle():
    profile = MachineProfile(
        platform="linux",
        arch="x86_64",
        apple_silicon=False,
        cuda_available=True,
        ffmpeg_available=True,
        espeak_available=True,
        free_disk_gb=80.0,
        network_available_for_downloads=True,
    )

    ranked = rank_audio_bundles(
        profile,
        prefer_offline_runtime=True,
        allow_hosted_fallbacks=True,
    )

    assert ranked[0].bundle_id == "nvidia_local"


def test_hosted_bundle_drops_when_hosted_fallbacks_disabled():
    profile = MachineProfile(
        platform="linux",
        arch="x86_64",
        apple_silicon=False,
        cuda_available=False,
        ffmpeg_available=True,
        espeak_available=True,
        free_disk_gb=40.0,
        network_available_for_downloads=True,
    )

    ranked = rank_audio_bundles(
        profile,
        prefer_offline_runtime=True,
        allow_hosted_fallbacks=False,
    )

    assert all(bundle.bundle_id != "hosted_plus_local_backup" for bundle in ranked)


def test_unsupported_hardware_bundles_move_to_excluded_list():
    profile = MachineProfile(
        platform="linux",
        arch="x86_64",
        apple_silicon=False,
        cuda_available=False,
        ffmpeg_available=True,
        espeak_available=True,
        free_disk_gb=40.0,
        network_available_for_downloads=True,
    )

    result = recommend_audio_bundles(
        profile,
        prefer_offline_runtime=True,
        allow_hosted_fallbacks=True,
    )

    recommendation_ids = {bundle["bundle_id"] for bundle in result["recommendations"]}
    excluded_ids = {bundle["bundle_id"] for bundle in result["excluded"]}

    assert "nvidia_local" not in recommendation_ids
    assert "apple_silicon_local" not in recommendation_ids
    assert {"nvidia_local", "apple_silicon_local"} <= excluded_ids
