from tldw_Server_API.app.core.Setup import install_manager
from tldw_Server_API.app.core.Setup.audio_profile_service import MachineProfile
from tldw_Server_API.app.core.Setup.audio_readiness_store import AudioReadinessStore


def test_verification_marks_partial_when_tts_prereq_missing(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_stt_health",
        return_value={"usable": True, "model": "small"},
    )
    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_tts_health",
        return_value={
            "status": "healthy",
            "providers": {
                "kokoro": {"espeak_lib_exists": False},
            },
        },
    )
    mocker.patch.object(
        install_manager.audio_profile_service,
        "detect_machine_profile",
        return_value=MachineProfile(
            platform="linux",
            arch="x86_64",
            apple_silicon=False,
            cuda_available=False,
            ffmpeg_available=True,
            espeak_available=False,
            free_disk_gb=64.0,
            network_available_for_downloads=True,
        ),
    )
    mocker.patch.object(
        install_manager.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=store,
    )

    result = install_manager.verify_audio_bundle("cpu_local")

    assert result["status"] == "partial"
    assert any(item["code"] == "KOKORO_ESPEAK_MISSING" for item in result["remediation_items"])
    assert store.load()["status"] == "partial"


def test_verification_marks_ready_when_primary_paths_are_usable(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_stt_health",
        return_value={"usable": True, "model": "small"},
    )
    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_tts_health",
        return_value={
            "status": "healthy",
            "providers": {
                "kokoro": {"espeak_lib_exists": True},
            },
        },
    )
    mocker.patch.object(
        install_manager.audio_profile_service,
        "detect_machine_profile",
        return_value=MachineProfile(
            platform="linux",
            arch="x86_64",
            apple_silicon=False,
            cuda_available=False,
            ffmpeg_available=True,
            espeak_available=True,
            free_disk_gb=64.0,
            network_available_for_downloads=True,
        ),
    )
    mocker.patch.object(
        install_manager.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=store,
    )

    result = install_manager.verify_audio_bundle("cpu_local")

    assert result["status"] == "ready"
    assert result["remediation_items"] == []
    assert store.load()["status"] == "ready"
