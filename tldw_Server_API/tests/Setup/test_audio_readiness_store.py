from tldw_Server_API.app.core.Setup import install_manager
from tldw_Server_API.app.core.Setup.audio_readiness_store import AudioReadinessStore


def test_audio_readiness_defaults_to_not_started(tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    readiness = store.load()

    assert readiness["status"] == "not_started"
    assert readiness["selected_bundle_id"] is None


def test_audio_readiness_update_persists_to_disk(tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    store.update(
        status="provisioning",
        selected_bundle_id="cpu_local",
        remediation_items=["Verification still pending"],
    )

    reloaded = AudioReadinessStore(tmp_path / "audio_readiness.json").load()

    assert reloaded["status"] == "provisioning"
    assert reloaded["selected_bundle_id"] == "cpu_local"
    assert reloaded["remediation_items"] == ["Verification still pending"]


def test_install_plan_success_marks_audio_readiness_partial(tmp_path, mocker):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")
    plan_payload = {
        "stt": [{"engine": "faster_whisper", "models": ["medium"]}],
        "tts": [],
        "embeddings": {
            "huggingface": [],
            "custom": [],
            "onnx": [],
        },
    }

    mocker.patch.object(
        install_manager.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=store,
    )
    mocker.patch.object(install_manager, "_install_dependencies")
    mocker.patch.object(install_manager, "_install_stt")
    mocker.patch.object(install_manager, "_install_tts")
    mocker.patch.object(install_manager, "_install_embeddings")

    install_manager.execute_install_plan(plan_payload)

    readiness = store.load()
    assert readiness["status"] == "partial"
    assert readiness["remediation_items"] == ["Run audio verification to confirm readiness."]
