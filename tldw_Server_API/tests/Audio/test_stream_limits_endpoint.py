import pytest


@pytest.mark.unit
def test_stream_limits_shape(client_user_only):
    client = client_user_only
    r = client.get("/api/v1/audio/stream/limits")
    assert r.status_code == 200
    data = r.json()

    # Top-level shape
    assert isinstance(data, dict)
    assert "user_id" in data and isinstance(data["user_id"], int)
    assert "tier" in data and isinstance(data["tier"], str)
    assert "limits" in data and isinstance(data["limits"], dict)
    assert "used_today_minutes" in data
    assert "remaining_minutes" in data  # may be None for unlimited tiers
    assert "active_streams" in data and isinstance(data["active_streams"], int)
    assert "can_start_stream" in data and isinstance(data["can_start_stream"], bool)

    # Limits structure
    limits = data["limits"]
    for key in ("daily_minutes", "concurrent_streams", "concurrent_jobs", "max_file_size_mb"):
        assert key in limits

    # Value sanity (types only; values are environment/config-dependent)
    if limits["daily_minutes"] is not None:
        assert isinstance(limits["daily_minutes"], (int, float))
    assert isinstance(limits["concurrent_streams"], int)
    assert isinstance(limits["concurrent_jobs"], int)
    assert isinstance(limits["max_file_size_mb"], int)
