import pytest

from tldw_Server_API.app.core.Setup import install_manager
from tldw_Server_API.app.core.Setup import audio_readiness_store
from tldw_Server_API.app.core.Setup.audio_readiness_store import AudioReadinessStore


def test_audio_readiness_defaults_to_not_started(tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    readiness = store.load()

    assert readiness["status"] == "not_started"
    assert readiness["selected_bundle_id"] is None
    assert readiness["selected_resource_profile"] == "balanced"


def test_audio_readiness_update_persists_to_disk(tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    store.update(
        status="provisioning",
        selected_bundle_id="cpu_local",
        selected_resource_profile="light",
        tts_choice="kitten_tts",
        selection_key="v2:cpu_local:light:kitten_tts",
        remediation_items=["Verification still pending"],
    )

    reloaded = AudioReadinessStore(tmp_path / "audio_readiness.json").load()

    assert reloaded["status"] == "provisioning"
    assert reloaded["selected_bundle_id"] == "cpu_local"
    assert reloaded["selected_resource_profile"] == "light"
    assert reloaded["tts_choice"] == "kitten_tts"
    assert reloaded["selection_key"] == "v2:cpu_local:light:kitten_tts"
    assert reloaded["remediation_items"] == ["Verification still pending"]


def test_readiness_defaults_missing_profile_to_balanced(tmp_path):
    readiness_path = tmp_path / "audio_readiness.json"
    readiness_path.write_text('{"status": "ready", "selected_bundle_id": "cpu_local"}', encoding="utf-8")

    readiness = AudioReadinessStore(readiness_path).load()

    assert readiness["selected_resource_profile"] == "balanced"


def test_readiness_canonicalizes_default_tts_choice_identity(tmp_path):
    readiness_path = tmp_path / "audio_readiness.json"
    readiness_path.write_text(
        (
            '{"status":"ready","selected_bundle_id":"cpu_local","selected_resource_profile":"balanced",'
            '"tts_choice":"kokoro","selection_key":"v2:cpu_local:balanced:kokoro"}'
        ),
        encoding="utf-8",
    )

    readiness = AudioReadinessStore(readiness_path).load()

    assert readiness["tts_choice"] is None
    assert readiness["selection_key"] == "v2:cpu_local:balanced"


def test_readiness_save_rewrites_stale_selection_key_to_canonical_identity(tmp_path):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    saved = store.save(
        {
            "status": "ready",
            "selected_bundle_id": "cpu_local",
            "selected_resource_profile": "balanced",
            "tts_choice": "kokoro",
            "selection_key": "v2:cpu_local:balanced:kokoro",
        }
    )

    assert saved["tts_choice"] is None
    assert saved["selection_key"] == "v2:cpu_local:balanced"


def test_readiness_save_does_not_swallow_unexpected_catalog_errors(tmp_path, monkeypatch):
    store = AudioReadinessStore(tmp_path / "audio_readiness.json")

    class _BrokenCatalog:
        def bundle_by_id(self, bundle_id):
            raise RuntimeError(f"broken catalog lookup for {bundle_id}")

    monkeypatch.setattr(audio_readiness_store, "get_audio_bundle_catalog", lambda: _BrokenCatalog())

    with pytest.raises(RuntimeError, match="broken catalog lookup"):
        store.save(
            {
                "status": "ready",
                "selected_bundle_id": "cpu_local",
                "selected_resource_profile": "balanced",
                "tts_choice": "kokoro",
            }
        )


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
