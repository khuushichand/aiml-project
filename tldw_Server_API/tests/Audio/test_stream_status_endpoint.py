import pytest


@pytest.mark.unit
def test_stream_status_shape(client_user_only):
    client = client_user_only
    r = client.get("/api/v1/audio/stream/status")
    assert r.status_code == 200
    data = r.json()

    # Basic top-level keys
    assert isinstance(data, dict)
    assert "status" in data
    assert data["status"] in {"available", "unavailable"}
    assert "available_models" in data
    assert isinstance(data["available_models"], list)
    assert all(isinstance(m, str) for m in data["available_models"])

    # Endpoint path advertised
    assert data.get("websocket_endpoint") == "/api/v1/audio/stream/transcribe"

    # Feature flags present
    sf = data.get("supported_features")
    assert isinstance(sf, dict)
    for key in (
        "partial_results",
        "multiple_languages",
        "concurrent_streams",
        "segment_metadata",
        "live_insights",
        "meeting_notes",
        "speaker_diarization",
        "audio_persistence",
    ):
        assert key in sf

    # If models are advertised, they should be known strings
    known_prefixes = ("parakeet-standard", "parakeet-onnx", "parakeet-mlx")
    for m in data["available_models"]:
        assert any(m.startswith(p.split("-")[0]) for p in known_prefixes)

