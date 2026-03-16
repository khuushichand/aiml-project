from tldw_Server_API.app.core.Setup import install_manager
from tldw_Server_API.app.core.Setup.audio_profile_service import MachineProfile


def test_cpu_local_bundle_expands_to_expected_install_plan():
    plan = install_manager.build_install_plan_from_bundle("cpu_local")

    assert [entry.engine for entry in plan.stt] == ["faster_whisper"]
    assert [entry.engine for entry in plan.tts] == ["kokoro"]


def test_safe_rerun_skips_bundle_when_expected_steps_are_already_completed(mocker):
    mocker.patch.object(
        install_manager,
        "get_install_status_snapshot",
        return_value={
            "status": "completed",
            "steps": [
                {"name": "deps:stt:faster_whisper", "status": "completed"},
                {"name": "stt:faster_whisper", "status": "completed"},
                {"name": "stt:silero_vad", "status": "completed"},
                {"name": "deps:tts:kokoro", "status": "completed"},
                {"name": "tts:kokoro", "status": "completed"},
            ],
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
    )
    execute_mock = mocker.patch.object(install_manager, "execute_install_plan")

    result = install_manager.execute_audio_bundle("cpu_local", safe_rerun=True)

    execute_mock.assert_not_called()
    assert "skipped" in {step["status"] for step in result["steps"]}
