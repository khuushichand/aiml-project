import os
import pytest


pytestmark = pytest.mark.unit


def test_stream_ttl_env_cache_and_clear(monkeypatch):
    from tldw_Server_API.app.core.Usage import audio_quota as aq

    # Ensure a clean start
    aq.clear_stream_ttl_cache()

    # Set env to 45 and read
    monkeypatch.setenv("AUDIO_STREAM_TTL_SECONDS", "45")
    v1 = aq._get_stream_ttl_seconds()
    assert v1 == 45

    # Change env to 60, but without clearing cache it should not change
    monkeypatch.setenv("AUDIO_STREAM_TTL_SECONDS", "60")
    v_cached = aq._get_stream_ttl_seconds()
    assert v_cached == 45

    # Clear cache → value should refresh to 60
    aq.clear_stream_ttl_cache()
    v2 = aq._get_stream_ttl_seconds()
    assert v2 == 60

    # Test clamping low
    monkeypatch.setenv("AUDIO_STREAM_TTL_SECONDS", "5")
    aq.clear_stream_ttl_cache()
    assert aq._get_stream_ttl_seconds() == 30

    # Test clamping high
    monkeypatch.setenv("AUDIO_STREAM_TTL_SECONDS", "100000")
    aq.clear_stream_ttl_cache()
    assert aq._get_stream_ttl_seconds() == 3600

    # Unset env → should fall back to default 120 (config may be absent in tests)
    monkeypatch.delenv("AUDIO_STREAM_TTL_SECONDS", raising=False)
    aq.clear_stream_ttl_cache()
    assert aq._get_stream_ttl_seconds() == 120
