import pytest

from tldw_Server_API.app.core.Setup import install_manager
from tldw_Server_API.app.core.Setup.audio_bundle_catalog import get_audio_bundle_catalog
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

    result = install_manager.verify_audio_bundle("cpu_local", resource_profile="balanced")

    assert result["status"] == "partial"
    assert result["selected_resource_profile"] == "balanced"
    assert any(item["code"] == "KOKORO_ESPEAK_MISSING" for item in result["remediation_items"])
    assert store.load()["status"] == "partial"


def test_verification_marks_ready_when_primary_paths_are_usable(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_stt_health",
        return_value={"usable": True, "model": "medium"},
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

    result = install_manager.verify_audio_bundle("cpu_local", resource_profile="performance")

    assert result["status"] == "ready"
    assert result["selected_resource_profile"] == "performance"
    assert result["remediation_items"] == []
    assert store.load()["status"] == "ready"
    assert store.load()["selected_resource_profile"] == "performance"


def test_verify_audio_bundle_uses_selected_profile_targets(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_stt_health",
        return_value={"usable": True, "model": None},
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
            platform="darwin",
            arch="arm64",
            apple_silicon=True,
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

    result = install_manager.verify_audio_bundle("apple_silicon_local", resource_profile="balanced")

    assert result["bundle_id"] == "apple_silicon_local"
    assert result["selected_resource_profile"] == "balanced"
    assert "targets_checked" not in result


def test_verify_audio_bundle_uses_selected_kitten_tts_choice(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_stt_health",
        return_value={"usable": True, "model": "medium"},
    )
    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_tts_health",
        return_value={
            "status": "healthy",
            "providers": {
                "kitten_tts": {"status": "healthy"},
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

    result = install_manager.verify_audio_bundle(
        "cpu_local",
        resource_profile="balanced",
        tts_choice="kitten_tts",
    )

    assert result["tts_choice"] == "kitten_tts"
    readiness = store.load()
    assert readiness["tts_choice"] == "kitten_tts"
    assert readiness["selection_key"] == "v2:cpu_local:balanced:kitten_tts"


def test_verify_audio_bundle_redacts_nested_health_debug_details(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_stt_health",
        return_value={
            "usable": False,
            "message": "Initialization failed.",
            "details": "/Users/private/model.bin",
            "traceback": "Traceback: /Users/private/model.bin",
            "nested": {"exception": "boom"},
        },
    )
    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_tts_health",
        return_value={
            "status": "error",
            "providers": {
                "kokoro": {
                    "status": "failed",
                    "details": "/Users/private/voices.json",
                }
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

    result = install_manager.verify_audio_bundle("cpu_local", resource_profile="balanced")

    assert "details" not in result["stt_health"]
    assert "traceback" not in result["stt_health"]
    assert "exception" not in result["stt_health"]["nested"]
    assert "details" not in result["tts_health"]["providers"]["kokoro"]

    readiness = store.load()
    assert "details" not in readiness["last_verification"]["stt_health"]
    assert "details" not in readiness["last_verification"]["tts_health"]["providers"]["kokoro"]


def test_verify_audio_bundle_rejects_invalid_curated_tts_choice_with_value_error():
    with pytest.raises(ValueError, match="Unknown curated TTS choice"):
        install_manager.verify_audio_bundle(
            "cpu_local",
            resource_profile="balanced",
            tts_choice="bogus_choice",
        )


def test_verification_remediation_uses_stable_codes_for_primary_paths(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_stt_health",
        return_value={"usable": False, "model": None},
    )
    mocker.patch.object(
        install_manager.audio_health,
        "collect_setup_tts_health",
        return_value={
            "status": "failed",
            "providers": {
                "dia": {"status": "failed"},
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
            cuda_available=True,
            ffmpeg_available=True,
            espeak_available=True,
            free_disk_gb=128.0,
            network_available_for_downloads=True,
        ),
    )
    mocker.patch.object(
        install_manager.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=store,
    )

    result = install_manager.verify_audio_bundle("nvidia_local", resource_profile="performance")
    remediation_codes = {item["code"] for item in result["remediation_items"]}

    assert "STT_UNUSABLE" in remediation_codes
    assert "TTS_UNHEALTHY" in remediation_codes


def test_cuda_available_ignores_cuda_env_without_verified_gpu(mocker):
    mocker.patch.dict(
        install_manager.os.environ,
        {"CUDA_HOME": "/usr/local/cuda", "CUDA_PATH": "/usr/local/cuda"},
        clear=False,
    )
    mocker.patch.object(install_manager.shutil, "which", return_value=None)

    assert install_manager._cuda_available() is False


def test_cuda_available_requires_working_nvidia_smi_probe(mocker):
    mocker.patch.object(install_manager.shutil, "which", return_value="/usr/bin/nvidia-smi")
    mocker.patch.object(
        install_manager.subprocess,
        "run",
        return_value=mocker.Mock(returncode=0, stdout="GPU 0: Mock GPU\n", stderr=""),
    )

    assert install_manager._cuda_available() is True
