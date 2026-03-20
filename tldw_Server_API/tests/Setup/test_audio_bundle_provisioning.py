import pytest

from tldw_Server_API.app.core.Setup import install_manager
from tldw_Server_API.app.core.Setup.audio_bundle_catalog import build_audio_selection_key
from tldw_Server_API.app.core.Setup.audio_profile_service import MachineProfile
from tldw_Server_API.app.core.Setup.audio_readiness_store import AudioReadinessStore


def test_cpu_local_bundle_expands_to_expected_install_plan():
    plan = install_manager.build_install_plan_from_bundle("cpu_local")

    assert [entry.engine for entry in plan.stt] == ["faster_whisper"]
    assert [entry.engine for entry in plan.tts] == ["kokoro"]


def test_cpu_local_performance_profile_expands_to_profile_specific_install_plan():
    plan = install_manager.build_install_plan_from_bundle("cpu_local", resource_profile="performance")

    assert [entry.engine for entry in plan.stt] == ["faster_whisper"]
    assert plan.stt[0].models == ["medium"]


def test_step_names_include_profile_identity():
    plan = install_manager.build_install_plan_from_bundle("cpu_local", resource_profile="performance")
    step_names = install_manager._plan_step_names(
        plan,
        bundle_id="cpu_local",
        resource_profile="performance",
        catalog_version="v2",
    )

    assert f"{build_audio_selection_key('cpu_local', 'performance', 'v2')}:deps:stt:faster_whisper" in step_names
    assert f"{build_audio_selection_key('cpu_local', 'performance', 'v2')}:stt:faster_whisper:medium" in step_names


def test_selection_key_includes_tts_choice_identity():
    assert build_audio_selection_key(
        "cpu_local",
        "balanced",
        "v2",
        tts_choice="kitten_tts",
    ) == "v2:cpu_local:balanced:kitten_tts"


def test_cpu_local_bundle_expands_to_curated_tts_choice_install_plan():
    plan = install_manager.build_install_plan_from_bundle(
        "cpu_local",
        resource_profile="balanced",
        tts_choice="kitten_tts",
    )

    assert [entry.engine for entry in plan.tts] == ["kitten_tts"]


def test_build_install_plan_rejects_invalid_curated_tts_choice_with_value_error():
    with pytest.raises(ValueError, match="Unknown curated TTS choice"):
        install_manager.build_install_plan_from_bundle(
            "cpu_local",
            resource_profile="balanced",
            tts_choice="bogus_choice",
        )


def test_execute_audio_bundle_canonicalizes_default_tts_choice_identity(mocker, tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

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
    mocker.patch.object(
        install_manager,
        "execute_install_plan",
        return_value={"status": "completed", "steps": [], "errors": []},
    )

    omitted_choice = install_manager.execute_audio_bundle("cpu_local", resource_profile="balanced")
    explicit_default_choice = install_manager.execute_audio_bundle(
        "cpu_local",
        resource_profile="balanced",
        tts_choice="kokoro",
    )

    assert omitted_choice["selection_key"] == "v2:cpu_local:balanced"
    assert explicit_default_choice["selection_key"] == "v2:cpu_local:balanced"
    assert omitted_choice["selection_key"] == explicit_default_choice["selection_key"]
    assert omitted_choice["tts_choice"] is None
    assert explicit_default_choice["tts_choice"] is None


def test_verify_audio_bundle_uses_selected_tts_choice_and_persists_canonical_identity(mocker, tmp_path):
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
            "providers": {"kitten_tts": {"status": "healthy"}},
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

    readiness = store.load()
    assert result["status"] == "ready"
    assert result["tts_choice"] == "kitten_tts"
    assert result["selection_key"] == "v2:cpu_local:balanced:kitten_tts"
    assert readiness["tts_choice"] == "kitten_tts"
    assert readiness["selection_key"] == "v2:cpu_local:balanced:kitten_tts"
    assert readiness["last_verification"]["tts_choice"] == "kitten_tts"


def test_safe_rerun_skips_bundle_when_expected_steps_are_already_completed(mocker):
    selection_key = build_audio_selection_key("cpu_local", "balanced", "v2")
    mocker.patch.object(
        install_manager,
        "get_install_status_snapshot",
        return_value={
            "status": "completed",
            "steps": [
                {"name": f"{selection_key}:deps:stt:faster_whisper", "status": "completed"},
                {"name": f"{selection_key}:stt:faster_whisper:small", "status": "completed"},
                {"name": f"{selection_key}:stt:silero_vad", "status": "completed"},
                {"name": f"{selection_key}:deps:tts:kokoro", "status": "completed"},
                {"name": f"{selection_key}:tts:kokoro:default", "status": "completed"},
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

    result = install_manager.execute_audio_bundle("cpu_local", tts_choice="kokoro", safe_rerun=True)

    execute_mock.assert_not_called()
    assert "skipped" in {step["status"] for step in result["steps"]}
    assert result["tts_choice"] is None


def test_safe_rerun_does_not_skip_when_profile_changes(mocker):
    selection_key = build_audio_selection_key("cpu_local", "light", "v2")
    mocker.patch.object(
        install_manager,
        "get_install_status_snapshot",
        return_value={
            "status": "completed",
            "steps": [
                {"name": f"{selection_key}:deps:stt:faster_whisper", "status": "completed"},
                {"name": f"{selection_key}:stt:faster_whisper:tiny", "status": "completed"},
                {"name": f"{selection_key}:stt:silero_vad", "status": "completed"},
                {"name": f"{selection_key}:deps:tts:kokoro", "status": "completed"},
                {"name": f"{selection_key}:tts:kokoro:default", "status": "completed"},
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
    execute_mock = mocker.patch.object(
        install_manager,
        "execute_install_plan",
        return_value={"status": "completed", "steps": []},
    )

    result = install_manager.execute_audio_bundle(
        "cpu_local",
        resource_profile="performance",
        safe_rerun=True,
    )

    execute_mock.assert_called_once()
    assert result["status"] == "completed"
