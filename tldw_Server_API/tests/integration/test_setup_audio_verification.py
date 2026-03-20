from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint
from tldw_Server_API.app.core.Setup.audio_profile_service import MachineProfile


def _make_client():
    return TestClient(app)


def test_setup_audio_verification_endpoint_persists_readiness(mocker, tmp_path):
    store = setup_endpoint.audio_readiness_store.AudioReadinessStore(
        tmp_path / "audio_readiness.json"
    )

    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": False},
    )
    mocker.patch.object(
        setup_endpoint.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=store,
    )
    mocker.patch.object(
        setup_endpoint.install_manager.audio_readiness_store,
        "get_audio_readiness_store",
        return_value=store,
    )
    mocker.patch.object(
        setup_endpoint.install_manager.audio_profile_service,
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
        setup_endpoint.install_manager.audio_health,
        "collect_setup_stt_health",
        new=AsyncMock(return_value={"usable": True, "model": "small"}),
    )
    mocker.patch.object(
        setup_endpoint.install_manager.audio_health,
        "collect_setup_tts_health",
        new=AsyncMock(
            return_value={
                "status": "healthy",
                "providers": {"kokoro": {"espeak_lib_exists": True}},
            }
        ),
    )

    with _make_client() as client:
        response = client.post(
            "/api/v1/setup/audio/verify",
            json={"bundle_id": "cpu_local", "resource_profile": "balanced"},
        )
        readiness = client.get("/api/v1/setup/audio/readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["selected_resource_profile"] == "balanced"
    assert readiness.status_code == 200
    assert readiness.json()["status"] == "ready"
    assert readiness.json()["selected_resource_profile"] == "balanced"
