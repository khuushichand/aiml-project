from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint


def _make_client():
    return TestClient(app)


def test_setup_audio_recommendations_endpoint_returns_profile_and_ranked_bundles(mocker):
    mocker.patch.object(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        return_value={"enabled": True, "needs_setup": True},
    )
    mocker.patch.object(
        setup_endpoint.audio_profile_service,
        "detect_machine_profile",
        return_value={
            "platform": "linux",
            "arch": "x86_64",
            "apple_silicon": False,
            "cuda_available": False,
            "ffmpeg_available": True,
            "espeak_available": True,
            "free_disk_gb": 64.0,
            "network_available_for_downloads": True,
        },
    )
    mocker.patch.object(
        setup_endpoint.audio_profile_service,
        "recommend_audio_bundles",
        return_value={
            "recommendations": [
                {
                    "bundle_id": "cpu_local",
                    "resource_profile": "balanced",
                    "selection_key": "v2:cpu_local:balanced",
                    "confidence": "high",
                    "label": "CPU Local",
                    "reasons": ["Local-first default"],
                }
            ],
            "excluded": [
                {"bundle_id": "nvidia_local", "reasons": ["CUDA not detected"]}
            ],
        },
    )

    with _make_client() as client:
        response = client.get("/api/v1/setup/audio/recommendations")

    assert response.status_code == 200
    body = response.json()
    assert body["machine_profile"]["platform"] == "linux"
    assert body["recommendations"][0]["bundle_id"] == "cpu_local"
    assert body["recommendations"][0]["resource_profile"] == "balanced"
    assert body["recommendations"][0]["selection_key"] == "v2:cpu_local:balanced"
    assert body["recommendations"][0]["confidence"] == "high"
    assert body["excluded"][0]["bundle_id"] == "nvidia_local"
